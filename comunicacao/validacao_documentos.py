"""Inspeção estrutural dos uploads. Nenhum conteúdo enviado é executado.

É uma política conservadora para materiais acadêmicos, não um antivírus.
Imagens são reconstruídas; documentos com recursos ativos são recusados.
"""
import io
import posixpath
import re
import stat
import warnings
import zipfile
from urllib.parse import unquote, urlsplit

from defusedxml import ElementTree
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, apply_configuration
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject

FORMATOS_IMAGEM = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".webp": "WEBP"}
MAX_PIXELS = 20_000_000
MAX_PIXELS_ANIMACAO = 40_000_000
MAX_QUADROS = 100
MAX_OBJETOS_PDF = 20_000
MAX_NOS_PDF = 100_000
MAX_PARTES_OFFICE = 2000
MAX_OFFICE_ABERTO = 100 * 1024 * 1024
MAX_XML = 10 * 1024 * 1024


def reconstruir_imagem(conteudo, extensao):
    """Decodifica todos os quadros e salva só os pixels, sem EXIF ou anexos."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(conteudo), formats=[FORMATOS_IMAGEM[extensao]]) as imagem:
                if imagem.width * imagem.height > MAX_PIXELS:
                    raise ValidationError("A imagem ultrapassa o limite de 20 milhões de pixels.")
                imagem.verify()
            with Image.open(io.BytesIO(conteudo), formats=[FORMATOS_IMAGEM[extensao]]) as imagem:
                quantidade = getattr(imagem, "n_frames", 1)
                if quantidade > MAX_QUADROS or quantidade * imagem.width * imagem.height > MAX_PIXELS_ANIMACAO:
                    raise ValidationError("A animação ultrapassa o limite de quadros ou de pixels.")
                quadros, duracoes = [], []
                for indice in range(quantidade):
                    imagem.seek(indice)
                    imagem.load()  # verify() sozinho não decodifica os pixels.
                    if imagem.width * imagem.height > MAX_PIXELS:
                        raise ValidationError("A imagem ultrapassa o limite de pixels.")
                    quadro = ImageOps.exif_transpose(imagem).convert("RGB" if extensao in (".jpg", ".jpeg") else "RGBA")
                    quadro.info.clear()
                    quadros.append(quadro)
                    duracoes.append(imagem.info.get("duration", 100))
                saida = io.BytesIO()
                opcoes = {}
                if quantidade > 1:
                    opcoes = {"save_all": True, "append_images": quadros[1:], "duration": duracoes,
                              "loop": imagem.info.get("loop", 0)}
                quadros[0].save(saida, format=FORMATOS_IMAGEM[extensao], **opcoes)
                return saida.getvalue()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as erro:
        raise ValidationError("O conteúdo não é uma imagem íntegra do tipo informado.") from erro


# Nomes já são decodificados pelo parser (inclusive escapes como #53).
CHAVES_PDF_PROIBIDAS = {"/JS", "/JavaScript", "/AA", "/XFA", "/EF", "/EmbeddedFiles", "/RichMediaContent"}
ACOES_PDF_PROIBIDAS = {"/JavaScript", "/Launch", "/SubmitForm", "/ImportData", "/GoToR", "/GoToE",
                       "/Rendition", "/Sound", "/Movie", "/RichMedia", "/3D", "/EmbeddedFile",
                       "/Filespec", "/FileAttachment"}


def conferir_pdf(conteudo):
    # Limites locais ao contexto desta validação, sem mudar outros leitores.
    with apply_configuration(
        maximum_declared_stream_length=20_000_000,
        zlib_maximum_output_length=20_000_000,
        array_based_stream_maximum_output_length=20_000_000,
        stream_decoding_work_maximum_length=40_000_000,
        page_tree_maximum_entries=5000,
        page_tree_maximum_depth=50,
        disable_legacy_handling=True,
    ):
        _conferir_estrutura_pdf(conteudo)


def _conferir_estrutura_pdf(conteudo):
    """Lê referências e objetos do PDF, inclusive os guardados em object streams."""
    if not conteudo.startswith(b"%PDF-"):
        raise ValidationError("O conteúdo não é um PDF de verdade.")
    if not conteudo.rstrip().endswith(b"%%EOF"):
        raise ValidationError("O PDF está incompleto ou tem conteúdo depois do final.")
    try:
        leitor = PdfReader(io.BytesIO(conteudo), strict=True, xref_stream_maximum_entries=MAX_OBJETOS_PDF)
        if leitor.is_encrypted:
            raise ValidationError("PDFs protegidos por senha não podem ser inspecionados e não são aceitos.")
        referencias = [(numero, geracao) for geracao, entradas in leitor.xref.items()
                       if geracao != 65535 for numero in entradas if numero != 0]
        referencias.extend((numero, 0) for numero in leitor.xref_objStm)
        if len(referencias) > MAX_OBJETOS_PDF:
            raise ValidationError("O PDF tem objetos demais para uma inspeção segura.")
        if not 0 < len(leitor.pages) <= 1000:
            raise ValidationError("O PDF precisa ter entre 1 e 1000 páginas.")
        pilha = [leitor.trailer]
        pilha.extend(IndirectObject(numero, geracao, leitor) for numero, geracao in referencias)
        vistos, referencias_vistas, passos = set(), set(), 0
        while pilha:
            objeto = pilha.pop()
            passos += 1
            if passos > MAX_NOS_PDF:
                raise ValidationError("O PDF é complexo demais para uma inspeção segura.")
            if isinstance(objeto, IndirectObject):
                chave = (objeto.idnum, objeto.generation)
                if chave in referencias_vistas:
                    continue
                referencias_vistas.add(chave)
                resolvido = objeto.get_object()
                if resolvido is None:
                    raise ValidationError("O PDF contém uma referência inválida.")
                pilha.append(resolvido)
            elif isinstance(objeto, (DictionaryObject, ArrayObject)):
                if id(objeto) in vistos:
                    continue
                vistos.add(id(objeto))
                if isinstance(objeto, DictionaryObject):
                    if CHAVES_PDF_PROIBIDAS.intersection(objeto):
                        raise ValidationError("O PDF contém conteúdo ativo ou arquivos embutidos.")
                    esquema = urlsplit(str(objeto["/URI"])).scheme.lower() if "/URI" in objeto else ""
                    if "/URI" in objeto and esquema not in ("http", "https", "mailto"):
                        raise ValidationError("O PDF contém um link de execução ou protocolo não permitido.")
                    pilha.extend(objeto.values())
                else:
                    pilha.extend(objeto)
            elif isinstance(objeto, NameObject) and objeto in ACOES_PDF_PROIBIDAS:
                raise ValidationError("O PDF contém conteúdo ativo ou arquivos embutidos.")
    except ValidationError:
        raise
    except Exception as erro:
        # Falha de leitura nunca autoriza a gravação do documento.
        raise ValidationError("O PDF está corrompido ou sua estrutura não é suportada.") from erro


NS_TIPOS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
PARTES_PRINCIPAIS = {
    ".docx": ("word/document.xml", "document", "wordprocessingml", "document"),
    ".xlsx": ("xl/workbook.xml", "workbook", "spreadsheetml", "sheet"),
    ".pptx": ("ppt/presentation.xml", "presentation", "presentationml", "presentation"),
}


def _xml_seguro(dados):
    if len(dados) > MAX_XML:
        raise ValidationError("Uma parte XML do documento é grande demais.")
    return ElementTree.fromstring(dados, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def _relacionamentos(raiz, nome, nomes):
    if raiz.tag != f"{{{NS_RELS}}}Relationships":
        raise ValidationError("O documento tem relacionamentos inválidos.")
    ids = set()
    for rel in raiz:
        tipo, destino = rel.get("Type", ""), rel.get("Target", "")
        identificador = rel.get("Id")
        if rel.tag != f"{{{NS_RELS}}}Relationship" or not identificador or identificador in ids or not destino:
            raise ValidationError("O documento tem relacionamentos inválidos.")
        ids.add(identificador)
        if any(
            trecho in tipo.lower()
            for trecho in (
                "oleobject",
                "package",
                "activex",
                "vbaproject",
                "attachedtemplate",
                "externallink",
                "afchunk",
            )
        ):
            raise ValidationError("O documento contém conteúdo ativo ou arquivos embutidos.")
        if rel.get("TargetMode") == "External":
            # Links clicáveis normais são permitidos; recursos externos automáticos não.
            if tipo != NS_REL_DOC + "hyperlink" or urlsplit(destino).scheme.lower() not in ("https", "http", "mailto"):
                raise ValidationError("O documento contém uma conexão externa não permitida.")
        else:
            destino = unquote(urlsplit(destino).path)
            base = posixpath.dirname(nome).replace("_rels", "").rstrip("/")
            caminho = posixpath.normpath(posixpath.join(base, destino)) if not destino.startswith("/") else destino[1:]
            if "\\" in destino or caminho not in nomes:
                raise ValidationError("O documento aponta para uma parte interna inexistente.")


def conferir_office(conteudo, extensao):
    """Confere o pacote completo e reconstrói as imagens internas antes de salvar."""
    principal, raiz_esperada, familia, tipo = PARTES_PRINCIPAIS[extensao]
    prefixo = principal.split("/")[0] + "/"
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
            itens = pacote.infolist()
            nomes = {item.filename for item in itens}
            if len(itens) > MAX_PARTES_OFFICE or sum(i.file_size for i in itens) > MAX_OFFICE_ABERTO:
                raise ValidationError("O documento é grande demais depois de descompactado.")
            if len({n.casefold() for n in nomes}) != len(itens):
                raise ValidationError("O documento contém partes duplicadas.")
            if "[Content_Types].xml" not in nomes or principal not in nomes or "_rels/.rels" not in nomes:
                raise ValidationError("O conteúdo não corresponde à extensão do arquivo.")
            partes, total = {}, 0
            for item in itens:
                nome, baixo = item.filename, item.filename.lower()
                if (
                    "\\" in nome
                    or nome.startswith("/")
                    or posixpath.normpath(nome.rstrip("/")) != nome.rstrip("/")
                    or ".." in nome.split("/")
                    or item.flag_bits & 1
                    or stat.S_ISLNK(item.external_attr >> 16)
                ):
                    raise ValidationError("O documento contém caminhos inválidos ou partes criptografadas.")
                if item.is_dir():
                    continue
                if "vba" in baixo or "activex" in baixo or "macrosheet" in baixo:
                    raise ValidationError("Documentos com macros ou controles ActiveX não são aceitos.")
                if "/embeddings/" in baixo:
                    raise ValidationError("Documentos com arquivos embutidos não são aceitos.")
                if nome != "[Content_Types].xml" and not nome.startswith(
                    (prefixo, "docProps/", "_rels/", "customXml/")
                ):
                    raise ValidationError("O documento contém um arquivo interno não permitido.")
                sufixo = ".rels" if baixo.endswith(".rels") else posixpath.splitext(baixo)[1]
                if sufixo not in (".xml", ".rels") and sufixo not in FORMATOS_IMAGEM:
                    raise ValidationError(
                        "O documento contém um tipo de arquivo interno não permitido. Exporte o material como PDF."
                    )
                with pacote.open(item) as entrada:
                    dados = entrada.read(min(item.file_size, MAX_OFFICE_ABERTO - total) + 1)
                total += len(dados)
                if len(dados) != item.file_size or total > MAX_OFFICE_ABERTO:
                    raise ValidationError("O documento é grande demais depois de descompactado.")
                partes[nome] = dados
            tipos = _xml_seguro(partes["[Content_Types].xml"])
            if tipos.tag != f"{{{NS_TIPOS}}}Types":
                raise ValidationError("O documento tem uma declaração de tipos inválida.")
            esperada = f"application/vnd.openxmlformats-officedocument.{familia}.{tipo}.main+xml"
            if not any(p.get("PartName") == "/" + principal and p.get("ContentType") == esperada for p in tipos):
                raise ValidationError("O tipo principal não corresponde à extensão do documento.")
            padroes, sobrescritos = {}, {}
            for declaracao in tipos:
                mime = declaracao.get("ContentType", "").lower()
                if any(p in mime for p in ("macro", "activex", "oleobject", "javascript", "vba")):
                    raise ValidationError("O documento declara conteúdo ativo não permitido.")
                if declaracao.tag == f"{{{NS_TIPOS}}}Default":
                    chave, tabela = declaracao.get("Extension", "").lower(), padroes
                elif declaracao.tag == f"{{{NS_TIPOS}}}Override":
                    chave, tabela = declaracao.get("PartName", "").lstrip("/"), sobrescritos
                    if chave not in partes:
                        raise ValidationError("O documento declara uma parte inexistente.")
                else:
                    raise ValidationError("O documento tem uma declaração de tipos inválida.")
                if not chave or chave in tabela or not mime:
                    raise ValidationError("O documento tem uma declaração de tipos duplicada ou inválida.")
                tabela[chave] = mime
            for nome, dados in list(partes.items()):
                sufixo = ".rels" if nome.lower().endswith(".rels") else posixpath.splitext(nome.lower())[1]
                mime = sobrescritos.get(nome, padroes.get(sufixo.lstrip("."), ""))
                if nome != "[Content_Types].xml":
                    mime_imagem = {
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                    }
                    if (
                        not mime
                        or (sufixo in mime_imagem and mime != mime_imagem[sufixo])
                        or (sufixo == ".rels" and mime != "application/vnd.openxmlformats-package.relationships+xml")
                        or (
                            sufixo == ".xml"
                            and not (mime == "application/xml" or mime == "text/xml" or mime.endswith("+xml"))
                        )
                    ):
                        raise ValidationError("O tipo declarado de uma parte interna é inválido.")
                if sufixo in (".xml", ".rels"):
                    raiz = _xml_seguro(dados)
                    if nome == principal and raiz.tag not in (
                        f"{{http://schemas.openxmlformats.org/{familia}/2006/main}}{raiz_esperada}",
                        f"{{http://purl.oclc.org/ooxml/{familia}/main}}{raiz_esperada}",
                    ):
                        raise ValidationError("A estrutura principal do documento é inválida.")
                    if sufixo == ".rels":
                        _relacionamentos(raiz, nome, nomes)
                    instrucoes = []
                    for elemento in raiz.iter():
                        local = elemento.tag.rsplit("}", 1)[-1]
                        if local.lower() in ("oleobject", "object", "altchunk", "ddelink", "ddelinks", "externalbook"):
                            raise ValidationError("O documento contém conteúdo ativo ou arquivos embutidos.")
                        if local == "f" and familia == "spreadsheetml":
                            formula = elemento.text or ""
                            if (
                                "|" in formula
                                or re.search(r"\b(?:WEBSERVICE|RTD|CALL|REGISTER\.ID|SQL\.REQUEST)\s*\(", formula, re.I)
                                or re.search(r"\bHYPERLINK\s*\(\s*\"\s*(?:javascript|file|data):", formula, re.I)
                            ):
                                raise ValidationError("A planilha contém uma fórmula de execução ou conexão externa.")
                        if local == "instrText":
                            instrucoes.append(elemento.text or "")
                        elif local == "fldSimple":
                            instrucoes.extend(elemento.attrib.values())
                    # Um comando pode estar dividido entre vários trechos de texto do Word.
                    if re.search(r"\b(?:DDE(?:AUTO)?|INCLUDETEXT|INCLUDEPICTURE|LINK)\b", "".join(instrucoes), re.I):
                        raise ValidationError("O documento contém campos de execução ou carregamento externo.")
                elif sufixo in FORMATOS_IMAGEM:
                    reconstruida = reconstruir_imagem(dados, sufixo)
                    total += len(reconstruida) - len(dados)
                    if total > MAX_OFFICE_ABERTO:
                        raise ValidationError("O documento é grande demais depois da reconstrução das imagens.")
                    partes[nome] = reconstruida
            rels_raiz = _xml_seguro(partes["_rels/.rels"])
            if not any(
                r.get("Type")
                in (
                    NS_REL_DOC + "officeDocument",
                    "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
                )
                and r.get("Target", "").lstrip("/") == principal
                and r.get("TargetMode") != "External"
                for r in rels_raiz
            ):
                raise ValidationError("O documento não vincula a sua parte principal.")
            saida = io.BytesIO()
            with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
                for nome, dados in partes.items():
                    novo.writestr(nome, dados)
            return saida.getvalue()
    except ValidationError:
        raise
    except Exception as erro:
        raise ValidationError("O documento Office está corrompido ou sua estrutura não é suportada.") from erro
