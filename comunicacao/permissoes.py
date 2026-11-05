"""
Quem pode ver e fazer o quê na comunicação.

As regras, em resumo:
- Cada turma é um espaço fechado: só o docente dela e os alunos com
  matrícula ativa entram. Quem é de fora recebe 404, como se a turma não
  existisse (a mesma proteção contra IDOR usada nas trilhas).
- Mensagem privada é vista só pelo autor e pelo destinatário.
- O professor manda mensagem privada para qualquer aluno da turma; o aluno
  manda só para o professor. Aluno com aluno fica de fora de propósito: o
  professor não teria como moderar uma conversa que não enxerga.
- Comentários de atividade só aparecem para o aluno se a atividade estiver
  publicada.
- Apaga uma publicação ou resposta quem escreveu ou o docente da turma.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q

from turmas.models import Turma

Usuario = get_user_model()


def turmas_do_usuario(usuario):
    if not usuario.is_authenticated:
        return Turma.objects.none()
    if getattr(usuario, "is_docente", False):
        return Turma.objects.filter(docente=usuario, ativa=True)
    if getattr(usuario, "is_discente", False):
        return Turma.objects.filter(
            ativa=True, matricula__discente=usuario, matricula__status="ATIVA"
        ).distinct()
    return Turma.objects.none()


def participa_da_turma(usuario, turma):
    return turmas_do_usuario(usuario).filter(pk=turma.pk).exists()


def alunos_da_turma(turma):
    return Usuario.objects.filter(
        matricula__turma=turma, matricula__status="ATIVA", perfil="DISCENTE", is_active=True
    ).distinct()


def participantes_da_turma(turma):
    return Usuario.objects.filter(
        Q(pk=turma.docente_id) | Q(pk__in=alunos_da_turma(turma).values("pk"))
    )


def destinatarios_permitidos(usuario, turma):
    """Para quem o usuário pode mandar mensagem privada nesta turma."""
    if turma.docente_id == usuario.pk:
        return alunos_da_turma(turma).order_by("first_name", "username")
    if getattr(usuario, "is_discente", False):
        return Usuario.objects.filter(pk=turma.docente_id)
    return Usuario.objects.none()


def publicacoes_visiveis(usuario, turma):
    """Publicações da turma que o usuário pode ver (as privadas só se for parte delas)."""
    visiveis = turma.publicacoes.filter(
        Q(destinatario__isnull=True) | Q(autor=usuario) | Q(destinatario=usuario)
    )
    if turma.docente_id != usuario.pk:
        visiveis = visiveis.filter(Q(atividade__isnull=True) | Q(atividade__publicada=True))
    return visiveis


def pode_ver_atividade(usuario, atividade):
    turma = atividade.trilha.turma
    if not participa_da_turma(usuario, turma):
        return False
    return atividade.publicada or turma.docente_id == usuario.pk


def pode_ver_publicacao(usuario, publicacao):
    if not participa_da_turma(usuario, publicacao.turma):
        return False
    if publicacao.privada and usuario.pk not in (publicacao.autor_id, publicacao.destinatario_id):
        return False
    if publicacao.atividade_id and not pode_ver_atividade(usuario, publicacao.atividade):
        return False
    return True


def pode_apagar(usuario, objeto):
    """Vale para publicação e para resposta."""
    publicacao = getattr(objeto, "publicacao", None) or objeto
    return objeto.autor_id == usuario.pk or publicacao.turma.docente_id == usuario.pk
