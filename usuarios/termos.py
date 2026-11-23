"""
Versão vigente dos termos e conversão do texto para a página.

O texto é escrito pela coordenação num formato simples, sem HTML:

    # Título da cláusula        (numerada sozinha e listada no índice)
    ## Subtítulo
    - item de lista
    > citação em destaque       (usada na declaração de aceite)
    ---                         (o que vem depois vira o rodapé)
    **negrito** e *itálico*

Linhas seguidas formam um parágrafo; uma linha em branco separa os blocos.
Todo o texto é escapado antes de receber as marcações acima, então nenhum
HTML digitado chega à página.
"""
import re

from django.conf import settings
from django.db.models import Subquery, Value
from django.db.models.functions import Coalesce
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import VersaoTermos

FORMATO_NUMERO = re.compile(r"^\d+(\.\d+){0,3}$")


def versao_vigente():
    return VersaoTermos.objects.order_by("-pk").first()


def numero_vigente():
    """Sem nenhuma versão cadastrada, vale a versão inicial definida nas configurações."""
    versao = versao_vigente()
    return versao.numero if versao else settings.TERMOS_DE_USO_VERSAO


def numero_vigente_expr():
    """O mesmo número, como expressão do banco, para conferir o aceite numa só consulta."""
    ultima = VersaoTermos.objects.order_by("-pk").values("numero")[:1]
    return Coalesce(Subquery(ultima), Value(settings.TERMOS_DE_USO_VERSAO))


def chave_numero(numero):
    return tuple(int(parte) for parte in numero.split("."))


def _inline(trecho):
    trecho = escape(trecho)
    trecho = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", trecho)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", trecho)


def linhas(texto):
    """Os pontos de um campo "um por linha", sem marcadores e linhas vazias."""
    return [
        mark_safe(_inline(linha.strip().lstrip("-").strip()))
        for linha in (texto or "").splitlines()
        if linha.strip()
    ]


def formatar(texto):
    """Devolve o índice das cláusulas, o corpo e o rodapé já prontos para o template."""
    indice, corpo, rodape = [], [], []
    destino = corpo
    bloco, tipo = [], None

    def fechar():
        nonlocal bloco, tipo
        if bloco:
            if tipo == "lista":
                itens = "".join(f"<li>{_inline(item)}</li>" for item in bloco)
                destino.append(f'<ol type="a">{itens}</ol>')
            elif tipo == "citacao":
                destino.append(f'<blockquote class="simap-termos-aceite">{_inline(" ".join(bloco))}</blockquote>')
            else:
                destino.append(f"<p>{_inline(' '.join(bloco))}</p>")
        bloco, tipo = [], None

    for linha in (texto or "").replace("\r\n", "\n").split("\n"):
        conteudo = linha.strip()
        if not conteudo:
            fechar()
        elif conteudo == "---":
            fechar()
            destino = rodape
        elif conteudo.startswith("## "):
            fechar()
            destino.append(f'<h3 class="simap-termos-subtitulo">{_inline(conteudo[3:])}</h3>')
        elif conteudo.startswith("# "):
            fechar()
            numero = len(indice) + 1
            titulo = conteudo[2:].strip()
            indice.append({"numero": numero, "titulo": titulo.replace("*", "")})
            destino.append(
                f'<h2 id="clausula-{numero}" class="simap-termos-clausula"><span>{numero}</span> {_inline(titulo)}</h2>'
            )
        elif conteudo.startswith("- "):
            if tipo != "lista":
                fechar()
                tipo = "lista"
            bloco.append(conteudo[2:])
        elif conteudo.startswith("> "):
            if tipo != "citacao":
                fechar()
                tipo = "citacao"
            bloco.append(conteudo[2:])
        else:
            if tipo not in (None, "paragrafo"):
                fechar()
            tipo = "paragrafo"
            bloco.append(conteudo)
    fechar()
    return {"indice": indice, "corpo": mark_safe("\n".join(corpo)), "rodape": mark_safe("\n".join(rodape))}
