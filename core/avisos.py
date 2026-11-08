"""
Avisos automáticos para os alunos quando o professor publica algo novo.

O aviso só sai quando o conteúdo passa a ficar visível para o aluno: criar
uma trilha como rascunho não avisa ninguém, mas marcar "publicada" depois
avisa. Editar o texto de algo que já estava publicado também não gera aviso,
para a turma não receber uma notificação a cada correção de vírgula.
"""
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from comunicacao.models import Notificacao
from comunicacao.servicos import notificar_alunos


def url_da_trilha(trilha):
    return f"{reverse('core:minhas_trilhas')}#trilha-{trilha.pk}"


def url_da_atividade(atividade):
    return f"{reverse('core:minhas_trilhas')}#atividade-{atividade.pk}"


def avisar_trilha_publicada(trilha):
    return notificar_alunos(
        trilha.turma,
        Notificacao.Tipo.TRILHA,
        f"Nova trilha em {trilha.turma.nome}: \"{Truncator(trilha.titulo).chars(80)}\".",
        url_da_trilha(trilha),
    )


def avisar_atividade_publicada(atividade):
    texto = f"Nova atividade em \"{Truncator(atividade.trilha.titulo).chars(50)}\": " \
            f"\"{Truncator(atividade.titulo).chars(60)}\"."
    if atividade.prazo:
        texto += f" Prazo: {timezone.localtime(atividade.prazo):%d/%m às %H:%M}."
    return notificar_alunos(
        atividade.trilha.turma, Notificacao.Tipo.ATIVIDADE, texto, url_da_atividade(atividade)
    )
