"""A publicação da avaliação oficial aciona o aviso ao aluno (RF33)."""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from comunicacao.emails_academicos import registrar_feedback

from .models import AvaliacaoOficial

logger = logging.getLogger("simap.integracoes")


@receiver(pre_save, sender=AvaliacaoOficial, dispatch_uid="rf33_feedback_anterior")
def guardar_feedback_anterior(sender, instance, raw=False, **kwargs):
    if not raw:
        instance._feedback_anterior = (
            sender.objects.filter(pk=instance.pk)
            .values_list(
                "nota",
                "feedback_professor",
            )
            .first()
        )


@receiver(post_save, sender=AvaliacaoOficial, dispatch_uid="rf33_feedback_publicado")
def avisar_feedback_publicado(sender, instance, raw=False, **kwargs):
    if raw or getattr(instance, "_feedback_anterior", None) == (
        Decimal(str(instance.nota)),
        instance.feedback_professor,
    ):
        return
    try:
        # O savepoint isola uma falha de registro do aviso sem perder a avaliação.
        with transaction.atomic():
            registrar_feedback(instance)
    except Exception:
        logger.exception("Não foi possível registrar o aviso da avaliação #%s", instance.pk)
