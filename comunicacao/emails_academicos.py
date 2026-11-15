"""Eventos e envio do RF33, independentes dos e-mails manuais de pendências (RF32)."""

import hashlib
import logging
import uuid
from datetime import timedelta
from decimal import Decimal
from functools import partial

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from painel.servicos import indicadores_da_turma, indicadores_do_aluno
from turmas.models import Matricula, Turma

from .models import EmailAcademico, EstadoAlertaAtencao

logger = logging.getLogger("simap.integracoes")
TEMPO_RESERVA = timedelta(minutes=10)


def assinatura_feedback(avaliacao):
    conteudo = f"{Decimal(str(avaliacao.nota)):.1f}\n{avaliacao.feedback_professor}"
    return hashlib.sha256(conteudo.encode()).hexdigest()


def registrar_feedback(avaliacao):
    """Registra junto à avaliação; só tenta HTTP quando a transação for confirmada."""
    assinatura = assinatura_feedback(avaliacao)
    versao = avaliacao.avaliado_em.isoformat()
    chave = f"feedback:{avaliacao.pk}:{hashlib.sha256((assinatura + versao).encode()).hexdigest()}"
    with transaction.atomic():
        # Uma revisão substitui avisos ainda não enviados de versões anteriores.
        EmailAcademico.objects.filter(
            tipo=EmailAcademico.Tipo.FEEDBACK,
            avaliacao=avaliacao,
            status=EmailAcademico.Status.PENDENTE,
        ).exclude(chave=chave).update(status=EmailAcademico.Status.CANCELADO)
        aviso, criado = EmailAcademico.objects.get_or_create(
            chave=chave,
            defaults={
                "tipo": EmailAcademico.Tipo.FEEDBACK,
                "destinatario_id": avaliacao.submissao.aluno_id,
                "avaliacao": avaliacao,
                "assinatura": assinatura,
            },
        )
        if criado:
            transaction.on_commit(partial(enviar_aviso, aviso.pk), robust=True)


def verificar_atencao():
    """Usa os mesmos indicadores do painel, inclusive para prazos que venceram."""
    elegiveis = Q(
        matricula__status="ATIVA",
        matricula__discente__is_active=True,
        matricula__discente__perfil="DISCENTE",
        matricula__turma__ativa=True,
        matricula__turma__docente__is_active=True,
        matricula__turma__docente__perfil="DOCENTE",
    )
    EstadoAlertaAtencao.objects.exclude(elegiveis).update(em_atencao=False)
    criados = 0
    for turma in Turma.objects.filter(ativa=True, docente__is_active=True, docente__perfil="DOCENTE"):
        matriculas = {
            m.discente_id: m
            for m in Matricula.objects.filter(
                turma=turma,
                status="ATIVA",
                discente__is_active=True,
                discente__perfil="DISCENTE",
            )
        }
        for linha in indicadores_da_turma(turma):
            matricula = matriculas.get(linha["discente"].pk)
            if matricula is None:
                continue
            with transaction.atomic():
                EstadoAlertaAtencao.objects.get_or_create(
                    matricula=matricula,
                    defaults={"docente_id": turma.docente_id},
                )
                estado = EstadoAlertaAtencao.objects.select_for_update().get(matricula=matricula)
                novo = linha["em_atencao"] and (not estado.em_atencao or estado.docente_id != turma.docente_id)
                estado.em_atencao = linha["em_atencao"]
                estado.docente_id = turma.docente_id
                if novo:
                    estado.episodio += 1
                    _, criado = EmailAcademico.objects.get_or_create(
                        chave=f"atencao:{matricula.pk}:{estado.episodio}",
                        defaults={
                            "tipo": EmailAcademico.Tipo.ATENCAO,
                            "destinatario_id": turma.docente_id,
                            "matricula": matricula,
                            "episodio": estado.episodio,
                        },
                    )
                    criados += int(criado)
                estado.save()
    return criados


def _acesso(caminho, instrucao):
    base = settings.SIMAP_PUBLIC_URL.rstrip("/")
    return f"{instrucao}\n{base}{caminho}" if base else instrucao


