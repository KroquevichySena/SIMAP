from .models import Turma, Matricula
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .forms import TurmaForm, MatriculaForm
from django.contrib.auth.decorators import login_required
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
