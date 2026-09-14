"""
Controle de acesso por perfil (RBAC) — camada 1 de segurança.
A camada 2 (posse do objeto) está no get_queryset() de cada view.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class PerfilRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Base compartilhada: garante login primeiro, depois o perfil certo."""

    def handle_no_permission(self):
        # Se não estiver logado, segue o fluxo padrão (redireciona para o login).
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        # Se estiver logado mas com o perfil errado, nega o acesso (403).
        raise PermissionDenied("Você não tem permissão para acessar esta funcionalidade.")


class DocenteRequiredMixin(PerfilRequiredMixin):
    """Restringe a view a usuários autenticados com perfil DOCENTE."""

    def test_func(self):
        return self.request.user.is_docente


class DiscenteRequiredMixin(PerfilRequiredMixin):
    """Restringe a view a usuários autenticados com perfil DISCENTE."""

    def test_func(self):
        return self.request.user.is_discente