def _mensagem(aviso):
    """Revalida o vínculo antes de enviar, inclusive em uma nova tentativa."""
    if not aviso.destinatario.is_active:
        return None
    if aviso.tipo == EmailAcademico.Tipo.FEEDBACK:
        avaliacao = aviso.avaliacao
        submissao = avaliacao.submissao
        atividade = submissao.atividade
        turma = atividade.trilha.turma
        if (
            aviso.destinatario_id != submissao.aluno_id
            or not aviso.destinatario.is_discente
            or assinatura_feedback(avaliacao) != aviso.assinatura
            or not atividade.publicada
            or not atividade.trilha.publicada
            or not turma.ativa
            or not Matricula.objects.filter(turma=turma, discente_id=submissao.aluno_id, status="ATIVA").exists()
        ):
            return None
        return (
            "SIMAP: feedback disponível",
            "Uma avaliação com nota e/ou feedback foi publicada ou atualizada para você.\n\n"
            + _acesso(reverse("entregas:resolver", args=[atividade.pk]), "Entre no SIMAP para consultar sua avaliação.")
            + "\n\nA nota e o feedback permanecem disponíveis somente dentro do sistema.",
        )
    matricula = aviso.matricula
    turma = matricula.turma
    estado = EstadoAlertaAtencao.objects.filter(matricula=matricula).first()
    if (
        turma.docente_id != aviso.destinatario_id
        or not aviso.destinatario.is_docente
        or not turma.ativa
        or not matricula.discente.is_active
        or not matricula.discente.is_discente
        or not estado
        or not estado.em_atencao
        or estado.episodio != aviso.episodio
    ):
        return None
    linha = indicadores_do_aluno(turma, matricula.discente)
    if not linha or not linha["em_atencao"]:
        return None
    return (
        "SIMAP: aluno em situação de atenção",
        "Um aluno de uma turma sob sua responsabilidade entrou em situação de atenção.\n\n"
        + _acesso(
            reverse("painel:detalhe_aluno", args=[turma.pk, matricula.discente_id]),
            "Entre no painel do SIMAP para consultar os indicadores e acompanhar o aluno.",
        )
        + "\n\nEssa sinalização usa o limite configurado na turma e não representa um diagnóstico.",
    )


def enviar_aviso(pk):
    """Reserva sem manter transação aberta durante HTTP. Falhas ficam pendentes."""
    reserva = uuid.uuid4()
    agora = timezone.now()
    disponivel = Q(status=EmailAcademico.Status.PENDENTE) | Q(
        status=EmailAcademico.Status.ENVIANDO,
        reservado_em__lt=agora - TEMPO_RESERVA,
    )
    obtido = EmailAcademico.objects.filter(disponivel, pk=pk).update(
        status=EmailAcademico.Status.ENVIANDO,
        reserva=reserva,
        reservado_em=agora,
        tentativas=F("tentativas") + 1,
    )
    if not obtido:
        return "ignorado"
    registro = EmailAcademico.objects.filter(pk=pk, reserva=reserva)
    try:
        aviso = EmailAcademico.objects.select_related(
            "destinatario",
            "avaliacao__submissao__atividade__trilha__turma",
            "matricula__turma",
            "matricula__discente",
        ).get(pk=pk)
        if aviso.tipo == EmailAcademico.Tipo.FEEDBACK:
            atividade = aviso.avaliacao.submissao.atividade
            if not atividade.publicada or not atividade.trilha.publicada:
                # Uma avaliação de rascunho só é anunciada quando ficar visível.
                registro.update(status=EmailAcademico.Status.PENDENTE, reserva=None)
                return "aguardando_publicacao"
        mensagem = _mensagem(aviso)
        if mensagem is None:
            registro.update(status=EmailAcademico.Status.CANCELADO, reserva=None)
            return "cancelado"
        if not aviso.destinatario.email:
            registro.update(status=EmailAcademico.Status.PENDENTE, reserva=None)
            return "sem_email"
        assunto, corpo = mensagem
        enviados = send_mail(
            assunto, corpo, settings.DEFAULT_FROM_EMAIL, [aviso.destinatario.email], fail_silently=False
        )
        if enviados != 1:
            raise RuntimeError("Backend não confirmou o envio do aviso acadêmico")
        registro.update(status=EmailAcademico.Status.ENVIADO, enviado_em=timezone.now(), reserva=None)
        return "enviado"
    except Exception:
        registro.update(status=EmailAcademico.Status.PENDENTE, reserva=None)
        logger.exception("Falha no envio do aviso acadêmico #%s; permanece pendente", pk)
        return "falha"


def processar_pendentes(limite=200):
    disponiveis = (
        EmailAcademico.objects.filter(
            Q(status=EmailAcademico.Status.PENDENTE)
            | Q(status=EmailAcademico.Status.ENVIANDO, reservado_em__lt=timezone.now() - TEMPO_RESERVA)
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:limite]
    )
    resultados = {}
    for pk in list(disponiveis):
        resultado = enviar_aviso(pk)
        resultados[resultado] = resultados.get(resultado, 0) + 1
    return resultados
