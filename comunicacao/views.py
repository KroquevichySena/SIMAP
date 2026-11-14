from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from core.models import Atividade

from . import permissoes, servicos
from .arquivos import resposta_de_download
from .forms import PublicacaoForm, RespostaForm
from .models import Anexo, Notificacao, Publicacao, Resposta


def _com_anexos_e_respostas(queryset):
    return (
        queryset.select_related("autor", "destinatario", "atividade", "turma")
        .prefetch_related("anexos")
        .annotate(total_respostas=Count("respostas", distinct=True))
    )


def _turma_do_usuario_ou_404(usuario, turma_id):
    return get_object_or_404(permissoes.turmas_do_usuario(usuario), pk=turma_id)


class InicioView(LoginRequiredMixin, ListView):
    """Lista as turmas do usuário, que são a porta de entrada para cada mural."""

    template_name = "comunicacao/inicio.html"
    context_object_name = "turmas"

    def get_queryset(self):
        return permissoes.turmas_do_usuario(self.request.user).select_related("docente").order_by("nome")


class MuralView(LoginRequiredMixin, View):
    """Mural da turma: publicações para todos e as mensagens privadas da pessoa."""

    template_name = "comunicacao/mural.html"

    def _contexto(self, request, turma, form):
        filtro = request.GET.get("filtro", "")
        publicacoes = permissoes.publicacoes_visiveis(request.user, turma).filter(atividade__isnull=True)
        if filtro == "privadas":
            publicacoes = publicacoes.filter(destinatario__isnull=False)
        elif filtro == "mural":
            publicacoes = publicacoes.filter(destinatario__isnull=True)
        return {
            "turma": turma,
            "form": form,
            "filtro": filtro,
            "publicacoes": _com_anexos_e_respostas(publicacoes)[:100],
            "eh_docente": turma.docente_id == request.user.pk,
        }

    def get(self, request, turma_id):
        turma = _turma_do_usuario_ou_404(request.user, turma_id)
        form = PublicacaoForm(usuario=request.user, turma=turma)
        para = request.GET.get("para")
        if para and para.isdigit():
            form.initial["destinatario"] = int(para)
        return render(request, self.template_name, self._contexto(request, turma, form))

    def post(self, request, turma_id):
        turma = _turma_do_usuario_ou_404(request.user, turma_id)
        form = PublicacaoForm(request.POST, request.FILES, usuario=request.user, turma=turma)
        if not form.is_valid():
            messages.error(request, "A mensagem não foi publicada. Confira os erros abaixo.")
            return render(request, self.template_name, self._contexto(request, turma, form), status=200)

        destinatario = form.cleaned_data.get("destinatario")
        publicacao = servicos.publicar(
            request.user, turma, form.cleaned_data["texto"], form.anexos_validados, destinatario=destinatario
        )
        if destinatario:
            messages.success(request, "Mensagem privada enviada.")
        else:
            messages.success(request, "Publicado no mural da turma.")
        return redirect(publicacao)


class ComentariosAtividadeView(LoginRequiredMixin, View):
    template_name = "comunicacao/atividade.html"

    def _atividade(self, request, atividade_id):
        atividade = get_object_or_404(Atividade.objects.select_related("trilha__turma"), pk=atividade_id)
        if not permissoes.pode_ver_atividade(request.user, atividade):
            raise Http404
        return atividade

    def _contexto(self, request, atividade, form):
        comentarios = permissoes.publicacoes_visiveis(request.user, atividade.trilha.turma).filter(
            atividade=atividade
        )
        return {
            "atividade": atividade,
            "turma": atividade.trilha.turma,
            "form": form,
            "publicacoes": _com_anexos_e_respostas(comentarios)[:100],
        }

    def get(self, request, atividade_id):
        atividade = self._atividade(request, atividade_id)
        form = PublicacaoForm(usuario=request.user, turma=atividade.trilha.turma, permitir_privada=False)
        return render(request, self.template_name, self._contexto(request, atividade, form))

    def post(self, request, atividade_id):
        atividade = self._atividade(request, atividade_id)
        turma = atividade.trilha.turma
        form = PublicacaoForm(
            request.POST, request.FILES, usuario=request.user, turma=turma, permitir_privada=False
        )
        if not form.is_valid():
            messages.error(request, "O comentário não foi publicado. Confira os erros abaixo.")
            return render(request, self.template_name, self._contexto(request, atividade, form))
        publicacao = servicos.publicar(
            request.user, turma, form.cleaned_data["texto"], form.anexos_validados, atividade=atividade
        )
        messages.success(request, "Comentário publicado.")
        return redirect(publicacao)


