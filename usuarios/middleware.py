from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from .acesso import aceitou_versao_atual, destino_seguro, url_primeiro_acesso, url_troca_senha


class AceiteTermosMiddleware(MiddlewareMixin):
    """Exige senha pessoal antes do aceite e do acesso às páginas e operações."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        rota = request.resolver_match
        caminho = request.get_full_path() if request.method in {"GET", "HEAD"} else ""
        if request.user.troca_senha_obrigatoria:
            permitidas_senha = {
                "trocar_senha_temporaria", "termos_de_uso", "login", "logout",
                "password_reset", "password_reset_done", "password_reset_confirm", "password_reset_complete",
            }
            if not rota or rota.url_name not in permitidas_senha:
                return HttpResponseRedirect(url_troca_senha(destino_seguro(request, caminho)))
            return None
        permitidas = {
            "primeiro_acesso", "trocar_senha_temporaria", "termos_de_uso", "login", "logout", "password_reset",
            "password_reset_done", "password_reset_confirm", "password_reset_complete",
        }
        if rota and rota.url_name in permitidas:
            return None
        if aceitou_versao_atual(request.user):
            return None
        # Não reexecuta um POST depois do aceite: o usuário retoma pelo painel.
        return HttpResponseRedirect(url_primeiro_acesso(destino_seguro(request, caminho)))
