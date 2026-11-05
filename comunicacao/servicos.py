"""
Criação de publicações, respostas e anexos, e o envio das notificações.

Tudo acontece numa transação: se um anexo falhar ao ser gravado, nem a
publicação nem as notificações ficam pela metade no banco.
"""
from django.db import transaction
from django.utils.text import Truncator

from . import permissoes
from .arquivos import salvar_arquivos
from .models import Anexo, Notificacao, Publicacao, Resposta


def _nome(usuario):
    return usuario.get_full_name() or usuario.username


def _salvar_anexos(dono, pares):
    """pares: lista de (arquivo enviado, ArquivoValidado)."""
    campo = "publicacao" if isinstance(dono, Publicacao) else "resposta"
    salvar_arquivos(Anexo, pares, **{campo: dono})


def _notificar(destinatarios, tipo, mensagem, url, exceto):
    notificacoes = [
        Notificacao(destinatario=pessoa, tipo=tipo, mensagem=mensagem[:255], url=url)
        for pessoa in {p.pk: p for p in destinatarios}.values()
        if pessoa.pk != exceto.pk
    ]
    Notificacao.objects.bulk_create(notificacoes)
    return len(notificacoes)


@transaction.atomic
def publicar(autor, turma, texto, anexos=(), atividade=None, destinatario=None):
    publicacao = Publicacao.objects.create(
        turma=turma, autor=autor, texto=texto, atividade=atividade, destinatario=destinatario
    )
    _salvar_anexos(publicacao, anexos)

    url = publicacao.get_absolute_url()
    if destinatario is not None:
        _notificar(
            [destinatario], Notificacao.Tipo.PRIVADA,
            f"{_nome(autor)} enviou uma mensagem privada para você ({turma.nome}).", url, autor,
        )
    elif atividade is not None:
        # Comentário do professor avisa a turma; comentário de aluno avisa o professor.
        publico = (
            permissoes.alunos_da_turma(turma) if turma.docente_id == autor.pk else [turma.docente]
        )
        _notificar(
            publico, Notificacao.Tipo.COMENTARIO,
            f"{_nome(autor)} comentou na atividade \"{Truncator(atividade.titulo).chars(60)}\".", url, autor,
        )
    else:
        publico = (
            permissoes.alunos_da_turma(turma) if turma.docente_id == autor.pk else [turma.docente]
        )
        _notificar(
            publico, Notificacao.Tipo.PUBLICACAO,
            f"{_nome(autor)} publicou no mural de {turma.nome}.", url, autor,
        )
    return publicacao


@transaction.atomic
def responder(autor, publicacao, texto, anexos=()):
    resposta = Resposta.objects.create(publicacao=publicacao, autor=autor, texto=texto)
    _salvar_anexos(resposta, anexos)

    # Avisamos quem já participa da conversa: o autor da publicação, quem já
    # respondeu e, numa mensagem privada, o destinatário. O professor também
    # acompanha toda conversa pública da turma. No fim, só fica quem ainda
    # pode ver a publicação (um aluno que saiu da turma não recebe nada).
    interessados = [publicacao.autor]
    interessados += [r.autor for r in publicacao.respostas.select_related("autor").exclude(pk=resposta.pk)]
    if publicacao.privada:
        interessados.append(publicacao.destinatario)
    else:
        interessados.append(publicacao.turma.docente)
    interessados = [p for p in interessados if permissoes.pode_ver_publicacao(p, publicacao)]

    _notificar(
        interessados, Notificacao.Tipo.RESPOSTA,
        f"{_nome(autor)} respondeu: \"{Truncator(publicacao.texto).chars(50)}\"",
        resposta.get_absolute_url(), autor,
    )
    return resposta


def notificar_alunos(turma, tipo, mensagem, url):
    """Avisa todos os alunos ativos da turma (usado pelas trilhas e atividades)."""
    notificacoes = [
        Notificacao(destinatario=aluno, tipo=tipo, mensagem=mensagem[:255], url=url)
        for aluno in permissoes.alunos_da_turma(turma)
    ]
    Notificacao.objects.bulk_create(notificacoes)
    return len(notificacoes)