class PublicacaoView(LoginRequiredMixin, View):
    """Uma publicação com todas as respostas, e o formulário para responder."""

    template_name = "comunicacao/publicacao.html"

    def _publicacao(self, request, pk):
        publicacao = get_object_or_404(
            Publicacao.objects.select_related("turma", "autor", "destinatario", "atividade__trilha__turma")
            .prefetch_related(
                "anexos",
                Prefetch("respostas", queryset=Resposta.objects.select_related("autor").prefetch_related("anexos")),
            ),
            pk=pk,
        )
        if not permissoes.pode_ver_publicacao(request.user, publicacao):
            raise Http404
        return publicacao

    def get(self, request, pk):
        publicacao = self._publicacao(request, pk)
        return render(request, self.template_name, {"publicacao": publicacao, "form": RespostaForm()})

    def post(self, request, pk):
        publicacao = self._publicacao(request, pk)
        form = RespostaForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "A resposta não foi enviada. Confira os erros abaixo.")
            return render(request, self.template_name, {"publicacao": publicacao, "form": form})
        resposta = servicos.responder(
            request.user, publicacao, form.cleaned_data["texto"], form.anexos_validados
        )
        messages.success(request, "Resposta enviada.")
        return HttpResponseRedirect(resposta.get_absolute_url())


class ApagarPublicacaoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        publicacao = get_object_or_404(Publicacao.objects.select_related("turma"), pk=pk)
        if not permissoes.pode_ver_publicacao(request.user, publicacao) or not permissoes.pode_apagar(
            request.user, publicacao
        ):
            raise Http404
        destino = (
            reverse("comunicacao:atividade", args=[publicacao.atividade_id])
            if publicacao.atividade_id
            else reverse("comunicacao:mural", args=[publicacao.turma_id])
        )
        publicacao.delete()
        messages.success(request, "Publicação apagada.")
        return redirect(destino)


class ApagarRespostaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        resposta = get_object_or_404(Resposta.objects.select_related("publicacao__turma"), pk=pk)
        publicacao = resposta.publicacao
        if not permissoes.pode_ver_publicacao(request.user, publicacao) or not permissoes.pode_apagar(
            request.user, resposta
        ):
            raise Http404
        resposta.delete()
        messages.success(request, "Resposta apagada.")
        return redirect(publicacao)


class BaixarAnexoView(LoginRequiredMixin, View):
    """
    Entrega o arquivo só para quem pode ver a mensagem.

    O tipo do conteúdo vem da nossa lista (nunca do que o navegador do autor
    mandou), o navegador é proibido de adivinhar outro tipo (nosniff) e a
    resposta vem com uma política que bloqueia scripts. Só imagens abrem na
    tela; todo o resto é sempre baixado.
    """

    def get(self, request, pk):
        anexo = get_object_or_404(
            Anexo.objects.select_related("publicacao__turma", "resposta__publicacao__turma"), pk=pk
        )
        if not permissoes.pode_ver_publicacao(request.user, anexo.publicacao_de_origem):
            raise Http404
        return resposta_de_download(anexo, mostrar_na_tela=request.GET.get("ver") == "1")


class NotificacoesView(LoginRequiredMixin, ListView):
    template_name = "comunicacao/notificacoes.html"
    context_object_name = "notificacoes"
    paginate_by = 30

    def get_queryset(self):
        return Notificacao.objects.filter(destinatario=self.request.user)


class AbrirNotificacaoView(LoginRequiredMixin, View):
    """Marca a notificação como lida e leva a pessoa até a mensagem."""

    def get(self, request, pk):
        notificacao = get_object_or_404(Notificacao, pk=pk, destinatario=request.user)
        if not notificacao.lida:
            notificacao.lida = True
            notificacao.save(update_fields=["lida"])
        destino = notificacao.url
        # Só caminhos internos do SIMAP: nada de redirecionar para outro site.
        if not destino.startswith("/") or destino.startswith("//") or not url_has_allowed_host_and_scheme(
            destino, allowed_hosts={request.get_host()}
        ):
            destino = reverse("comunicacao:notificacoes")
        return HttpResponseRedirect(destino)


class MarcarTodasLidasView(LoginRequiredMixin, View):
    def post(self, request):
        total = Notificacao.objects.filter(destinatario=request.user, lida=False).update(lida=True)
        messages.success(request, f"{total} notificação(ões) marcada(s) como lida(s).")
        return redirect("comunicacao:notificacoes")
