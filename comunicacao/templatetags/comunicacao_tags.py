"""
Mostra o texto das mensagens com os links clicáveis, sem abrir brecha.

O texto do usuário nunca é tratado como HTML: tudo é escapado primeiro, e só
depois os endereços que passam na checagem viram <a>. Um link só é aceito se:
- começar com http:// ou https:// (javascript:, data:, file: e afins ficam
  como texto comum, sem clique);
- não tiver usuário e senha embutidos, o truque de
  "https://banco.com@site-falso.com", que parece um endereço e leva a outro;
- for um endereço válido para o validador de URL do Django.

O link abre em outra aba, sem dar à página de destino acesso ao SIMAP
(noopener), sem contar de onde a pessoa veio (noreferrer) e sem repassar
reputação de busca (nofollow). O endereço completo fica visível no texto, e o
domínio aparece ao lado, para ninguém clicar num link sem saber para onde vai.
"""
import re
from urllib.parse import urlsplit

from django import template
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

_PADRAO_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
# Pontuação que costuma colar no fim do link na escrita ("veja https://x.com.")
_PONTUACAO_FINAL = ".,;:!?)]}"
_validar_url = URLValidator(schemes=["http", "https"])
TAMANHO_MAXIMO_URL = 2000


def link_seguro(url):
    """Devolve True se o endereço pode virar link clicável."""
    if len(url) > TAMANHO_MAXIMO_URL:
        return False
    try:
        _validar_url(url)
        partes = urlsplit(url)
    except (ValidationError, ValueError):
        return False
    if partes.username or partes.password or "@" in partes.netloc:
        return False
    return partes.scheme.lower() in ("http", "https") and bool(partes.hostname)


def _montar_link(url):
    dominio = urlsplit(url).hostname
    return format_html(
        '<a href="{}" target="_blank" rel="noopener noreferrer nofollow">{}</a>'
        ' <small class="text-muted">({})</small>',
        url, url, dominio,
    )


@register.filter(name="texto_com_links")
def texto_com_links(texto):
    texto = str(texto or "")
    partes = []
    posicao = 0
    for achado in _PADRAO_URL.finditer(texto):
        url = achado.group(0)
        sobra = ""
        while url and url[-1] in _PONTUACAO_FINAL:
            sobra = url[-1] + sobra
            url = url[:-1]
        partes.append(escape(texto[posicao:achado.start()]))
        partes.append(_montar_link(url) if link_seguro(url) else escape(url))
        partes.append(escape(sobra))
        posicao = achado.end()
    partes.append(escape(texto[posicao:]))
    html = "".join(str(p) for p in partes).replace("\r\n", "\n").replace("\n", "<br>")
    return mark_safe(html)


@register.filter(name="pode_apagar")
def pode_apagar_filtro(objeto, usuario):
    from ..permissoes import pode_apagar

    return pode_apagar(usuario, objeto)
