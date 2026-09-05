from django.shortcuts import render
from .models import Turma

def lista_turmas(request):
    turmas = Turma.objects.all()
    return render(request, 'turmas/lista.html', {'turmas': turmas})