from django import template

from tutoria import servicos
from tutoria.models import PedidoDeAjuda

register = template.Library()


@register.inclusion_tag("tutoria/_painel.html", takes_context=True)
def painel_de_ajuda(context, atividade, com_codigo=False):
    """O painel "Preciso de ajuda", com o histórico do aluno nesta atividade."""
    aluno = context["request"].user
    return {
        "atividade": atividade,
        "com_codigo": com_codigo,
        "situacao": servicos.situacao(aluno, atividade),
        "pedidos": PedidoDeAjuda.objects.filter(aluno=aluno, atividade=atividade)
        .exclude(status=PedidoDeAjuda.Status.EM_ANDAMENTO)
        .order_by("-criado_em")[:20],
        "csrf_token": context.get("csrf_token"),
    }


@register.simple_tag
def resumo_de_ajuda(atividade):
    """Uso da ajuda da IA por aluno, para a tela de correção."""
    return servicos.resumo_para_o_professor(atividade)


@register.filter
def do_aluno(resumo, aluno_id):
    return (resumo or {}).get(aluno_id)
