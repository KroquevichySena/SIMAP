from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from usuarios.mixins import CoordenacaoRequiredMixin

from .forms import InstituicaoForm, LimiteAtencaoForm, MatriculaForm, TurmaDaInstituicaoForm, TurmaForm
from .models import Instituicao, Matricula, Turma
from .permissoes import docente_required


@login_required
def lista_turmas(request):
    if request.user.is_docente:
        turmas = Turma.objects.filter(docente=request.user)
    elif request.user.is_discente:
        turmas = Turma.objects.filter(
            matricula__discente=request.user,
            matricula__status='ATIVA',
        )
    else:
        turmas = Turma.objects.none()
    return render(request, 'turmas/lista.html', {'turmas': turmas})
@login_required
@docente_required
def criar_turma(request):
    if request.method == 'POST':
        form = TurmaForm(request.POST)
        if form.is_valid():
            turma = form.save(commit=False)
            turma.docente = request.user
            turma.save()
            return redirect('lista_turmas')
    else:
        form = TurmaForm()
    return render(request, 'turmas/form.html', {'form': form})
@login_required
@docente_required
def criar_matricula(request):
    if request.method == 'POST':
        form = MatriculaForm(request.POST, docente=request.user)
        if form.is_valid():
            form.save()
            return redirect('lista_turmas')
    else:
        form = MatriculaForm(docente=request.user)
    return render(request, 'turmas/matricula_form.html', {'form': form})
@login_required
@docente_required
def matriculas_turma(request, pk):
    turma = get_object_or_404(Turma, pk=pk, docente=request.user)
    matriculas = turma.matricula_set.select_related('discente').order_by('discente__first_name')
    return render(request, 'turmas/matriculas.html', {'turma': turma, 'matriculas': matriculas})
@login_required
@docente_required
@require_POST
def alterar_status_matricula(request, pk):
    matricula = get_object_or_404(Matricula, pk=pk, turma__docente=request.user)
    matricula.status = 'INATIVA' if matricula.status == 'ATIVA' else 'ATIVA'
    matricula.save(update_fields=['status'])
    return redirect('matriculas_turma', pk=matricula.turma_id)


@login_required
@docente_required
def configurar_turma(request, pk):
    turma = get_object_or_404(Turma, pk=pk, docente=request.user)
    form = LimiteAtencaoForm(request.POST if request.method == 'POST' else None, instance=turma)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Limite de atenção da turma atualizado.')
        return redirect('configurar_turma', pk=turma.pk)
    return render(request, 'turmas/configuracoes.html', {'turma': turma, 'form': form})


class InstituicaoListView(CoordenacaoRequiredMixin, ListView):
    template_name = "turmas/instituicoes.html"
    context_object_name = "instituicoes"

    def get_queryset(self):
        return Instituicao.objects.annotate(total_turmas=Count("turmas")).order_by("nome")


class InstituicaoFormMixin(CoordenacaoRequiredMixin):
    model = Instituicao
    form_class = InstituicaoForm
    template_name = "turmas/instituicao_form.html"
    mensagem = ""

    def get_success_url(self):
        # Depois de salvar, a coordenação continua na instituição para cadastrar as turmas.
        return reverse("editar_instituicao", args=[self.object.pk])

    def form_valid(self, form):
        # A instituição e os vínculos das turmas são salvos juntos, ou nada é salvo.
        with transaction.atomic():
            resposta = super().form_valid(form)
        messages.success(self.request, self.mensagem)
        return resposta


class InstituicaoCreateView(InstituicaoFormMixin, CreateView):
    mensagem = "Instituição cadastrada. Agora cadastre as turmas dela."


class InstituicaoUpdateView(InstituicaoFormMixin, UpdateView):
    mensagem = "Instituição atualizada."


class TurmaDaInstituicaoCreateView(CoordenacaoRequiredMixin, CreateView):
    form_class = TurmaDaInstituicaoForm
    template_name = "turmas/turma_instituicao_form.html"

    @cached_property
    def instituicao(self):
        # Buscada só depois do mixin conferir o perfil, para quem não é coordenação receber 403.
        return get_object_or_404(Instituicao, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        return super().get_context_data(instituicao=self.instituicao, **kwargs)

    def form_valid(self, form):
        form.instance.instituicao = self.instituicao
        resposta = super().form_valid(form)
        messages.success(self.request, f"Turma {self.object} cadastrada em {self.instituicao}.")
        return resposta

    def get_success_url(self):
        return reverse("editar_instituicao", args=[self.instituicao.pk])
