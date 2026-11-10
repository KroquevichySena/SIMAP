import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.mail import send_mass_mail
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, View

from comunicacao.arquivos import resposta_de_download, salvar_arquivos, validar_arquivos
from comunicacao.forms import ACEITAR

from core.mixins import DiscenteRequiredMixin, DocenteRequiredMixin
from core.models import Atividade
from turmas.models import Matricula

from .ia_services import gerar_analise
from .models import AnexoSubmissao, AvaliacaoOficial, RascunhoCodigo, Submissao

logger = logging.getLogger("simap.integracoes")


class CorrigirAtividadeView(DocenteRequiredMixin, DetailView):
    """Tela de correção: entregas de uma atividade + lista de pendentes."""

    model = Atividade
    template_name = "entregas/docente/corrigir.html"
    context_object_name = "atividade"

    def get_queryset(self):
        # ANTI-IDOR: mesmo padrão de AtividadeUpdateView — só atividades do próprio docente
        return Atividade.objects.filter(
            trilha__turma__docente=self.request.user
        ).select_related("trilha", "trilha__turma")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        atividade = self.object

        submissoes = (
            Submissao.objects.filter(atividade=atividade)
            .select_related("aluno", "analise_ia", "avaliacao_oficial")
            .prefetch_related("anexos")
            .order_by("-data_envio")
        )
        ctx["submissoes"] = submissoes
        ctx["casos"] = list(atividade.casos_de_teste.all())

        ids_ja_enviaram = submissoes.values_list("aluno_id", flat=True)
        ctx["pendentes"] = (
            Matricula.objects.filter(turma=atividade.trilha.turma, status="ATIVA")
            .exclude(discente_id__in=ids_ja_enviaram)
            .select_related("discente")
        )
        return ctx


class GravarNotaView(DocenteRequiredMixin, View):
    """Cria ou atualiza a nota/feedback do docente para uma submissão."""

    def post(self, request, pk, *args, **kwargs):
        submissao = get_object_or_404(
            Submissao.objects.filter(atividade__trilha__turma__docente=request.user),
            pk=pk,
        )
        try:
            nota = Decimal(request.POST.get("nota", ""))
            if not (0 <= nota <= 10):
                raise InvalidOperation
        except InvalidOperation:
            messages.error(request, "Nota inválida. Use um valor entre 0 e 10.")
            return redirect("entregas:corrigir", pk=submissao.atividade_id)

        AvaliacaoOficial.objects.update_or_create(
            submissao=submissao,
            defaults={
                "nota": nota,
                "feedback_professor": request.POST.get("feedback_professor", ""),
            },
        )
        messages.success(request, "Nota registrada com sucesso.")
        return redirect("entregas:corrigir", pk=submissao.atividade_id)


class RetentarAnaliseView(DocenteRequiredMixin, View):
    """Reprocessa a análise de IA de uma submissão (botão 'Tentar Novamente')."""

    def post(self, request, pk, *args, **kwargs):
        submissao = get_object_or_404(
            Submissao.objects.filter(atividade__trilha__turma__docente=request.user),
            pk=pk,
        )
        gerar_analise(submissao)
        return redirect("entregas:corrigir", pk=submissao.atividade_id)


class NotificarPendentesView(DocenteRequiredMixin, View):
    """Envia e-mail em massa para os alunos que ainda não entregaram a atividade."""

    def post(self, request, pk, *args, **kwargs):
        atividade = get_object_or_404(
            Atividade.objects.filter(trilha__turma__docente=request.user), pk=pk
        )
        mensagem = request.POST.get("mensagem", "").strip()
        if not mensagem:
            messages.error(request, "Escreva uma mensagem antes de enviar.")
            return redirect("entregas:corrigir", pk=atividade.pk)

        ids_ja_enviaram = Submissao.objects.filter(atividade=atividade).values_list(
            "aluno_id", flat=True
        )
        pendentes = Matricula.objects.filter(
            turma=atividade.trilha.turma, status="ATIVA"
        ).exclude(discente_id__in=ids_ja_enviaram).select_related("discente")

        destinatarios = [m.discente.email for m in pendentes if m.discente.email]
        assunto = f"Pendência: {atividade.titulo}"
        mensagens = tuple(
            (assunto, mensagem, settings.DEFAULT_FROM_EMAIL, [email])
            for email in destinatarios
        )
        if mensagens:
            # Se o Mailgun estiver fora do ar, a falha vai para o log e o
            # docente recebe um aviso, em vez de uma tela de erro 500.
            try:
                send_mass_mail(mensagens, fail_silently=False)
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao enviar aviso de pendência da atividade %s", atividade.pk)
                messages.error(
                    request,
                    "Não foi possível enviar os e-mails agora. Tente novamente em alguns minutos.",
                )
                return redirect("entregas:corrigir", pk=atividade.pk)
        messages.success(request, f"Notificação enviada para {len(destinatarios)} aluno(s).")
        return redirect("entregas:corrigir", pk=atividade.pk)



