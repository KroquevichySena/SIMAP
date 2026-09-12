from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import AbrirChamadaForm

@login_required
def abrir_chamada(request):
    if request.user.perfil != 'DOCENTE':
        messages.error(request, "Apenas professores podem abrir chamadas.")
        return redirect('core:dashboard')
  

    if request.method == 'POST':
        form = AbrirChamadaForm(request.POST, professor=request.user)
        if form.is_valid():
            chamada = form.save()
            messages.success(request, f"Chamada {chamada.token_chamada} aberta com sucesso para a turma {chamada.turma.nome}.")
            return redirect('chamada:abrir_chamada')
    else:
        form = AbrirChamadaForm(professor=request.user)

    context = {
        'form': form,
        'titulo_pagina': 'Abrir Nova Chamada'
    }
    
    # Renderiza o HTML enviando o formulário pronto
    return render(request, 'chamada/abrir_chamada.html', context)   