"""Quando um anexo sai do banco, o arquivo também sai do disco."""
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Anexo


@receiver(post_delete, sender=Anexo, dispatch_uid="comunicacao_apagar_arquivo")
def apagar_arquivo_do_disco(sender, instance, **kwargs):
    arquivo = instance.arquivo
    if not arquivo:
        return
    storage, nome = arquivo.storage, arquivo.name
    # Só apaga depois que a exclusão no banco for confirmada, para não perder
    # o arquivo se a transação for desfeita.
    transaction.on_commit(lambda: storage.delete(nome))
