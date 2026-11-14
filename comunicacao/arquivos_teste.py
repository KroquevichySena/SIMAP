"""Arquivos íntegros gerados em memória para os testes de upload."""
import io
import zipfile

from PIL import Image
from pypdf import PdfWriter
from pypdf.actions import JavaScript

from .validacao_documentos import NS_REL_DOC, NS_RELS, NS_TIPOS, PARTES_PRINCIPAIS


def pdf_teste(configurar=None):
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    if configurar:
        configurar(escritor)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def adicionar_javascript(escritor):
    escritor.add_open_action(JavaScript("app.alert(1)"))


def imagem_teste(formato="PNG", **opcoes):
    saida = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(saida, format=formato, **opcoes)
    return saida.getvalue()


def office_teste(principal="word/document.xml", extras=(), substituir=None):
    extensao = next(e for e, p in PARTES_PRINCIPAIS.items() if p[0] == principal)
    _, local, familia, tipo = PARTES_PRINCIPAIS[extensao]
    mime = f"application/vnd.openxmlformats-officedocument.{familia}.{tipo}.main+xml"
    partes = {
        "[Content_Types].xml": (
            f'<Types xmlns="{NS_TIPOS}">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            f'<Override PartName="/{principal}" ContentType="{mime}"/></Types>'
        ).encode(),
        "_rels/.rels": (
            f'<Relationships xmlns="{NS_RELS}"><Relationship Id="rId1" '
            f'Type="{NS_REL_DOC}officeDocument" Target="{principal}"/></Relationships>'
        ).encode(),
        principal: f'<x:{local} xmlns:x="http://schemas.openxmlformats.org/{familia}/2006/main"/>'.encode(),
    }
    partes.update({nome: b"conteudo" for nome in extras})
    partes.update(substituir or {})
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as pacote:
        for nome, conteudo in partes.items():
            pacote.writestr(nome, conteudo)
    return saida.getvalue()


PDF_OK = pdf_teste()
PNG_OK = imagem_teste()
