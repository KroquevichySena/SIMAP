"""
Controle de acesso por perfil (RBAC) — camada 1 de segurança.
A camada 2 (posse do objeto) está no get_queryset() de cada view.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class PerfilRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True  # 403 direto, sem redirect explorável

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Você não tem permissão para acessar esta funcionalidade.")


class DocenteRequiredMixin(PerfilRequiredMixin):
    def test_func(self):
        return self.request.user.is_docente


class DiscenteRequiredMixin(PerfilRequiredMixin):
    def test_func(self):
        return self.request.user.is_discente
