from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from core.mixins import DiscenteRequiredMixin, DocenteRequiredMixin
from turmas.models import Turma

from .forms import LimiteAtencaoForm
from .servicos import (
    METRICAS,
    dados_do_grafico,
    historico_do_aluno,
    indicadores_da_turma,
    indicadores_do_aluno,
    resumo_da_turma,
)

Usuario = get_user_model()


class PainelDocenteView(DocenteRequiredMixin, TemplateView):
    template_name = "painel/docente/painel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        turmas = Turma.objects.filter(docente=self.request.user, ativa=True).order_by(
            "-periodo", "nome"
        )
        turma_id = self.request.GET.get("turma", "")
        if turma_id.isdigit():
            turma = get_object_or_404(turmas, pk=int(turma_id))
        else:
            turma = turmas.first()

        ctx["turmas"] = turmas
        ctx["turma"] = turma
        if turma is None:
            return ctx

        linhas = indicadores_da_turma(turma)
        ctx["linhas"] = linhas
        ctx["resumo"] = resumo_da_turma(linhas)
        ctx["form_limite"] = LimiteAtencaoForm(instance=turma)
        ctx["dados_grafico"] = dados_do_grafico(turma, linhas)
        return ctx


class DetalheAlunoView(DocenteRequiredMixin, TemplateView):
    template_name = "painel/docente/detalhe_aluno.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        turma = get_object_or_404(
            Turma, pk=self.kwargs["turma_pk"], docente=self.request.user
        )
        discente = get_object_or_404(Usuario, pk=self.kwargs["aluno_pk"], perfil="DISCENTE")

        linhas = indicadores_da_turma(turma)
        linha = next((linha for linha in linhas if linha["discente"] == discente), None)
        if linha is None:
            raise Http404
        resumo = resumo_da_turma(linhas)

        ctx["turma"] = turma
        ctx["linha"] = linha
        ctx["resumo"] = resumo
        ctx["historico"] = historico_do_aluno(turma, discente)
        ctx["dados_comparacao"] = {
            "aluno": [linha[metrica] for metrica in METRICAS],
            "turma": [resumo[metrica] for metrica in METRICAS],
            "limite": float(turma.limite_atencao),
        }
        return ctx


class PainelDiscenteView(DiscenteRequiredMixin, TemplateView):
    template_name = "painel/discente/painel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        turmas = Turma.objects.filter(
            matricula__discente=self.request.user,
            matricula__status="ATIVA",
            ativa=True,
        ).order_by("-periodo", "nome")
        turma_id = self.request.GET.get("turma", "")
        if turma_id.isdigit():
            turma = get_object_or_404(turmas, pk=int(turma_id))
        else:
            turma = turmas.first()

        ctx["turmas"] = turmas
        ctx["turma"] = turma
        if turma is None:
            return ctx

        linha = indicadores_do_aluno(turma, self.request.user)
        historico = historico_do_aluno(turma, self.request.user)
        ctx["linha"] = linha
        ctx["historico"] = historico
        ctx["dados_grafico"] = {
            "indicadores": [linha[metrica] for metrica in METRICAS],
            "limite": float(turma.limite_atencao),
            "trilhas": [
                {"rotulo": item["trilha"].titulo, "valor": item["percentual"]}
                for item in historico["trilhas"]
            ],
        }
        return ctx


class DefinirLimiteView(DocenteRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        turma = get_object_or_404(Turma, pk=pk, docente=request.user)
        form = LimiteAtencaoForm(request.POST, instance=turma)
        if form.is_valid():
            form.save()
            messages.success(request, "Limite de atenção atualizado.")
        else:
            messages.error(request, "Informe um limite entre 0 e 100.")
        return redirect(f"{reverse('painel:docente')}?turma={turma.pk}")
