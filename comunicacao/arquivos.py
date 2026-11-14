"""
Funções comuns a todo arquivo enviado no SIMAP (comunicação, material das
trilhas e entregas): validar uma lista, gravar e entregar no download.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404

from .seguranca import nome_para_download, validar_anexo


def validar_arquivos(arquivos):
    """
    Confere uma lista de arquivos enviados num formulário.

    Devolve pares (arquivo, ArquivoValidado) ou levanta um ValidationError
    com uma mensagem para cada arquivo recusado.
    """
    arquivos = list(arquivos or [])
    if len(arquivos) > settings.COMUNICACAO_MAXIMO_ANEXOS:
        raise ValidationError(
            f"Envie no máximo {settings.COMUNICACAO_MAXIMO_ANEXOS} arquivos de uma vez."
        )
    validados, erros = [], []
    for arquivo in arquivos:
        try:
            validados.append((arquivo, validar_anexo(arquivo)))
        except ValidationError as erro:
            erros.extend(erro.messages)
    if erros:
        raise ValidationError(erros)
    return validados


def salvar_arquivos(modelo, pares, **dono):
    """Grava os arquivos já validados, ligados ao dono (ex.: trilha=..., submissao=...)."""
    criados = []
    for arquivo, dados in pares:
        registro = modelo(
            nome_original=dados.nome_original,
            extensao=dados.extensao,
            tipo_conteudo=dados.tipo_conteudo,
            tamanho=dados.tamanho,
            sha256=dados.sha256,
            **dono,
        )
        # Imagens e pacotes Office passam a usar os bytes reconstruídos.
        arquivo.seek(0)
        conteudo = ContentFile(dados.conteudo_seguro) if dados.conteudo_seguro is not None else arquivo
        registro.arquivo.save(dados.nome_original, conteudo, save=False)
        registro.save()
        criados.append(registro)
    return criados


def resposta_de_download(registro, mostrar_na_tela=False):
    """
    Entrega o arquivo com as proteções de sempre.

    O tipo do conteúdo vem da nossa lista (nunca do que o navegador de quem
    enviou informou), o navegador é proibido de adivinhar outro tipo (nosniff)
    e a resposta vem com uma política que bloqueia scripts. Só imagens podem
    abrir na tela; todo o resto é sempre baixado. Quem chama esta função já
    conferiu se a pessoa pode ver o arquivo.
    """
    try:
        arquivo = registro.arquivo.open("rb")
    except FileNotFoundError:
        raise Http404("O arquivo não está mais disponível.") from None
    resposta = FileResponse(
        arquivo,
        as_attachment=not (mostrar_na_tela and registro.eh_imagem),
        filename=nome_para_download(registro.nome_original, registro.extensao),
        content_type=registro.tipo_conteudo,
    )
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


def conectar_limpeza_do_disco(modelo):
    """Quando o registro sai do banco, o arquivo também sai do disco."""
    from django.db import transaction
    from django.db.models.signals import post_delete

    def apagar(sender, instance, **kwargs):
        if not instance.arquivo:
            return
        storage, nome = instance.arquivo.storage, instance.arquivo.name
        # Só depois que a exclusão no banco for confirmada.
        transaction.on_commit(lambda: storage.delete(nome))

    post_delete.connect(apagar, sender=modelo, weak=False, dispatch_uid=f"limpeza_disco_{modelo._meta.label}")
