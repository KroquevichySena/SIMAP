"""
Validação dos anexos da comunicação.

A regra geral é "só entra o que a gente conhece". Em vez de tentar listar
tudo que é perigoso (.bat, .exe, .vbs, .ps1, .scr e mais centenas), temos
uma lista curta do que é permitido, e cada arquivo passa por quatro filtros:

1. Nome: a extensão final precisa estar na lista. "trabalho.pdf.bat" termina
   em .bat e é recusado. Caracteres de controle e o caractere que inverte o
   texto (usado para disfarçar "fdp.exe" como "exe.pdf") são removidos.
2. Tamanho: no máximo COMUNICACAO_TAMANHO_MAXIMO_ANEXO (10 MB).
3. Conteúdo: bibliotecas leem a estrutura real; imagens são reconstruídas. Um
   programa .exe renomeado para .pdf começa com "MZ", e não com "%PDF", então
   é recusado. Documentos do Office com macro e PDFs com ações ativas também.
4. Executáveis disfarçados: qualquer arquivo que comece com a assinatura de
   um executável do Windows, Linux ou macOS é recusado, seja qual for o nome.

O arquivo aprovado é salvo com um nome aleatório e só é entregue pela view
de download, que força o navegador a baixar (não abrir) e proíbe que ele
tente adivinhar o tipo do conteúdo.
"""
import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename

from .validacao_documentos import conferir_office, conferir_pdf, reconstruir_imagem

# Categorias: define como o arquivo é conferido e como ele é entregue.
DOCUMENTO = "documento"
IMAGEM = "imagem"
TEXTO = "texto"
CODIGO = "codigo"

