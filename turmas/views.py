from .models import Turma
from django.shortcuts import render, redirect
from .forms import TurmaForm

def lista_turmas(request):
    turmas = Turma.objects.all()
    return render(request, 'turmas/lista.html', {'turmas': turmas})
def criar_turma(request):
    if request.method == 'POST':
        form = TurmaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_turmas')
    else:
        form = TurmaForm()
    return render(request, 'turmas/form.html', {'form': form})