from .models import Turma
from django.shortcuts import render, redirect
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
        form = MatriculaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_turmas')
    else:
        form = MatriculaForm()
    return render(request, 'turmas/matricula_form.html', {'form': form})          