def atividades_do_aluno(aluno):
    """Atividades que o aluno pode ver e responder: publicadas e da turma dele."""
    return Atividade.objects.filter(
        publicada=True,
        trilha__publicada=True,
        trilha__turma__ativa=True,
        trilha__turma__matricula__discente=aluno,
        trilha__turma__matricula__status="ATIVA",
    )


class SubmeterAtividadeView(DiscenteRequiredMixin, View):
    """Recebe a resposta do aluno e dispara a análise de IA."""

    def post(self, request, pk, *args, **kwargs):
        atividade = get_object_or_404(atividades_do_aluno(request.user), pk=pk)

        resposta_texto = request.POST.get("resposta_texto", "").strip()
        if not resposta_texto:
            messages.error(request, "Escreva uma resposta antes de enviar.")
            return redirect(self._voltar(atividade))

        # Os arquivos passam pela mesma checagem dos anexos da comunicação.
        # Se um deles for barrado, nada é gravado e o aluno vê o motivo.
        try:
            anexos = validar_arquivos(request.FILES.getlist("anexos"))
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
            return redirect(self._voltar(atividade))

        if Submissao.objects.filter(atividade=atividade, aluno=request.user).exists():
            messages.info(request, "Você já enviou uma resposta para esta atividade.")
            return redirect(self._voltar(atividade))

        try:
            with transaction.atomic():
                submissao = Submissao.objects.create(
                    atividade=atividade, aluno=request.user, resposta_texto=resposta_texto
                )
                salvar_arquivos(AnexoSubmissao, anexos, submissao=submissao)
                # O rascunho do editor já virou a entrega; não precisa mais dele.
                RascunhoCodigo.objects.filter(atividade=atividade, aluno=request.user).delete()
        except IntegrityError:
            # Dois cliques seguidos em "Submeter": a segunda tentativa cai aqui.
            messages.info(request, "Você já enviou uma resposta para esta atividade.")
            return redirect(self._voltar(atividade))

        # A análise de IA continua usando só o texto da resposta.
        gerar_analise(submissao)
        messages.success(request, "Resposta enviada e analisada.")
        return redirect(self._voltar(atividade))

    @staticmethod
    def _voltar(atividade):
        return "core:minhas_trilhas"


class ResolverAtividadeView(DiscenteRequiredMixin, View):
    """
    Tela do editor de código de uma atividade prática.

    O código abre com, nesta ordem: a resposta já entregue (só leitura), o
    rascunho salvo ou o código inicial que o professor deixou.
    """

    template_name = "entregas/discente/resolver.html"

    def get(self, request, pk):
        atividade = get_object_or_404(
            atividades_do_aluno(request.user).select_related("trilha__turma"), pk=pk, tipo="PRATICA"
        )
        submissao = (
            Submissao.objects.filter(atividade=atividade, aluno=request.user)
            .select_related("avaliacao_oficial").prefetch_related("anexos").first()
        )
        rascunho = None
        if submissao:
            codigo = submissao.resposta_texto
        else:
            rascunho = RascunhoCodigo.objects.filter(atividade=atividade, aluno=request.user).first()
            codigo = rascunho.codigo if rascunho else atividade.codigo_inicial
        return render(request, self.template_name, {
            "atividade": atividade,
            "submissao": submissao,
            "rascunho": rascunho,
            "codigo": codigo,
            "casos": list(atividade.casos_de_teste.all()),
            "extensoes_aceitas": ACEITAR,
            "url_rascunho": "" if submissao else reverse("entregas:salvar_rascunho", args=[atividade.pk]),
        })


class SalvarRascunhoView(DiscenteRequiredMixin, View):
    """Guarda o código do editor enquanto o aluno ainda não entregou (chamado pelo JavaScript)."""

    def post(self, request, pk):
        atividade = get_object_or_404(atividades_do_aluno(request.user), pk=pk, tipo="PRATICA")
        codigo = request.POST.get("codigo", "")
        if len(codigo) > settings.EDITOR_TAMANHO_MAXIMO_CODIGO:
            return JsonResponse({"erro": "O código passou do tamanho máximo."}, status=400)
        if Submissao.objects.filter(atividade=atividade, aluno=request.user).exists():
            return JsonResponse({"erro": "Esta atividade já foi entregue."}, status=409)
        RascunhoCodigo.objects.update_or_create(
            atividade=atividade, aluno=request.user, defaults={"codigo": codigo}
        )
        return JsonResponse({"salvo_em": timezone.localtime().strftime("%H:%M")})


class BaixarAnexoSubmissaoView(LoginRequiredMixin, View):
    """O arquivo da entrega só sai para o aluno que enviou e para o professor da turma."""

    def get(self, request, pk):
        anexo = get_object_or_404(
            AnexoSubmissao.objects.select_related("submissao__atividade__trilha__turma"), pk=pk
        )
        submissao = anexo.submissao
        docente_id = submissao.atividade.trilha.turma.docente_id
        if request.user.pk not in (submissao.aluno_id, docente_id):
            raise Http404
        return resposta_de_download(anexo, mostrar_na_tela=request.GET.get("ver") == "1")
