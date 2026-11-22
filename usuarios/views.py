from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.deletion import ProtectedError, RestrictedError
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView

from auditoria.contexto import obter_ip

from .acesso import aceitou_versao_atual, destino_apos_login, destino_seguro
from .forms import (
    AceitePrimeiroAcessoForm,
    CadastroUsuarioForm,
    ConfirmacaoGestaoUsuarioForm,
    NovaVersaoTermosForm,
    TrocaSenhaTemporariaForm,
)
from .gestao import contas_academicas, possui_historico
from .mixins import CoordenacaoRequiredMixin
from .models import AceiteTermos, Usuario, VersaoTermos
from .termos import formatar, linhas, numero_vigente, versao_vigente


class LoginView(auth_views.LoginView):
    form_class = AuthenticationForm

    def get_success_url(self):
        return destino_apos_login(self.request)


class TrocarSenhaTemporariaView(LoginRequiredMixin, auth_views.PasswordChangeView):
    template_name = "usuarios/trocar_senha_temporaria.html"
    form_class = TrocaSenhaTemporariaForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.troca_senha_obrigatoria:
            return HttpResponseRedirect(destino_apos_login(request))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["next"] = destino_seguro(self.request)
        return contexto

    def form_valid(self, form):
        # A view nativa salva a senha e atualiza a sessão; o formulário limpa a pendência.
        with transaction.atomic():
            resposta = super().form_valid(form)
        messages.success(self.request, "Senha pessoal definida. A senha temporária deixou de funcionar.")
        return resposta

    def get_success_url(self):
        return destino_apos_login(self.request)


class PrimeiroAcessoView(LoginRequiredMixin, FormView):
    template_name = "usuarios/primeiro_acesso.html"
    form_class = AceitePrimeiroAcessoForm

    def get(self, request, *args, **kwargs):
        if aceitou_versao_atual(request.user):
            return HttpResponseRedirect(destino_seguro(request))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["next"] = destino_seguro(self.request)
        versao = versao_vigente()
        contexto["versao_atual"] = numero_vigente()
        # Quem já aceitou uma versão anterior vê o que mudou antes de aceitar de novo.
        if versao and AceiteTermos.objects.filter(usuario=self.request.user).exists():
            contexto["o_que_mudou"] = linhas(versao.o_que_mudou)
        return contexto

    def form_valid(self, form):
        AceiteTermos.objects.get_or_create(
            usuario=self.request.user,
            versao=form.cleaned_data["versao"],
            defaults={"ip_address": obter_ip(self.request)},
        )
        return HttpResponseRedirect(destino_seguro(self.request))


class UsuarioListView(CoordenacaoRequiredMixin, ListView):
    model = Usuario
    template_name = "usuarios/lista.html"
    context_object_name = "usuarios"
    paginate_by = 20

    def get_queryset(self):
        usuarios = contas_academicas().order_by("first_name", "last_name", "username")
        perfil = self.request.GET.get("perfil", "")
        if perfil in {"DOCENTE", "DISCENTE"}:
            usuarios = usuarios.filter(perfil=perfil)
        texto = self.request.GET.get("q", "").strip()
        if texto:
            usuarios = usuarios.filter(
                Q(username__icontains=texto)
                | Q(first_name__icontains=texto)
                | Q(last_name__icontains=texto)
                | Q(email__icontains=texto)
                | Q(rgm__icontains=texto)
            )
        return usuarios

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtros = self.request.GET.copy()
        filtros.pop("page", None)
        contexto.update(filtros=self.request.GET, filtros_url=filtros.urlencode())
        return contexto


class UsuarioCreateView(CoordenacaoRequiredMixin, CreateView):
    form_class = CadastroUsuarioForm
    template_name = "usuarios/form.html"
    success_url = reverse_lazy("usuarios_lista")

    def get_initial(self):
        initial = super().get_initial()
        perfil = self.request.GET.get("perfil")
        if perfil in {"DOCENTE", "DISCENTE"}:
            initial["perfil"] = perfil
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            resposta = super().form_valid(form)
        messages.success(
            self.request,
            "Usuário cadastrado. No primeiro acesso, a pessoa trocará a senha temporária "
            "e fará o próprio aceite dos termos.",
        )
        return resposta


