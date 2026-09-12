"""
Views do SIMAP - Funcionalidade 7 (Trilhas e Publicação de Atividades).

Padrão de segurança adotado:
  1) Mixin de perfil  -> controla QUEM entra na rota (RBAC).
  2) get_queryset()   -> controla QUAIS objetos o usuário vê/edita (anti-IDOR).
  3) form_kwargs      -> controla A QUAIS objetos ele pode vincular (anti-tampering).
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import AtividadeForm, TrilhaAprendizagemForm
from .mixins import DiscenteRequiredMixin, DocenteRequiredMixin
from .models import (
    MATRICULA_ATIVA,
    Atividade,
    Matricula,
    TrilhaAprendizagem,
)


# DASHBOARD — roteia o usuário conforme o perfil

class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    """Ponto de entrada pós-login: encaminha para a área correta."""

    def get(self, request, *args, **kwargs):
        if request.user.is_docente:
            return redirect("core:trilha_list")
        return redirect("core:minhas_trilhas")


# ÁREA DO DOCENTE — CRUD de Trilhas

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



# ÁREA DO DOCENTE — CRUD de Atividades

class AtividadeListView(DocenteRequiredMixin, ListView):
    model = Atividade
    template_name = "core/docente/atividade_list.html"
    context_object_name = "atividades"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Atividade.objects.filter(trilha__turma__docente=self.request.user)
            .select_related("trilha", "trilha__turma")
            .order_by("trilha__turma__nome", "trilha__ordem", "ordem", "id")
        )
        # Filtro opcional por trilha (validado dentro do escopo do docente)
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
        kwargs["docente"] = self.request.user  # Restringe o queryset de 'trilha'
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
    """
    Exibe apenas trilhas publicadas de turmas ativas nas quais o discente
    possui matrícula com status ATIVA (critério de aceitação da Funcionalidade 7).
    """

    model = TrilhaAprendizagem
    template_name = "core/discente/minhas_trilhas.html"
    context_object_name = "trilhas"

    def get_queryset(self):
        usuario = self.request.user

        # Subconjunto de turmas em que o aluno está efetivamente matriculado
        turmas_do_aluno = Matricula.objects.filter(
            discente=usuario, status=MATRICULA_ATIVA, turma__ativa=True
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
                discente=self.request.user, status=MATRICULA_ATIVA, turma__ativa=True
            ).count()
        )
        return ctx