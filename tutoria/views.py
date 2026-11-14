from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views import View

from core.mixins import DiscenteRequiredMixin
from entregas.views import atividades_do_aluno

from . import servicos
from .models import PedidoDeAjuda


def _atividade_do_aluno(request, pk):
    return get_object_or_404(atividades_do_aluno(request.user).select_related("trilha__turma"), pk=pk)


def _estado(aluno, atividade):
    atual = servicos.situacao(aluno, atividade)
    return {
        "restantes_hoje": atual.restantes_hoje,
        "proximo_nivel": atual.proximo_nivel,
        "espera_segundos": atual.espera_segundos,
        "ajuda_ligada": atual.ajuda_ligada,
    }


class AjudaAtividadeView(DiscenteRequiredMixin, View):
    """Página de ajuda das atividades teóricas (nas práticas, o painel fica no editor)."""

    def get(self, request, pk):
        atividade = _atividade_do_aluno(request, pk)
        if not atividade.ajuda_ia:
            raise Http404
        return render(request, "tutoria/atividade.html", {"atividade": atividade})


class PedirAjudaView(DiscenteRequiredMixin, View):
    """Recebe o clique num botão de ajuda (chamado pelo JavaScript) e devolve a resposta."""

    def post(self, request, pk):
        atividade = _atividade_do_aluno(request, pk)
        tipo = request.POST.get("tipo", "")
        if tipo not in PedidoDeAjuda.Tipo.values:
            return JsonResponse({"erro": "Tipo de ajuda inválido."}, status=400)
        if tipo == PedidoDeAjuda.Tipo.CODIGO and not atividade.eh_pratica:
            return JsonResponse({"erro": "Esta atividade não tem código para analisar."}, status=400)
        try:
            nivel = int(request.POST.get("nivel") or 0)
        except ValueError:
            return JsonResponse({"erro": "Nível inválido."}, status=400)

        try:
            pedido = servicos.pedir_ajuda(
                request.user, atividade, tipo, nivel,
                codigo=request.POST.get("codigo", ""), erro=request.POST.get("erro", ""),
            )
        except servicos.PedidoRecusado as motivo:
            return JsonResponse({"erro": str(motivo), "estado": _estado(request.user, atividade)}, status=429)

        html = render_to_string("tutoria/_pedido.html", {"pedido": pedido}, request=request)
        return JsonResponse({"html": html, "status": pedido.status, "estado": _estado(request.user, atividade)})
