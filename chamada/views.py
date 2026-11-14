import uuid
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from turmas.models import Matricula

from .forms import AbrirChamadaForm, ConfirmarPresencaForm
from .models import Chamada, Registro_de_Presenca
from .servicos import PresencaRecusada, registrar_presenca

COOKIE_APARELHO = "simap_aparelho"
UM_ANO = 60 * 60 * 24 * 365


def _chamada_do_professor(request, pk):
    return get_object_or_404(
        Chamada.objects.select_related("turma"), pk=pk, turma__docente=request.user
    )


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
            messages.success(request, f"Chamada aberta para a turma {chamada.turma.nome}.")
            return redirect('chamada:ao_vivo', pk=chamada.pk)
    else:
        form = AbrirChamadaForm(professor=request.user)

    chamadas = Chamada.objects.filter(
        turma__docente=request.user
    ).select_related('turma').prefetch_related('presencas').order_by('-data_criacao')
    chamadas_recentes = Paginator(chamadas, 10).get_page(request.GET.get('pagina'))

    context = {
        'form': form,
        'chamadas_recentes': chamadas_recentes,
        'titulo_pagina': 'Gestão de Chamadas'
    }
    return render(request, 'chamada/abrir_chamada.html', context)


@login_required
def ao_vivo(request, pk):
    if request.user.perfil != 'DOCENTE':
        messages.error(request, "Apenas professores podem abrir chamadas.")
        return redirect('core:dashboard')

    chamada = _chamada_do_professor(request, pk)
    presencas = list(chamada.presencas.select_related('discente').order_by('-data_registro'))
    com_presenca = {p.discente_id for p in presencas if p.situacao != Registro_de_Presenca.RECUSADA}

    faltas = []
    if chamada.finalizada_em:
        faltas = [
            matricula.discente
            for matricula in Matricula.objects.filter(turma=chamada.turma, status='ATIVA').select_related('discente')
            if matricula.discente_id not in com_presenca
        ]

    context = {
        'chamada': chamada,
        'presencas': presencas,
        'confirmadas': sum(p.situacao == Registro_de_Presenca.CONFIRMADA for p in presencas),
        'em_analise': sum(p.situacao == Registro_de_Presenca.EM_ANALISE for p in presencas),
        'presentes': len(com_presenca),
        'faltas': faltas,
    }
    return render(request, 'chamada/ao_vivo.html', context)


@login_required
def projecao(request, pk):
    if request.user.perfil != 'DOCENTE':
        return redirect('core:dashboard')
    chamada = _chamada_do_professor(request, pk)
    return render(request, 'chamada/projecao.html', {'chamada': chamada})


@login_required
def estado_chamada(request, pk):
    """Consultada a cada poucos segundos pela projeção e pelo painel do professor."""
    if request.user.perfil != 'DOCENTE':
        return JsonResponse({}, status=403)
    chamada = _chamada_do_professor(request, pk)
    restante = (chamada.data_expiracao - timezone.now()).total_seconds()
    return JsonResponse({
        'token': chamada.token_chamada,
        'link': request.build_absolute_uri(reverse('chamada:ler_qr', args=[chamada.token_chamada])),
        'segundos': max(int(restante), 0),
        'aberto': chamada.qr_aberto,
        'finalizada': chamada.finalizada_em is not None,
        'presentes': chamada.presencas.exclude(situacao=Registro_de_Presenca.RECUSADA).count(),
        'limite': chamada.limite_uso,
    })


@login_required
@require_POST
def renovar_chamada(request, pk):
    chamada = _chamada_do_professor(request, pk)
    if chamada.finalizada_em:
        messages.error(request, "Esta chamada já foi finalizada.")
    elif chamada.qr_aberto:
        messages.info(request, "O QR code ainda está valendo.")
    else:
        chamada.renovar()
        messages.success(request, "QR code renovado.")
    return redirect('chamada:ao_vivo', pk=chamada.pk)


@login_required
@require_POST
def finalizar_chamada(request, pk):
    chamada = _chamada_do_professor(request, pk)
    if not chamada.finalizada_em:
        chamada.finalizar()
        messages.success(request, "Chamada finalizada. Revise as presenças em análise.")
    return redirect('chamada:ao_vivo', pk=chamada.pk)


