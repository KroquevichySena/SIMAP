"""
Telas da Funcionalidade 7: trilhas de aprendizagem e publicação de atividades.

A segurança aqui funciona em três camadas, uma completando a outra:

1. O mixin de perfil decide quem pode entrar em cada tela (docente ou discente).
2. O get_queryset() decide quais objetos cada um enxerga. Assim, um docente
   não consegue abrir a trilha de outro só trocando o número na URL (IDOR).
3. O form_kwargs limita a quais turmas e trilhas um formulário pode ligar
   um objeto, para ninguém forjar um POST com o ID de uma turma alheia.
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


# Depois do login, cada um vai para a sua área.

class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    """Manda o docente para as trilhas dele e o aluno para as trilhas que ele cursa."""

    def get(self, request, *args, **kwargs):
        if request.user.is_docente:
            return redirect("core:trilha_list")
        return redirect("core:minhas_trilhas")


class TrilhaListView(DocenteRequiredMixin, ListView):
    """Lista as trilhas das turmas do docente que está logado."""

    model = TrilhaAprendizagem
    template_name = "core/docente/trilha_list.html"
    context_object_name = "trilhas"
    paginate_by = 15

    def get_queryset(self):
        # Só as trilhas das turmas do próprio docente, nunca as de outro professor.
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
        # Se alguém trocar o número na URL para a trilha de outro professor,
        # ela não é encontrada aqui e a pessoa recebe 404.
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
        # Se a tela foi aberta a partir de uma trilha, ela já vem selecionada,
        # mas só depois de confirmar que a trilha é mesmo desse docente.
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


# Área do aluno: ele vê só as trilhas das turmas em que está matriculado.

class MinhasTrilhasListView(DiscenteRequiredMixin, ListView):
    """Exibe apenas trilhas publicadas de turmas ativas nas quais o discente
    possui matrícula com status ATIVA (critério de aceitação da Funcionalidade 7).
    """

    model = TrilhaAprendizagem
    template_name = "core/discente/minhas_trilhas.html"
    context_object_name = "trilhas"

    def get_queryset(self):
        usuario = self.request.user

        # As turmas em que o aluno tem matrícula ativa.
        turmas_do_aluno = Matricula.objects.filter(
            discente=usuario, status='ATIVA', turma__ativa=True
        ).values_list("turma_id", flat=True)

        # Já traz as atividades junto, só as publicadas e na ordem certa, para
        # não precisar de uma consulta extra por trilha.
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
    Marca a atividade como concluída, ou desfaz se ela já estava.

    Só aceita POST: como a ação muda dados, ela precisa do token CSRF e não
    pode acontecer só por alguém abrir um link.
    """

    def post(self, request, pk, *args, **kwargs):
        # O aluno só pode concluir uma atividade publicada, de uma trilha
        # publicada, numa turma ativa em que ele esteja matriculado. Qualquer
        # outro ID digitado na URL dá 404.
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
