from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from core.mixins import DocenteRequiredMixin
from turmas.models import Turma

from .forms import LimiteAtencaoForm
from .servicos import dados_do_grafico, indicadores_da_turma, resumo_da_turma


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
