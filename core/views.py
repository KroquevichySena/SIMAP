"""
Views do SIMAP - Funcionalidade 7 (Trilhas e Publicação de Atividades).

Padrão de segurança adotado:
  1) Mixin de perfil  -> controla QUEM entra na rota (RBAC).
  2) get_queryset()   -> controla QUAIS objetos o usuário vê/edita (anti-IDOR).
  3) form_kwargs      -> controla A QUAIS objetos ele pode vincular (anti-tampering).
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView, View

from entregas.models import Submissao
from turmas.models import Matricula


from .forms import AtividadeForm, TrilhaAprendizagemForm
from .mixins import DiscenteRequiredMixin, DocenteRequiredMixin
from .models import (
    Atividade,
    ConclusaoAtividade,
    TrilhaAprendizagem,
)


# DASHBOARD — roteia o usuário conforme o perfil

class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    """Ponto de entrada pós-login: encaminha para a área correta."""

    def get(self, request, *args, **kwargs):
        if request.user.is_docente:
            return redirect("core:trilha_list")
        return redirect("core:minhas_trilhas")


class TrilhaListView(DocenteRequiredMixin, ListView):
    """Listagem gerencial das trilhas do docente logado."""

    model = TrilhaAprendizagem
    template_name = "core/docente/trilha_list.html"
    context_object_name = "trilhas"
    paginate_by = 15

    def get_queryset(self):
        # ANTI-IDOR: retorna apenas trilhas das turmas do próprio docente
        return (
            TrilhaAprendizagem.objects.filter(turma__docente=self.request.user)
            .select_related("turma")
            .annotate(qtd_atividades=Count("atividades"))
            .order_by("turma__nome", "ordem", "id")
        )


class TrilhaCreateView(DocenteRequiredMixin, CreateView):
    model = TrilhaAprendizagem
    form_class = TrilhaAprendizagemForm
    template_name = "core/docente/trilha_form.html"
    success_url = reverse_lazy("core:trilha_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["docente"] = self.request.user  # Restringe o queryset de 'turma'
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Trilha criada com sucesso.")
        return super().form_valid(form)


class TrilhaUpdateView(DocenteRequiredMixin, UpdateView):
    model = TrilhaAprendizagem
    form_class = TrilhaAprendizagemForm
    template_name = "core/docente/trilha_form.html"
    success_url = reverse_lazy("core:trilha_list")

    def get_queryset(self):
        # ANTI-IDOR: impede editar trilha de outro docente pela URL
        return TrilhaAprendizagem.objects.filter(turma__docente=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["docente"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Trilha atualizada com sucesso.")
        return super().form_valid(form)


class TrilhaDeleteView(DocenteRequiredMixin, DeleteView):
    model = TrilhaAprendizagem
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("core:trilha_list")

    def get_queryset(self):
        return TrilhaAprendizagem.objects.filter(turma__docente=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Trilha excluída com sucesso.")
        return super().form_valid(form)

class AtividadeListView(DocenteRequiredMixin, ListView):
    model = Atividade
    template_name = "core/docente/atividade_list.html"
    context_object_name = "atividades"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Atividade.objects.filter(trilha__turma__docente=self.request.user)
            .select_related("trilha", "trilha__turma")
            .annotate(qtd_concluidas=Count("conclusoes", distinct=True))
            .order_by("trilha__turma__nome", "trilha__ordem", "ordem", "id")
        )
        trilha_id = self.request.GET.get("trilha")
        if trilha_id and trilha_id.isdigit():
            qs = qs.filter(trilha_id=int(trilha_id))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trilhas_disponiveis"] = TrilhaAprendizagem.objects.filter(
            turma__docente=self.request.user
        ).select_related("turma").order_by("turma__nome", "ordem")
        ctx["trilha_selecionada"] = self.request.GET.get("trilha", "")
        return ctx


class AtividadeCreateView(DocenteRequiredMixin, CreateView):
    model = Atividade
    form_class = AtividadeForm
    template_name = "core/docente/atividade_form.html"
    success_url = reverse_lazy("core:atividade_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["docente"] = self.request.user  
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Pré-seleciona a trilha se vier pela query string (validando a posse)
        trilha_id = self.request.GET.get("trilha")
        if trilha_id and trilha_id.isdigit():
            if TrilhaAprendizagem.objects.filter(
                pk=int(trilha_id), turma__docente=self.request.user
            ).exists():
                initial["trilha"] = int(trilha_id)
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Atividade publicada com sucesso.")
        return super().form_valid(form)


class AtividadeUpdateView(DocenteRequiredMixin, UpdateView):
    model = Atividade
    form_class = AtividadeForm
    template_name = "core/docente/atividade_form.html"
    success_url = reverse_lazy("core:atividade_list")

    def get_queryset(self):
        return Atividade.objects.filter(trilha__turma__docente=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["docente"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Atividade atualizada com sucesso.")
        return super().form_valid(form)


class AtividadeDeleteView(DocenteRequiredMixin, DeleteView):
    model = Atividade
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("core:atividade_list")

    def get_queryset(self):
        return Atividade.objects.filter(trilha__turma__docente=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Atividade excluída com sucesso.")
        return super().form_valid(form)


# ÁREA DO DISCENTE — visualização das trilhas das turmas em que está matriculado

class MinhasTrilhasListView(DiscenteRequiredMixin, ListView):
    """Exibe apenas trilhas publicadas de turmas ativas nas quais o discente
    possui matrícula com status ATIVA (critério de aceitação da Funcionalidade 7).
    """

    model = TrilhaAprendizagem
    template_name = "core/discente/minhas_trilhas.html"
    context_object_name = "trilhas"

    def get_queryset(self):
        usuario = self.request.user

        # Subconjunto de turmas em que o aluno está efetivamente matriculado
        turmas_do_aluno = Matricula.objects.filter(
            discente=usuario, status='ATIVA', turma__ativa=True
        ).values_list("turma_id", flat=True)

        # Prefetch traz somente atividades publicadas, já ordenadas
        atividades_publicadas = Prefetch(
            "atividades",
            queryset=Atividade.objects.filter(publicada=True).order_by("ordem", "id"),
            to_attr="atividades_visiveis",
        )

        return (
            TrilhaAprendizagem.objects.filter(
                turma_id__in=turmas_do_aluno, publicada=True
            )
            .select_related("turma", "turma__docente")
            .prefetch_related(atividades_publicadas)
            .order_by("turma__nome", "ordem", "id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_turmas"] = (
            Matricula.objects.filter(
                discente=self.request.user, status='ATIVA', turma__ativa=True
            ).count()
        )

        concluidas = set(
            ConclusaoAtividade.objects.filter(
                discente=self.request.user
            ).values_list("atividade_id", flat=True)
        )
        enviadas = {
            s.atividade_id: s
            for s in Submissao.objects.filter(aluno=self.request.user).select_related(
                "avaliacao_oficial"
            )
        }


        total_geral = 0
        concluidas_geral = 0
        for trilha in ctx["trilhas"]:
            visiveis = trilha.atividades_visiveis
            for atividade in visiveis:
                atividade.concluida = atividade.pk in concluidas
                atividade.submissao = enviadas.get(atividade.pk)


            trilha.total_visiveis = len(visiveis)
            trilha.total_concluidas = sum(1 for a in visiveis if a.concluida)
            trilha.percentual = (
                round(100 * trilha.total_concluidas / trilha.total_visiveis)
                if trilha.total_visiveis
                else 0
            )
            total_geral += trilha.total_visiveis
            concluidas_geral += trilha.total_concluidas

        ctx["total_atividades"] = total_geral
        ctx["total_concluidas"] = concluidas_geral
        ctx["percentual_geral"] = (
            round(100 * concluidas_geral / total_geral) if total_geral else 0
        )
        return ctx


class ConcluirAtividadeView(DiscenteRequiredMixin, View):
    """
    Marca / desmarca uma atividade como concluída pelo discente logado.
    Aceita apenas POST (ação com efeito colateral exige CSRF + método seguro).
    """

    def post(self, request, pk, *args, **kwargs):
        # ANTI-IDOR: a atividade precisa estar publicada, em trilha publicada,
        # de uma turma ativa onde o aluno tenha matrícula ativa.
        atividade = get_object_or_404(
            Atividade.objects.filter(
                publicada=True,
                trilha__publicada=True,
                trilha__turma__ativa=True,
                trilha__turma__matricula__discente=request.user,
                trilha__turma__matricula__status='ATIVA',
            ),
            pk=pk,
        )

        conclusao, criada = ConclusaoAtividade.objects.get_or_create(
            atividade=atividade, discente=request.user
        )
        if criada:
            messages.success(request, f"Atividade “{atividade.titulo}” concluída.")
        else:
            conclusao.delete()
            messages.info(request, f"Conclusão de “{atividade.titulo}” desfeita.")
        return redirect("core:minhas_trilhas")
