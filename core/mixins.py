"""
Mixins de controle de acesso (RBAC) para as views do core.

Cada mixin garante duas coisas, nessa ordem:
  1) LoginRequiredMixin -> usuário precisa estar autenticado
  2) UserPassesTestMixin -> usuário precisa ter o perfil correto
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class DocenteRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a view a usuários autenticados com perfil DOCENTE."""

    def test_func(self):
        return self.request.user.is_docente

    def handle_no_permission(self):
        # Se não estiver logado, segue o fluxo padrão (redireciona para o login).
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        # Se estiver logado mas com o perfil errado, nega o acesso (403).
        raise PermissionDenied("Apenas docentes podem acessar esta área.")


class DiscenteRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a view a usuários autenticados com perfil DISCENTE."""

    def test_func(self):
        return self.request.user.is_discente

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Apenas discentes podem acessar esta área.")
