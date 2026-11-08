from django import template
from django.conf import settings
from django.utils.html import json_script

register = template.Library()


@register.simple_tag
def pyodide_url():
    url = settings.SIMAP_PYODIDE_URL
    return url if url.endswith("/") else url + "/"


@register.filter
def casos_json(casos, sufixo):
    """
    Casos de teste no formato que o editor (JavaScript) espera, dentro de um
    <script type="application/json">. O json_script escapa tudo, então um
    caso com "</script>" no texto não quebra a página.
    """
    dados = [{"entrada": c.entrada, "saida": c.saida_esperada} for c in (casos or [])]
    return json_script(dados, f"casos-{sufixo}")
