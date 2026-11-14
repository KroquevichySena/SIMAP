"""
Conversa com o Gemini (biblioteca google-genai).

Fica isolado aqui para os testes poderem trocar a IA por uma resposta pronta
(ver tutoria/tests.py) e para o resto do código não depender da biblioteca.
"""
import logging
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger("simap.integracoes")

TEMPO_LIMITE_MS = 20_000


class IAIndisponivel(Exception):
    """A IA não respondeu (sem chave, fora do ar, tempo esgotado...)."""


@dataclass
class RespostaDaIA:
    texto: str
    fontes: list = field(default_factory=list)       # [{"titulo": ..., "url": ...}]
    sugestoes_html: str = ""                         # sugestões de busca do Google


def _cliente():
    from google import genai
    from google.genai import types

    if not settings.GEMINI_API_KEY:
        raise IAIndisponivel("GEMINI_API_KEY não configurada")
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=TEMPO_LIMITE_MS),
    )


def perguntar(instrucoes, conteudo, buscar_na_web=False, max_tokens=700):
    """Manda o pedido ao Gemini e devolve o texto (e as fontes, se buscou na web)."""
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=instrucoes,
        temperature=0.4,
        max_output_tokens=max_tokens,
        tools=[types.Tool(google_search=types.GoogleSearch())] if buscar_na_web else None,
    )
    try:
        resposta = _cliente().models.generate_content(
            model=settings.TUTORIA_MODELO, contents=conteudo, config=config
        )
    except IAIndisponivel:
        raise
    except Exception as erro:  # rede, cota, chave inválida...
        logger.exception("Falha ao chamar o Gemini na tutoria")
        raise IAIndisponivel(str(erro)) from erro

    texto = (getattr(resposta, "text", None) or "").strip()
    if not texto:
        raise IAIndisponivel("resposta vazia")

    fontes, sugestoes = [], ""
    candidatos = getattr(resposta, "candidates", None) or []
    metadados = getattr(candidatos[0], "grounding_metadata", None) if candidatos else None
    if metadados:
        for pedaco in getattr(metadados, "grounding_chunks", None) or []:
            web = getattr(pedaco, "web", None)
            if web and getattr(web, "uri", None):
                fontes.append({"titulo": (web.title or web.domain or "")[:120], "url": web.uri})
        ponto = getattr(metadados, "search_entry_point", None)
        sugestoes = (getattr(ponto, "rendered_content", None) or "") if ponto else ""
    return RespostaDaIA(texto=texto, fontes=fontes, sugestoes_html=sugestoes)
