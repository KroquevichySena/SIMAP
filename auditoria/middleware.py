"""
O middleware passa por todas as requisições e faz três coisas:

1. Anota quem está fazendo a requisição, para que os sinais saibam quem
   criou, alterou ou excluiu cada coisa.
2. Registra as páginas que usuários logados acessam.
3. Registra todo acesso negado (403), inclusive de quem não está logado.
   Tentativas de entrar onde não pode são justamente o que mais interessa
   numa auditoria de segurança.

Ele precisa vir depois do AuthenticationMiddleware no settings, senão
ainda não sabe quem é o usuário.
"""
from django.conf import settings

from . import contexto
from .models import Acao
from .servicos import registrar

METODOS_DE_LEITURA = {"GET", "HEAD"}


def _prefixos_ignorados():
    # CSS, imagens e afins não dizem nada sobre o que o usuário fez,
    # então nem entram na auditoria.
    prefixos = ["/favicon.ico", "/admin/jsi18n/"]
    static_url = getattr(settings, "STATIC_URL", None)
    if static_url:
        prefixos.append("/" + static_url.lstrip("/"))
    prefixos.extend(getattr(settings, "AUDITORIA_CAMINHOS_IGNORADOS", []))
    return tuple(prefixos)


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixos_ignorados = _prefixos_ignorados()

    def __call__(self, request):
        if request.path.startswith(self.prefixos_ignorados):
            return self.get_response(request)

        token = contexto.definir(contexto.a_partir_do_request(request))
        try:
            response = self.get_response(request)
            self._registrar_acesso(request, response)
            return response
        finally:
            # Limpa o contexto no fim, para não sobrar nada para a próxima requisição.
            contexto.restaurar(token)

    def _registrar_acesso(self, request, response):
        status = response.status_code
        # Olhamos o usuário de novo porque ele pode ter acabado de fazer login.
        usuario = getattr(request, "user", None)
        autenticado = usuario is not None and usuario.is_authenticated
        ctx = contexto.a_partir_do_request(request)

        if status == 403:
            registrar(
                Acao.ACESSO_NEGADO,
                ctx=ctx,
                status_http=status,
                descricao=f"Acesso negado a {request.path[:200]}",
            )
        elif autenticado and request.method in METODOS_DE_LEITURA and status < 400:
            # Só leituras. Os envios de formulário já aparecem como
            # criação, alteração ou exclusão, com mais detalhes.
            registrar(Acao.ACESSO, ctx=ctx, status_http=status,
                      descricao=f"Acessou {request.path[:200]}")