class UsuarioAcaoView(CoordenacaoRequiredMixin, View):
    acoes = {"desativar": "Desativar usuário", "reativar": "Reativar usuário", "excluir": "Excluir usuário"}

    def _conta(self, pk, acao, bloquear=False):
        if acao not in self.acoes:
            raise Http404
        contas = contas_academicas()
        if bloquear:
            contas = contas.select_for_update()
        return get_object_or_404(contas, pk=pk)

    def _pagina(self, request, conta, acao, form):
        return render(
            request,
            "usuarios/confirmar_acao.html",
            {
                "conta": conta,
                "acao": acao,
                "titulo": self.acoes[acao],
                "form": form,
                "exclusao_bloqueada": acao == "excluir" and possui_historico(conta),
            },
        )

    def get(self, request, pk, acao):
        conta = self._conta(pk, acao)
        return self._pagina(request, conta, acao, ConfirmacaoGestaoUsuarioForm())

    def post(self, request, pk, acao):
        form = ConfirmacaoGestaoUsuarioForm(request.POST)
        with transaction.atomic():
            conta = self._conta(pk, acao, bloquear=True)
            if form.is_valid():
                if acao == "excluir":
                    if possui_historico(conta):
                        form.add_error(
                            None,
                            "Esta conta possui vínculos ou registros de uso. Desative-a para preservar o histórico.",
                        )
                    else:
                        try:
                            with transaction.atomic():
                                conta.delete()
                        except (ProtectedError, RestrictedError):
                            form.add_error(None, "A conta possui vínculos que impedem a exclusão. Use a desativação.")
                        else:
                            messages.success(
                                request, "Conta sem histórico excluída. Os registros de auditoria foram preservados."
                            )
                            return redirect("usuarios_lista")
                else:
                    conta.is_active = acao == "reativar"
                    conta.save(update_fields=["is_active"])
                    estado = "reativada" if conta.is_active else "desativada"
                    messages.success(request, f"Conta {estado}. Os vínculos e registros foram preservados.")
                    return redirect("usuarios_lista")
        return self._pagina(request, conta, acao, form)


class TermosDeUsoView(TemplateView):
    """Mostra a versão vigente; com um número na URL, a coordenação consulta uma versão anterior."""

    template_name = "usuarios/termos_de_uso.html"

    def get(self, request, *args, numero=None, **kwargs):
        if numero is None:
            self.versao = versao_vigente()
        elif request.user.is_authenticated and request.user.is_coordenacao:
            self.versao = get_object_or_404(VersaoTermos, numero=numero)
        else:
            raise Http404
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_layout"] = (
            "base.html"
            if (
                self.request.user.is_authenticated
                and not self.request.user.troca_senha_obrigatoria
                and aceitou_versao_atual(self.request.user)
            )
            else "base_publico.html"
        )
        context["versao"] = self.versao
        context["versao_atual"] = self.versao.numero if self.versao else numero_vigente()
        context["consulta_historico"] = self.kwargs.get("numero") is not None
        if context["consulta_historico"]:
            context["versao_vigente_numero"] = numero_vigente()
        if self.versao:
            context["resumo"] = linhas(self.versao.resumo)
            context["o_que_mudou"] = linhas(self.versao.o_que_mudou)
            context["documento"] = formatar(self.versao.texto)
        return context


class VersoesTermosView(CoordenacaoRequiredMixin, ListView):
    """Histórico das versões dos termos, com quantas contas aceitaram cada uma."""

    template_name = "usuarios/versoes_termos.html"
    context_object_name = "versoes"

    def get_queryset(self):
        aceites = (
            AceiteTermos.objects.filter(versao=OuterRef("numero"))
            .values("versao").annotate(total=Count("pk")).values("total")
        )
        return (
            VersaoTermos.objects.select_related("publicada_por")
            .annotate(total_aceites=Coalesce(Subquery(aceites), 0))
            .order_by("-pk")
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["contas_ativas"] = Usuario.objects.filter(is_active=True).count()
        return contexto


class NovaVersaoTermosView(CoordenacaoRequiredMixin, View):
    """
    Publica uma nova versão em dois passos: primeiro a pré-visualização, depois
    a confirmação. O formulário começa com o texto da versão vigente.
    """

    template_name = "usuarios/nova_versao_termos.html"

    def get(self, request):
        vigente = versao_vigente()
        inicial = {}
        if vigente:
            partes = vigente.numero.split(".")
            if all(parte.isdigit() for parte in partes):
                partes[-1] = str(int(partes[-1]) + 1)
            inicial = {"numero": ".".join(partes), "resumo": vigente.resumo, "texto": vigente.texto}
        return self._pagina(request, NovaVersaoTermosForm(initial=inicial))

    def post(self, request):
        publicar = request.POST.get("acao") == "publicar"
        form = NovaVersaoTermosForm(request.POST, publicar=publicar)
        if not form.is_valid():
            return self._pagina(request, form, previa=form.is_bound and "texto" in form.cleaned_data)
        if not publicar:
            return self._pagina(request, form, previa=True)
        with transaction.atomic():
            versao = form.save(commit=False)
            versao.publicada_por = request.user
            versao.save()
        messages.success(
            request, f"Versão {versao.numero} publicada. Cada usuário precisará aceitá-la no próximo acesso."
        )
        return redirect("versoes_termos")

    def _pagina(self, request, form, previa=False):
        contexto = {"form": form, "vigente": versao_vigente()}
        if previa:
            dados = form.cleaned_data
            contexto["previa"] = {
                "documento": formatar(dados.get("texto", "")),
                "resumo": linhas(dados.get("resumo", "")),
                "o_que_mudou": linhas(dados.get("o_que_mudou", "")),
            }
        return render(request, self.template_name, contexto)
