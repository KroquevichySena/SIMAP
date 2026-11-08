"""
Reconhece links de vídeo do YouTube e devolve só o código do vídeo.

O SIMAP nunca guarda nem mostra o link do jeito que foi colado: guardamos o
código de 11 caracteres e montamos nós mesmos o endereço do player. Assim um
link parecido ("youtube.com.site-falso.com", "javascript:...") não passa, e o
player usa o domínio youtube-nocookie.com, que não grava cookies de rastreio
enquanto o aluno não der play.
"""
import re
from urllib.parse import parse_qs, urlsplit

_CODIGO = re.compile(r"^[A-Za-z0-9_-]{11}$")
_DOMINIOS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}
_PREFIXOS = ("/shorts/", "/embed/", "/live/", "/v/")
_LINK_NO_TEXTO = re.compile(r"https?://[^\s<>\"']+")


def codigo_do_video(url):
    """Devolve o código do vídeo, ou None se o link não for do YouTube."""
    if not url:
        return None
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return None
    if partes.scheme not in ("http", "https") or partes.username or partes.password or partes.port:
        return None
    host = (partes.hostname or "").lower()
    caminho = partes.path

    if host == "youtu.be":
        codigo = caminho.strip("/").split("/")[0]
    elif host in _DOMINIOS:
        if caminho in ("/watch", "/watch/"):
            codigo = (parse_qs(partes.query).get("v") or [""])[0]
        else:
            prefixo = next((p for p in _PREFIXOS if caminho.startswith(p)), None)
            if prefixo is None:
                return None
            codigo = caminho[len(prefixo):].split("/")[0]
    else:
        return None
    return codigo if _CODIGO.match(codigo) else None


def codigos_no_texto(texto, limite=3):
    """Códigos dos vídeos do YouTube citados num texto, sem repetir, na ordem."""
    encontrados = []
    for link in _LINK_NO_TEXTO.findall(texto or ""):
        codigo = codigo_do_video(link.rstrip(".,;:!?)"))
        if codigo and codigo not in encontrados:
            encontrados.append(codigo)
            if len(encontrados) == limite:
                break
    return encontrados


def endereco_do_player(codigo):
    return f"https://www.youtube-nocookie.com/embed/{codigo}"


def endereco_para_assistir(codigo):
    return f"https://www.youtube.com/watch?v={codigo}"