# Extensão permitida -> (categoria, tipo MIME usado no download)
EXTENSOES_PERMITIDAS = {
    # Documentos
    ".pdf": (DOCUMENTO, "application/pdf"),
    ".docx": (DOCUMENTO, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".xlsx": (DOCUMENTO, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".pptx": (DOCUMENTO, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    # Imagens (SVG fica de fora: ele pode carregar JavaScript)
    ".png": (IMAGEM, "image/png"),
    ".jpg": (IMAGEM, "image/jpeg"),
    ".jpeg": (IMAGEM, "image/jpeg"),
    ".gif": (IMAGEM, "image/gif"),
    ".webp": (IMAGEM, "image/webp"),
    # Texto puro
    ".txt": (TEXTO, "text/plain"),
    ".md": (TEXTO, "text/plain"),
    ".csv": (TEXTO, "text/plain"),
    # Código-fonte: aceito só como texto, nunca executado pelo SIMAP
    ".py": (CODIGO, "text/plain"),
    ".java": (CODIGO, "text/plain"),
    ".c": (CODIGO, "text/plain"),
    ".cpp": (CODIGO, "text/plain"),
    ".h": (CODIGO, "text/plain"),
    ".cs": (CODIGO, "text/plain"),
    ".js": (CODIGO, "text/plain"),
    ".ts": (CODIGO, "text/plain"),
    ".html": (CODIGO, "text/plain"),
    ".css": (CODIGO, "text/plain"),
    ".sql": (CODIGO, "text/plain"),
    ".json": (CODIGO, "text/plain"),
}

# Executáveis e instaladores, reconhecidos pelo conteúdo e não pelo nome.
ASSINATURAS_EXECUTAVEL = (
    b"MZ",                    # .exe, .dll, .scr, .com do Windows
    b"\x7fELF",               # programas do Linux
    b"\xcf\xfa\xed\xfe",      # programas do macOS (64 bits)
    b"\xce\xfa\xed\xfe",      # programas do macOS (32 bits)
    b"\xca\xfe\xba\xbe",      # programas universais do macOS / classes Java compiladas
    b"\xd0\xcf\x11\xe0",      # .doc/.xls/.msi antigos (formato que carrega macros)
)

# Parte principal que cada documento do Office precisa ter.
PARTE_PRINCIPAL_OFFICE = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
    ".pptx": "ppt/presentation.xml",
}

# Caracteres invisíveis de controle de direção do texto (o truque do "fdp.exe").
_CARACTERES_DE_DIRECAO = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069]")


@dataclass(frozen=True)
class ArquivoValidado:
    nome_original: str
    extensao: str
    categoria: str
    tipo_conteudo: str
    tamanho: int
    sha256: str
    conteudo_seguro: bytes | None = field(default=None, repr=False)


def limpar_nome(nome):
    """Deixa o nome do arquivo seguro para mostrar e para gravar."""
    nome = os.path.basename(nome or "")
    nome = _CARACTERES_DE_DIRECAO.sub("", nome)
    nome = "".join(c for c in nome if unicodedata.category(c)[0] != "C")
    nome = unicodedata.normalize("NFC", nome).strip().strip(".")
    try:
        nome = get_valid_filename(nome)
    except Exception:  # get_valid_filename recusa nomes que viram vazios
        nome = ""
    return nome[:200] or "arquivo"


def _ler_tudo(arquivo):
    arquivo.seek(0)
    conteudo = arquivo.read(settings.COMUNICACAO_TAMANHO_MAXIMO_ANEXO + 1)
    arquivo.seek(0)
    return conteudo


def _conferir_texto(conteudo):
    if b"\x00" in conteudo:
        raise ValidationError("Arquivos de texto e de código não podem ter conteúdo binário.")
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            conteudo.decode(codificacao)
            return
        except UnicodeDecodeError:
            continue
    raise ValidationError("Não foi possível ler o arquivo como texto.")


def validar_anexo(arquivo):
    """Confere um arquivo enviado e devolve os dados dele, ou levanta ValidationError."""
    nome = limpar_nome(getattr(arquivo, "name", ""))
    extensao = os.path.splitext(nome)[1].lower()

    if extensao not in EXTENSOES_PERMITIDAS:
        mostrar = extensao or "sem extensão"
        raise ValidationError(
            f"O arquivo \"{nome}\" não foi aceito: o tipo {mostrar} não é permitido."
        )

    limite = settings.COMUNICACAO_TAMANHO_MAXIMO_ANEXO
    if arquivo.size > limite:
        raise ValidationError(
            f"O arquivo \"{nome}\" passa do limite de {limite // (1024 * 1024)} MB."
        )
    if arquivo.size == 0:
        raise ValidationError(f"O arquivo \"{nome}\" está vazio.")

    conteudo = _ler_tudo(arquivo)
    if len(conteudo) != arquivo.size:
        raise ValidationError("O tamanho informado não corresponde ao conteúdo recebido.")
    conteudo_seguro = None
    if conteudo.startswith(ASSINATURAS_EXECUTAVEL):
        raise ValidationError(f"O arquivo \"{nome}\" é um programa executável disfarçado e foi bloqueado.")

    categoria, tipo_conteudo = EXTENSOES_PERMITIDAS[extensao]
    try:
        if extensao == ".pdf":
            conferir_pdf(conteudo)
        elif extensao in PARTE_PRINCIPAL_OFFICE:
            conteudo_seguro = conferir_office(conteudo, extensao)
        elif categoria == IMAGEM:
            conteudo_seguro = reconstruir_imagem(conteudo, extensao)
        else:
            _conferir_texto(conteudo)
    except ValidationError as erro:
        raise ValidationError(f"O arquivo \"{nome}\" não foi aceito. {erro.messages[0]}") from erro

    conteudo_final = conteudo_seguro if conteudo_seguro is not None else conteudo
    if len(conteudo_final) > limite:
        raise ValidationError("O arquivo ultrapassa o limite de tamanho depois da reconstrução segura.")
    return ArquivoValidado(
        nome_original=nome,
        extensao=extensao,
        categoria=categoria,
        tipo_conteudo=tipo_conteudo,
        tamanho=len(conteudo_final),
        sha256=hashlib.sha256(conteudo_final).hexdigest(),
        conteudo_seguro=conteudo_seguro,
    )


def nome_para_download(nome_original, extensao):
    """
    Código-fonte é baixado com ".txt" no fim (ex.: "exercicio.py.txt").

    Assim, um clique duplo no arquivo baixado abre um editor de texto, e não
    executa o programa no computador de quem baixou.
    """
    categoria = EXTENSOES_PERMITIDAS.get(extensao, (CODIGO, ""))[0]
    if categoria == CODIGO:
        return f"{nome_original}.txt"
    return nome_original
