from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import AbrirChamadaForm, ConfirmarPresencaForm
from .models import Chamada

@login_required
def abrir_chamada(request):
    """View para o professor abrir chamadas e acompanhar os registros em tempo real."""
    
    if request.user.perfil != 'DOCENTE':
        messages.error(request, "Apenas professores podem abrir chamadas.")
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = AbrirChamadaForm(request.POST, professor=request.user)
        if form.is_valid():
            chamada = form.save()
            messages.success(
                request,
                f"Chamada '{chamada.token_chamada}' aberta com sucesso para a turma {chamada.turma.nome}!"
            )
            return redirect('chamada:abrir_chamada')
    else:
        form = AbrirChamadaForm(professor=request.user)

    chamadas_recentes = Chamada.objects.filter(
        turma__docente=request.user
    ).select_related('turma').prefetch_related('presencas').order_by('-data_criacao')[:10]

    context = {
        'form': form,
        'chamadas_recentes': chamadas_recentes,
        'titulo_pagina': 'Gestão de Chamadas'
    }
    return render(request, 'chamada/abrir_chamada.html', context)
     

def confirmar_presenca(request):
    if request.method == 'POST':
        form = ConfirmarPresencaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Presença confirmada com sucesso!")
            return redirect('chamada:confirmar_presenca')
    else:
        form = ConfirmarPresencaForm()

    context = {
        'form': form,
        'titulo_pagina': 'Confirmar Presença',
    }
    return render(request, 'chamada/confirmar_presenca.html', context)
