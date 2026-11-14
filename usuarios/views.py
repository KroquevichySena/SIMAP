from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, ListView, TemplateView

from auditoria.contexto import obter_ip

from .acesso import aceitou_versao_atual, destino_seguro, url_primeiro_acesso
from .forms import AceitePrimeiroAcessoForm, CadastroUsuarioForm
from .mixins import CoordenacaoRequiredMixin
from .models import AceiteTermos, Usuario


class LoginView(auth_views.LoginView):
    form_class = AuthenticationForm

    def get_success_url(self):
        destino = destino_seguro(self.request)
        if not aceitou_versao_atual(self.request.user):
            return url_primeiro_acesso(destino)
        return destino


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
        contexto["versao_atual"] = settings.TERMOS_DE_USO_VERSAO
        return contexto

    def form_valid(self, form):
        AceiteTermos.objects.get_or_create(
            usuario=self.request.user, versao=form.cleaned_data["versao"],
            defaults={"ip_address": obter_ip(self.request)},
        )
        return HttpResponseRedirect(destino_seguro(self.request))


class UsuarioListView(CoordenacaoRequiredMixin, ListView):
    model = Usuario
    template_name = "usuarios/lista.html"
    context_object_name = "usuarios"
    paginate_by = 20

    def get_queryset(self):
        usuarios = Usuario.objects.filter(
            perfil__in=["DOCENTE", "DISCENTE"], is_superuser=False, is_staff=False
        ).order_by("first_name", "last_name", "username")
        perfil = self.request.GET.get("perfil", "")
        if perfil in {"DOCENTE", "DISCENTE"}:
            usuarios = usuarios.filter(perfil=perfil)
        texto = self.request.GET.get("q", "").strip()
        if texto:
            usuarios = usuarios.filter(
                Q(username__icontains=texto) | Q(first_name__icontains=texto)
                | Q(last_name__icontains=texto) | Q(email__icontains=texto)
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
            self.request, "Usuário cadastrado. O aceite dos termos será feito pela própria pessoa no primeiro acesso."
        )
        return resposta


class TermosDeUsoView(TemplateView):
    template_name = "usuarios/termos_de_uso.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_layout"] = (
            "base.html"
            if self.request.user.is_authenticated and aceitou_versao_atual(self.request.user)
            else "base_publico.html"
        )
        context["versao_atual"] = settings.TERMOS_DE_USO_VERSAO
        return context
