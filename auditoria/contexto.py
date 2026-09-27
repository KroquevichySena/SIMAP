"""
Aqui guardamos quem está fazendo a requisição no momento.

O problema que isso resolve: quando alguém salva uma atividade, o Django
avisa a auditoria pelo sinal post_save, mas esse sinal não sabe qual usuário
estava logado. O middleware anota os dados da requisição aqui, e os sinais
leem daqui.

Usamos contextvars em vez de threading.local porque ele funciona tanto no
modo síncrono quanto no assíncrono e não mistura dados de requisições
diferentes que passem pela mesma thread.
"""
import ipaddress
from contextvars import ContextVar
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class ContextoRequisicao:
    usuario: object = None
    ip: str | None = None
    user_agent: str = ""
    metodo: str = ""
    caminho: str = ""


_contexto_atual: ContextVar[ContextoRequisicao | None] = ContextVar(
    "auditoria_contexto", default=None
)


def definir(contexto):
    return _contexto_atual.set(contexto)


def restaurar(token):
    _contexto_atual.reset(token)


def atual() -> ContextoRequisicao | None:
    return _contexto_atual.get()


def _ip_valido(valor):
    try:
        return str(ipaddress.ip_address(valor.strip()))
    except (ValueError, AttributeError):
        return None


def obter_ip(request):
    """
    Descobre o IP de quem fez a requisição.

    O cuidado aqui é com o cabeçalho X-Forwarded-For: qualquer pessoa pode
    mandá-lo com um IP inventado. Por isso, por padrão só confiamos no
    REMOTE_ADDR, que vem da própria conexão.

    Em produção no Render existe um proxy na frente do Django, e aí o
    REMOTE_ADDR passa a ser o IP do proxy. Nesse caso configuramos
    AUDITORIA_PROXIES_CONFIAVEIS=1 e pegamos o IP que o proxy anexou no FIM
    da lista. O que está à esquerda pode ter sido escrito pelo próprio
    cliente, então ignoramos.
    """
    proxies = getattr(settings, "AUDITORIA_PROXIES_CONFIAVEIS", 0)
    if proxies > 0:
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
        cadeia = [ip for ip in encaminhado.split(",") if ip.strip()]
        if len(cadeia) >= proxies:
            ip = _ip_valido(cadeia[-proxies])
            if ip:
                return ip
    return _ip_valido(request.META.get("REMOTE_ADDR", ""))


def a_partir_do_request(request):
    usuario = getattr(request, "user", None)
    if usuario is not None and not usuario.is_authenticated:
        usuario = None
    return ContextoRequisicao(
        usuario=usuario,
        ip=obter_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        metodo=request.method or "",
        caminho=request.path[:255],
    )
