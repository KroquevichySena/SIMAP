"""
Regras para registrar uma presença na chamada por QR code.

Recusa é quando há certeza: a presença não é gravada.
Sinal é quando há só suspeita: a presença é gravada em análise
e o professor decide depois se aceita ou recusa.
"""
import math
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from turmas.models import Matricula

from .models import Chamada, Registro_de_Presenca

TEMPO_PARA_CONFIRMAR = timedelta(minutes=3)


class PresencaRecusada(Exception):
    pass


def distancia_metros(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = (math.radians(float(v)) for v in (lat1, lng1, lat2, lng2))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return round(6371000 * 2 * math.asin(math.sqrt(a)))


def _motivo_da_localizacao(instituicao, localizacao):
    """Devolve (motivo, distância). O motivo fica vazio quando está tudo certo."""
    if instituicao is None or not instituicao.tem_localizacao:
        return "", None
    if localizacao is None:
        return "Localização não autorizada", None
    if localizacao["precisao"] > instituicao.precisao_minima:
        return f"Localização imprecisa (erro de {round(localizacao['precisao'])} m)", None

    distancia = distancia_metros(
        instituicao.latitude, instituicao.longitude, localizacao["latitude"], localizacao["longitude"]
    )
    if distancia > instituicao.raio_metros:
        return f"Fora do raio ({distancia} m da instituição)", distancia
    return "", distancia


def registrar_presenca(chamada_id, aluno, lido_em, origem, dispositivo="", localizacao=None):
    if timezone.now() - lido_em > TEMPO_PARA_CONFIRMAR:
        raise PresencaRecusada("O tempo para confirmar acabou. Leia o QR code que está na tela agora.")

    with transaction.atomic():
        # select_for_update segura a chamada até o fim: dois alunos ao mesmo
        # tempo não passam juntos pela conferência do limite.
        chamada = Chamada.objects.select_for_update().select_related("turma__instituicao").get(pk=chamada_id)

        if chamada.finalizada_em:
            raise PresencaRecusada("Esta chamada já foi finalizada pelo professor.")
        if not Matricula.objects.filter(turma=chamada.turma, discente=aluno, status="ATIVA").exists():
            raise PresencaRecusada("Você não tem matrícula ativa nesta turma.")
        if chamada.presencas.filter(discente=aluno).exists():
            raise PresencaRecusada("Você já registrou presença nesta chamada.")

        validas = chamada.presencas.exclude(situacao=Registro_de_Presenca.RECUSADA)
        if validas.count() >= chamada.limite_uso:
            raise PresencaRecusada("O limite de presenças desta chamada foi atingido. Fale com o professor.")

        motivos = []
        if dispositivo:
            outro = validas.filter(dispositivo=dispositivo).select_related("discente").first()
            if outro:
                nome = outro.discente.get_full_name() or outro.discente.username
                motivos.append(f"Mesmo celular de {nome}")

        motivo_local, distancia = _motivo_da_localizacao(chamada.turma.instituicao, localizacao)
        if motivo_local:
            motivos.append(motivo_local)

        return Registro_de_Presenca.objects.create(
            chamada=chamada,
            discente=aluno,
            origem=origem,
            dispositivo=dispositivo,
            distancia_m=distancia,
            situacao=Registro_de_Presenca.EM_ANALISE if motivos else Registro_de_Presenca.CONFIRMADA,
            motivo="; ".join(motivos),
        )
