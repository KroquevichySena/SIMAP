"""
A auditoria "escuta" o que acontece no sistema, sem precisar mexer nas
views dos outros apps.

Para login, logout e login com erro, usamos os sinais que o próprio Django
dispara. Eles funcionam tanto no login do admin quanto na tela de login do
SIMAP, então quando a tela nova entrar, nada aqui precisa mudar.

Para os dados, ouvimos os momentos antes e depois de salvar e de excluir os
modelos listados em AUDITORIA_MODELOS. Se um app da lista ainda não estiver
instalado (como o de entregas antes do merge), ele é simplesmente ignorado,
e passa a ser auditado sozinho quando entrar no projeto.
"""
import logging
from dataclasses import replace

from django.apps import apps
from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save

from . import contexto
from .models import Acao
from .servicos import _repr_seguro, registrar, valor_para_json

logger = logging.getLogger("simap.auditoria")

MODELOS_PADRAO = [
    "usuarios.Usuario",
    "usuarios.AceiteTermos",
    "turmas.Turma",
    "turmas.Matricula",
    "core.TrilhaAprendizagem",
    "core.Atividade",
    "core.ConclusaoAtividade",
    "chamada.Chamada",
    "chamada.Registro_de_Presenca",
    "entregas.Submissao",
    "entregas.AnaliseIA",
    "entregas.AvaliacaoOficial",
]

# O Django atualiza o last_login sozinho a cada login. Não é uma ação do
# usuário, então não queremos um registro de "alteração" por causa disso.
CAMPOS_IGNORADOS = {"last_login"}

_UID = "simap_auditoria_{}_{}"


# Autenticação

def _contexto_de(request):
    return contexto.a_partir_do_request(request) if request is not None else None


def ao_logar(sender, request, user, **kwargs):
    registrar(Acao.LOGIN, usuario=user, ctx=_contexto_de(request),
              descricao="Login realizado.")
    # A requisição começou com um visitante anônimo, mas a partir daqui já é
    # esse usuário. Atualizamos o contexto para que o que for salvo depois do
    # login, nessa mesma requisição (como o aceite dos termos), fique no nome dele.
    atual = contexto.atual()
    if atual is not None:
        contexto.definir(replace(atual, usuario=user))


def ao_deslogar(sender, request, user, **kwargs):
    if user is None:
        return
    registrar(Acao.LOGOUT, usuario=user, ctx=_contexto_de(request),
              descricao="Logout realizado.")


def ao_falhar_login(sender, credentials, request=None, **kwargs):
    # O Django já esconde a senha dentro de 'credentials', mas mesmo assim
    # aproveitamos só o nome de usuário que a pessoa digitou.
    login_digitado = str(credentials.get("username", ""))
    registrar(
        Acao.LOGIN_FALHA,
        usuario_login=login_digitado,
        ctx=_contexto_de(request),
        descricao=f"Tentativa de login falhou para '{login_digitado[:100]}'.",
    )


# Alterações nos dados

def _campos_auditaveis(modelo):
    for campo in modelo._meta.concrete_fields:
        if campo.primary_key or campo.name in CAMPOS_IGNORADOS:
            continue
        # Campos com auto_now mudam sozinhos a cada save, não interessam.
        if getattr(campo, "auto_now", False):
            continue
        yield campo


def _retrato(instancia):
    """Uma "foto" dos valores do objeto, com os campos sensíveis escondidos."""
    return {
        campo.name: valor_para_json(campo.name, getattr(instancia, campo.attname))
        for campo in _campos_auditaveis(type(instancia))
    }


def antes_de_salvar(sender, instance, raw=False, update_fields=None, **kwargs):
    # Objeto novo não tem "antes". Para os que já existem, buscamos como
    # estavam no banco, para depois comparar com o que está sendo salvo.
    if raw or instance._state.adding or instance.pk is None:
        return
    campos = [c.attname for c in _campos_auditaveis(sender)]
    if update_fields is not None:
        campos = [c for c in campos if c in update_fields or c.removesuffix("_id") in update_fields]
    if not campos:
        instance._auditoria_antes = {}
        return
    antes = sender._default_manager.filter(pk=instance.pk).values(*campos).first()
    instance._auditoria_antes = antes or {}


def depois_de_salvar(sender, instance, created, raw=False, update_fields=None, **kwargs):
    if raw:
        return
    if created:
        registrar(Acao.CRIACAO, instancia=instance, dados=_retrato(instance),
                  descricao=f"{sender._meta.verbose_name.capitalize()} criado(a).")
        return

    antes = getattr(instance, "_auditoria_antes", None)
    if antes is None:
        return

    # Guardamos só o que realmente mudou, com o valor de antes e o de depois.
    alteracoes = {}
    for campo in _campos_auditaveis(sender):
        if campo.attname not in antes:
            continue
        valor_antigo = antes[campo.attname]
        valor_novo = getattr(instance, campo.attname)
        if valor_antigo != valor_novo:
            alteracoes[campo.name] = {
                "antes": valor_para_json(campo.name, valor_antigo),
                "depois": valor_para_json(campo.name, valor_novo),
            }
    instance._auditoria_antes = None

    # Salvar sem mudar nada não gera registro.
    if alteracoes:
        registrar(
            Acao.ALTERACAO,
            instancia=instance,
            dados=alteracoes,
            descricao="Campos alterados: " + ", ".join(sorted(alteracoes)),
        )


def antes_de_excluir(sender, instance, **kwargs):
    # Tiramos a foto antes de apagar, enquanto os objetos relacionados ainda
    # existem. Depois da exclusão já não daria para saber o que era.
    instance._auditoria_exclusao = {
        "entidade": sender._meta.label,
        "pk": instance.pk,
        "repr": _repr_seguro(instance),
        "dados": _retrato(instance),
    }


def depois_de_excluir(sender, instance, **kwargs):
    retrato = getattr(instance, "_auditoria_exclusao", None) or {
        "entidade": sender._meta.label, "pk": instance.pk, "repr": "", "dados": None,
    }
    registrar(
        Acao.EXCLUSAO,
        alvo=retrato,
        dados=retrato["dados"],
        descricao=f"{sender._meta.verbose_name.capitalize()} excluído(a).",
    )


# Ligando tudo

def modelos_auditados():
    rotulos = getattr(settings, "AUDITORIA_MODELOS", MODELOS_PADRAO)
    modelos = []
    for rotulo in rotulos:
        try:
            modelos.append(apps.get_model(rotulo))
        except (LookupError, ValueError):
            logger.debug("Auditoria: o modelo %s não está instalado, pulando.", rotulo)
    return modelos


def conectar():
    user_logged_in.connect(ao_logar, dispatch_uid="simap_auditoria_login")
    user_logged_out.connect(ao_deslogar, dispatch_uid="simap_auditoria_logout")
    user_login_failed.connect(ao_falhar_login, dispatch_uid="simap_auditoria_login_falha")

    for modelo in modelos_auditados():
        rotulo = modelo._meta.label_lower
        pre_save.connect(antes_de_salvar, sender=modelo, dispatch_uid=_UID.format("pre_save", rotulo))
        post_save.connect(depois_de_salvar, sender=modelo, dispatch_uid=_UID.format("post_save", rotulo))
        pre_delete.connect(antes_de_excluir, sender=modelo, dispatch_uid=_UID.format("pre_delete", rotulo))
        post_delete.connect(depois_de_excluir, sender=modelo, dispatch_uid=_UID.format("post_delete", rotulo))
