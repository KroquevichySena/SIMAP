from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from .acesso import aceitou_versao_atual, destino_seguro, url_primeiro_acesso


class AceiteTermosMiddleware(MiddlewareMixin):
    """Bloqueia páginas e operações até o próprio usuário aceitar a versão atual."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        rota = request.resolver_match
        permitidas = {
            "primeiro_acesso", "termos_de_uso", "login", "logout", "password_reset",
            "password_reset_done", "password_reset_confirm", "password_reset_complete",
        }
        if rota and rota.url_name in permitidas:
            return None
        if aceitou_versao_atual(request.user):
            return None
        # Não reexecuta um POST depois do aceite: o usuário retoma pelo painel.
        caminho = request.get_full_path() if request.method in {"GET", "HEAD"} else ""
        return HttpResponseRedirect(url_primeiro_acesso(destino_seguro(request, caminho)))