@login_required
@require_POST
def decidir_presenca(request, pk):
    presenca = get_object_or_404(
        Registro_de_Presenca.objects.select_related('chamada'), pk=pk, chamada__turma__docente=request.user
    )
    acao = request.POST.get('acao')
    if acao == 'aceitar':
        presenca.situacao = Registro_de_Presenca.CONFIRMADA
    elif acao == 'recusar':
        presenca.situacao = Registro_de_Presenca.RECUSADA
    presenca.save(update_fields=['situacao'])
    return redirect('chamada:ao_vivo', pk=presenca.chamada_id)


def ler_qr(request, token):
    """Endereço do QR code. Guarda a leitura antes do login, por isso não exige login."""
    chamada = Chamada.objects.filter(token_chamada=token.upper()).first()
    if chamada is None or not chamada.qr_aberto:
        return render(request, 'chamada/resultado.html', {
            'tipo': 'erro',
            'titulo': 'QR code expirado',
            'texto': 'Este QR code não vale mais. Leia o que está na tela do professor agora.',
        })
    request.session['leitura_chamada'] = {
        'chamada': chamada.pk, 'lido_em': timezone.now().isoformat(), 'origem': 'QR',
    }
    return redirect('chamada:confirmar_leitura')


@login_required
def confirmar_presenca(request):

    if request.user.perfil != 'DISCENTE':
        messages.error(request, "Apenas discentes podem confirmar presença.")
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = ConfirmarPresencaForm(request.POST, discente=request.user)
        if form.is_valid():
            request.session['leitura_chamada'] = {
                'chamada': form.chamada.pk, 'lido_em': timezone.now().isoformat(), 'origem': 'CODIGO',
            }
            return redirect('chamada:confirmar_leitura')
    else:
        form = ConfirmarPresencaForm(discente=request.user)

    context = {
        'form': form,
        'titulo_pagina': 'Confirmar Presença',
    }
    return render(request, 'chamada/confirmar_presenca.html', context)


def _ler_localizacao(dados):
    try:
        return {
            'latitude': float(dados['latitude']),
            'longitude': float(dados['longitude']),
            'precisao': float(dados['precisao']),
        }
    except (KeyError, ValueError):
        return None


@login_required
def confirmar_leitura(request):
    if request.user.perfil != 'DISCENTE':
        messages.error(request, "Apenas discentes podem confirmar presença.")
        return redirect('core:dashboard')

    leitura = request.session.get('leitura_chamada')
    if not leitura:
        messages.info(request, "Leia o QR code da tela do professor ou digite o código.")
        return redirect('chamada:confirmar_presenca')

    chamada = get_object_or_404(Chamada.objects.select_related('turma__instituicao'), pk=leitura['chamada'])

    if request.method != 'POST':
        instituicao = chamada.turma.instituicao
        return render(request, 'chamada/confirmar_leitura.html', {
            'chamada': chamada,
            'pedir_localizacao': instituicao is not None and instituicao.tem_localizacao,
        })

    del request.session['leitura_chamada']
    aparelho = request.get_signed_cookie(COOKIE_APARELHO, default=None) or str(uuid.uuid4())
    try:
        presenca = registrar_presenca(
            chamada.pk,
            request.user,
            lido_em=datetime.fromisoformat(leitura['lido_em']),
            origem=leitura['origem'],
            dispositivo=aparelho,
            localizacao=_ler_localizacao(request.POST),
        )
    except PresencaRecusada as erro:
        contexto = {'tipo': 'erro', 'titulo': 'Presença não registrada', 'texto': str(erro)}
    else:
        if presenca.situacao == Registro_de_Presenca.EM_ANALISE:
            contexto = {
                'tipo': 'analise',
                'titulo': 'Presença registrada, em análise',
                'texto': f"{presenca.motivo}. O professor vai confirmar.",
            }
        else:
            contexto = {
                "tipo": "ok",
                "titulo": "Presença registrada",
                "texto": (
                    f"{chamada.turma.nome} · {timezone.localtime(presenca.data_registro):%H:%M}. "
                    "Pode guardar o celular."
                ),
            }

    resposta = render(request, "chamada/resultado.html", contexto)
    resposta.set_signed_cookie(
        COOKIE_APARELHO,
        aparelho,
        max_age=UM_ANO,
        httponly=True,
        secure=request.is_secure(),
        samesite="Lax",
    )
    return resposta
