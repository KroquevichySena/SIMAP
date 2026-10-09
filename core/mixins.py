"""
Quem pode entrar em cada tela, de acordo com o perfil (docente ou discente).

Essa é a primeira barreira. A segunda fica no get_queryset() de cada view,
que confere se o objeto aberto pertence mesmo a quem está pedindo.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class PerfilRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Primeiro confere se a pessoa está logada, depois se tem o perfil certo."""

    def handle_no_permission(self):
        # Quem não está logado vai para a tela de login.
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        # Quem está logado mas com o perfil errado recebe acesso negado (403).
        raise PermissionDenied("Você não tem permissão para acessar esta funcionalidade.")


class DocenteRequiredMixin(PerfilRequiredMixin):
    """Tela exclusiva de docentes."""

    def test_func(self):
        return self.request.user.is_docente


class DiscenteRequiredMixin(PerfilRequiredMixin):
    """Tela exclusiva de alunos."""

    def test_func(self):
        return self.request.user.is_discente
