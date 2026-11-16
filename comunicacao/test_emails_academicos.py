"""RF33: publicação, autorização, transação, transições e falhas sem e-mail real."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Atividade, ConclusaoAtividade, TrilhaAprendizagem
from entregas.models import AnaliseIA, AvaliacaoOficial, Submissao
from turmas.models import Matricula, Turma
from usuarios.test_helpers import registrar_aceites_atuais

from .emails_academicos import enviar_aviso, processar_pendentes, verificar_atencao
from .models import EmailAcademico, EstadoAlertaAtencao


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SIMAP_PUBLIC_URL="https://simap.example"
)
class EmailsAcademicosTest(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.prof = Usuario.objects.create_user("prof", perfil="DOCENTE", email="prof@example.test")
        self.outro = Usuario.objects.create_user("outro", perfil="DOCENTE", email="outro@example.test")
        self.aluno = Usuario.objects.create_user("discente.demo", perfil="DISCENTE", email="aluno@example.test")
        registrar_aceites_atuais(Usuario.objects.all())
        self.turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.prof)
        self.matricula = Matricula.objects.create(turma=self.turma, discente=self.aluno)
        Matricula.objects.filter(pk=self.matricula.pk).update(data_matricula=timezone.now() - timedelta(days=2))
        self.trilha = TrilhaAprendizagem.objects.create(turma=self.turma, titulo="Introdução", publicada=True)
        self.atividade = Atividade.objects.create(
            trilha=self.trilha,
            titulo="Variáveis",
            enunciado="Explique.",
            publicada=True,
            prazo=timezone.now() - timedelta(hours=1),
        )
        self.submissao = Submissao.objects.create(
            atividade=self.atividade, aluno=self.aluno, resposta_texto="Resposta privada"
        )
        self.client.force_login(self.prof)
        self.url = reverse("entregas:avaliar", args=[self.submissao.pk])

    def avaliar(self, **dados):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {"nota": "8", "feedback_professor": "Texto privado do feedback", **dados})

    def criar_aviso(self):
        avaliacao = AvaliacaoOficial.objects.create(
            submissao=self.submissao,
            nota="8",
            feedback_professor="Feedback privado",
        )
        return avaliacao, EmailAcademico.objects.get(avaliacao=avaliacao)

    def test_feedback_publicado_envia_so_ao_aluno_apos_salvar_sem_expor_conteudo(self):
        self.assertEqual(self.avaliar().status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.aluno.email])
        self.assertIn("https://simap.example" + reverse("entregas:resolver", args=[self.atividade.pk]), email.body)
        for segredo in ("Texto privado do feedback", "Resposta privada", self.aluno.username, "8.0"):
            self.assertNotIn(segredo, email.body)
        self.assertEqual(EmailAcademico.objects.get().status, EmailAcademico.Status.ENVIADO)
        self.assertTrue(AvaliacaoOficial.objects.filter(submissao=self.submissao).exists())

    def test_salvar_sem_mudanca_nao_repete_mas_revisao_real_avisa(self):
        self.avaliar()
        self.avaliar()
        self.assertEqual(len(mail.outbox), 1)
        self.avaliar(feedback_professor="Feedback revisado")
        self.assertEqual(len(mail.outbox), 2)
        self.avaliar(nota="9", feedback_professor="Feedback revisado")
        self.assertEqual(len(mail.outbox), 3)

    def test_sinal_tambem_cobre_admin_e_normaliza_nota_textual(self):
        with self.captureOnCommitCallbacks(execute=True):
            avaliacao, _ = self.criar_aviso()
        with self.captureOnCommitCallbacks(execute=True):
            avaliacao.nota = "8.0"
            avaliacao.save()
        self.assertEqual(len(mail.outbox), 1)

    def test_parecer_da_ia_nao_publica_avaliacao_nem_envia_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            AnaliseIA.objects.create(submissao=self.submissao, parecer_texto="Consultivo", status="CONCLUIDO")
        self.assertFalse(EmailAcademico.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_nota_invalida_outro_docente_discente_nao_geram_email(self):
        self.avaliar(nota="11")
        self.assertFalse(EmailAcademico.objects.exists())
        for usuario, codigo in ((self.outro, 404), (self.aluno, 403)):
            self.client.force_login(usuario)
            self.assertEqual(self.avaliar().status_code, codigo)
        self.assertFalse(EmailAcademico.objects.exists())
        self.assertFalse(AvaliacaoOficial.objects.exists())

    def test_rollback_nao_envia_nem_deixa_aviso(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.criar_aviso()
                    raise RuntimeError("Desfaz a publicação")
        self.assertFalse(AvaliacaoOficial.objects.exists())
        self.assertFalse(EmailAcademico.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    @patch("comunicacao.emails_academicos.send_mail", side_effect=RuntimeError("provedor indisponível"))
    def test_falha_preserva_nota_e_permite_reenvio_sem_duplicar(self, enviar):
        with self.assertLogs("simap.integracoes", level="ERROR"):
            self.avaliar()
        aviso = EmailAcademico.objects.get()
        self.assertEqual(aviso.status, EmailAcademico.Status.PENDENTE)
        self.assertEqual(AvaliacaoOficial.objects.get().nota, 8)
        enviar.side_effect = None
        enviar.return_value = 1
        self.assertEqual(processar_pendentes(), {"enviado": 1})
        self.assertEqual(processar_pendentes(), {})
        aviso.refresh_from_db()
        self.assertEqual(aviso.tentativas, 2)

    @patch("entregas.sinais.registrar_feedback", side_effect=RuntimeError("falha no registro"))
    def test_falha_no_registro_do_aviso_nao_perde_avaliacao(self, registrar):
        with self.assertLogs("simap.integracoes", level="ERROR"):
            self.avaliar()
        self.assertTrue(AvaliacaoOficial.objects.exists())

    def test_nova_revisao_cancela_aviso_pendente_antigo(self):
        avaliacao, antigo = self.criar_aviso()
        with self.captureOnCommitCallbacks(execute=True):
            avaliacao.feedback_professor = "Revisado"
            avaliacao.save()
        antigo.refresh_from_db()
        self.assertEqual(antigo.status, EmailAcademico.Status.CANCELADO)
        self.assertEqual(processar_pendentes(), {})
        self.assertEqual(len(mail.outbox), 1)

    def test_antes_de_reenviar_confere_matricula_e_conta_ativa(self):
        _, aviso = self.criar_aviso()
        self.matricula.status = "INATIVA"
        self.matricula.save()
        self.assertEqual(enviar_aviso(aviso.pk), "cancelado")
        self.assertEqual(len(mail.outbox), 0)

    def test_feedback_oculto_aguarda_publicacao_da_trilha(self):
        _, aviso = self.criar_aviso()
        self.trilha.publicada = False
        self.trilha.save()
        self.assertEqual(enviar_aviso(aviso.pk), "aguardando_publicacao")
        self.assertEqual(len(mail.outbox), 0)
        self.trilha.publicada = True
        self.trilha.save()
        self.assertEqual(enviar_aviso(aviso.pk), "enviado")

    def test_sem_email_fica_pendente_e_tenta_apos_corrigir_cadastro(self):
        _, aviso = self.criar_aviso()
        self.aluno.email = ""
        self.aluno.save()
        self.assertEqual(enviar_aviso(aviso.pk), "sem_email")
        self.aluno.email = "novo@example.test"
        self.aluno.save()
        self.assertEqual(enviar_aviso(aviso.pk), "enviado")
        self.assertEqual(mail.outbox[0].to, ["novo@example.test"])

    def test_reserva_impede_envio_simultaneo_e_recupera_reserva_antiga(self):
        _, aviso = self.criar_aviso()
        with patch("comunicacao.emails_academicos.send_mail") as enviar:

            def confirmar(*args, **kwargs):
                self.assertEqual(enviar_aviso(aviso.pk), "ignorado")
                return 1

            enviar.side_effect = confirmar
            self.assertEqual(enviar_aviso(aviso.pk), "enviado")
            enviar.assert_called_once()
        EmailAcademico.objects.filter(pk=aviso.pk).update(
            status=EmailAcademico.Status.ENVIANDO,
            reservado_em=timezone.now() - timedelta(minutes=11),
        )
        self.assertEqual(enviar_aviso(aviso.pk), "enviado")

    def test_backend_que_retorna_zero_nao_marca_como_enviado(self):
        _, aviso = self.criar_aviso()
        with (
            patch("comunicacao.emails_academicos.send_mail", return_value=0),
            self.assertLogs(
                "simap.integracoes",
                level="ERROR",
            ),
        ):
            self.assertEqual(enviar_aviso(aviso.pk), "falha")
        aviso.refresh_from_db()
        self.assertEqual(aviso.status, EmailAcademico.Status.PENDENTE)

    def test_atencao_usa_mesmo_limite_e_nao_repete_enquanto_situacao_persistir(self):
        # A entrega existe, mas o progresso é zero por não ter concluído a atividade.
        self.assertEqual(verificar_atencao(), 1)
        self.assertEqual(processar_pendentes(), {"enviado": 1})
        self.assertEqual(mail.outbox[0].to, [self.prof.email])
        self.assertIn("atenção", mail.outbox[0].subject)
        self.assertNotIn(self.aluno.username, mail.outbox[0].body)
        self.assertEqual(verificar_atencao(), 0)
        self.assertEqual(processar_pendentes(), {})
        self.assertEqual(len(mail.outbox), 1)

    def test_recuperacao_e_nova_queda_geram_outro_episodio(self):
        verificar_atencao()
        processar_pendentes()
        conclusao = ConclusaoAtividade.objects.create(atividade=self.atividade, discente=self.aluno)
        self.assertEqual(verificar_atencao(), 0)
        self.assertFalse(EstadoAlertaAtencao.objects.get().em_atencao)
        conclusao.delete()
        self.assertEqual(verificar_atencao(), 1)
        processar_pendentes()
        self.assertEqual(len(mail.outbox), 2)

    def test_sem_indicadores_ou_limite_zero_nao_gera_alerta(self):
        self.atividade.prazo = timezone.now() + timedelta(days=1)
        self.atividade.save()
        self.assertEqual(verificar_atencao(), 0)
        self.atividade.prazo = timezone.now() - timedelta(hours=1)
        self.atividade.save()
        self.turma.limite_atencao = 0
        self.turma.save()
        self.assertEqual(verificar_atencao(), 0)

    def test_mudanca_no_limite_e_no_docente_respeitada(self):
        self.turma.limite_atencao = 0
        self.turma.save()
        verificar_atencao()
        self.turma.limite_atencao = 60
        self.turma.save()
        self.assertEqual(verificar_atencao(), 1)
        processar_pendentes()
        self.turma.docente = self.outro
        self.turma.save()
        self.assertEqual(verificar_atencao(), 1)
        processar_pendentes()
        self.assertEqual(mail.outbox[-1].to, [self.outro.email])

    def test_reenvio_descarta_atencao_que_nao_existe_mais(self):
        verificar_atencao()
        ConclusaoAtividade.objects.create(atividade=self.atividade, discente=self.aluno)
        self.assertEqual(processar_pendentes(), {"cancelado": 1})

    def test_ignora_contas_matriculas_e_turmas_inativas(self):
        self.matricula.status = "INATIVA"
        self.matricula.save()
        self.assertEqual(verificar_atencao(), 0)
        self.matricula.status = "ATIVA"
        self.matricula.save()
        self.aluno.is_active = False
        self.aluno.save()
        self.assertEqual(verificar_atencao(), 0)
        self.aluno.is_active = True
        self.aluno.save()
        self.turma.ativa = False
        self.turma.save()
        self.assertEqual(verificar_atencao(), 0)

    def test_comando_cria_alertas_e_processa_pendentes_com_limite(self):
        self.criar_aviso()
        call_command("notificar_acompanhamento", limite=1, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        call_command("notificar_acompanhamento", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 2)
        call_command("notificar_acompanhamento", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 2)
        with self.assertRaises(CommandError):
            call_command("notificar_acompanhamento", limite=0, stdout=StringIO())

    @override_settings(SIMAP_PUBLIC_URL="")
    def test_sem_endereco_publico_orienta_entrar_no_sistema_sem_inventar_host(self):
        self.avaliar()
        self.assertIn("Entre no SIMAP", mail.outbox[0].body)
        self.assertNotIn("http", mail.outbox[0].body)

    def test_modo_periodico_verifica_sem_depender_de_acessar_pagina(self):
        saida = StringIO()
        with patch(
            "comunicacao.management.commands.notificar_acompanhamento.time.sleep", side_effect=KeyboardInterrupt
        ):
            call_command("notificar_acompanhamento", intervalo=60, stdout=saida)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("interrompido", saida.getvalue())
        with self.assertRaises(CommandError):
            call_command("notificar_acompanhamento", intervalo=-1, stdout=StringIO())
