"""
Todo registro de auditoria passa por aqui antes de ir para o banco.

A regra mais importante deste arquivo: a auditoria nunca pode derrubar o
sistema. Se der qualquer problema na hora de gravar, o erro vai para o log
e o usuário segue usando o SIMAP normalmente, sem nem perceber.
"""
import logging

from django.db import transaction

from . import contexto
from .models import RegistroAuditoria

logger = logging.getLogger("simap.auditoria")

# Se o nome do campo tiver algum desses trechos, o valor nunca é gravado.
# É a minimização de dados da LGPD: guardamos que a senha mudou, não a senha.
CAMPOS_SENSIVEIS = ("password", "senha", "token", "secret", "api_key")
LIMITE_VALOR = 200


def campo_sensivel(nome):
    nome = nome.lower()
    return any(trecho in nome for trecho in CAMPOS_SENSIVEIS)


def valor_para_json(nome, valor):
    """Prepara o valor de um campo para ser gravado, escondendo o que é sensível."""
    if campo_sensivel(nome):
        return "***"
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    # Textos longos (como a resposta de uma atividade) são cortados, para
    # a auditoria registrar a ação sem virar uma cópia de todo o conteúdo.
    texto = str(valor)
    if len(texto) > LIMITE_VALOR:
        texto = texto[:LIMITE_VALOR] + "…"
    return texto


def registrar(acao, *, usuario=None, instancia=None, alvo=None, descricao="",
              dados=None, status_http=None, ctx=None, usuario_login=None):
    """
    Grava um registro de auditoria.

    IP, navegador e caminho vêm da requisição que está em andamento. Se a
    ação aconteceu fora de uma requisição (um comando no terminal, por
    exemplo), o registro fica sem usuário e aparece como "sistema".
    """
    ctx = ctx or contexto.atual()
    if usuario is None and ctx is not None:
        usuario = ctx.usuario

    campos = {
        "acao": acao,
        "descricao": descricao[:255],
        "dados": dados,
        "status_http": status_http,
    }

    if usuario is not None:
        campos["usuario"] = usuario
        campos["usuario_login"] = usuario.get_username()[:150]
    elif usuario_login:
        # Login que deu errado: ainda não existe usuário válido,
        # então guardamos só o nome que a pessoa digitou.
        campos["usuario_login"] = usuario_login[:150]

    if instancia is not None:
        campos["entidade"] = instancia._meta.label
        campos["objeto_id"] = str(instancia.pk)[:64] if instancia.pk is not None else ""
        campos["objeto_repr"] = _repr_seguro(instancia)
    elif alvo is not None:
        # Na exclusão o objeto já não existe mais, então usamos
        # a "foto" que foi tirada dele logo antes de apagar.
        campos["entidade"] = alvo["entidade"]
        campos["objeto_id"] = str(alvo["pk"])[:64]
        campos["objeto_repr"] = alvo["repr"][:200]

    if ctx is not None:
        campos.update(
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metodo=ctx.metodo,
            caminho=ctx.caminho,
        )

    try:
        # O savepoint garante que, se a gravação falhar no meio de uma
        # transação maior, só o registro de auditoria é desfeito, e não
        # a operação que o usuário estava fazendo.
        with transaction.atomic():
            return RegistroAuditoria.objects.create(**campos)
    except Exception:  # noqa: BLE001
        logger.exception("Não foi possível gravar o registro de auditoria (%s).", acao)
        return None


def _repr_seguro(instancia):
    # O __str__ de alguns modelos consulta objetos relacionados, que podem já
    # ter sido apagados numa exclusão em cascata. Se falhar, usamos um texto simples.
    try:
        return str(instancia)[:200]
    except Exception:  # noqa: BLE001
        return f"{instancia._meta.verbose_name} #{instancia.pk}"
