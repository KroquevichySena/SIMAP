"""Contas acadêmicas gerenciáveis e proteção de vínculos na exclusão pela interface."""

from django.db.models.deletion import CASCADE, PROTECT, RESTRICT

from .models import Usuario


def contas_academicas():
    return Usuario.objects.filter(perfil__in=["DOCENTE", "DISCENTE"], is_superuser=False, is_staff=False)


def possui_historico(usuario):
    if usuario.last_login is not None:
        return True
    # Inclui matrículas, turmas, aceites, entregas, mensagens e futuros vínculos
    # que seriam removidos em cascata ou impediriam a exclusão. A auditoria usa
    # SET_NULL e preserva o login em texto, portanto não é apagada pela exclusão.
    for relacao in Usuario._meta.related_objects:
        if relacao.one_to_many or relacao.one_to_one:
            if relacao.on_delete in (CASCADE, PROTECT, RESTRICT):
                if relacao.related_model._default_manager.filter(**{relacao.field.attname: usuario.pk}).exists():
                    return True
    return False
