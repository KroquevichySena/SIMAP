from collections import defaultdict

from django.utils import timezone

from chamada.models import Chamada, Registro_de_Presenca
from core.models import Atividade, ConclusaoAtividade
from entregas.models import AvaliacaoOficial, Submissao
from turmas.models import Matricula


def _percentual(parte, total):
    if not total:
        return None
    return round(100 * parte / total, 1)


def _dados_da_turma(turma):
    notas = defaultdict(list)
    for aluno_id, nota in AvaliacaoOficial.objects.filter(
        submissao__atividade__trilha__turma=turma
    ).values_list("submissao__aluno_id", "nota"):
        notas[aluno_id].append(nota)

    return {
        "agora": timezone.now(),
        "chamadas": list(
            Chamada.objects.filter(turma=turma).values_list("pk", "data_expiracao")
        ),
        "presencas": set(
            Registro_de_Presenca.objects.filter(chamada__turma=turma).values_list(
                "discente_id", "chamada_id"
            )
        ),
        "atividades": list(
            Atividade.objects.filter(
                trilha__turma=turma, publicada=True, trilha__publicada=True
            ).values_list("pk", "prazo")
        ),
        "entregas": set(
            Submissao.objects.filter(atividade__trilha__turma=turma).values_list(
                "aluno_id", "atividade_id"
            )
        ),
        "conclusoes": set(
            ConclusaoAtividade.objects.filter(atividade__trilha__turma=turma).values_list(
                "discente_id", "atividade_id"
            )
        ),
        "notas": notas,
    }


def calcular_frequencia(matricula, dados):
    aluno = matricula.discente_id
    consideradas = [
        pk
        for pk, expiracao in dados["chamadas"]
        if (aluno, pk) in dados["presencas"]
        or matricula.data_matricula <= expiracao <= dados["agora"]
    ]
    presentes = sum(1 for pk in consideradas if (aluno, pk) in dados["presencas"])
    return _percentual(presentes, len(consideradas))


def calcular_taxa_entrega(matricula, dados):
    aluno = matricula.discente_id
    consideradas = [
        pk
        for pk, prazo in dados["atividades"]
        if (aluno, pk) in dados["entregas"]
        or (prazo and matricula.data_matricula <= prazo <= dados["agora"])
    ]
    entregues = sum(1 for pk in consideradas if (aluno, pk) in dados["entregas"])
    return _percentual(entregues, len(consideradas))


def calcular_progresso(matricula, dados):
    aluno = matricula.discente_id
    concluidas = sum(
        1 for pk, _ in dados["atividades"] if (aluno, pk) in dados["conclusoes"]
    )
    return _percentual(concluidas, len(dados["atividades"]))


def calcular_media(matricula, dados):
    notas = dados["notas"].get(matricula.discente_id)
    if not notas:
        return None
    return round(sum(notas) / len(notas), 1)


def _indicadores(matricula, dados, limite):
    valores = {
        "frequencia": calcular_frequencia(matricula, dados),
        "entregas": calcular_taxa_entrega(matricula, dados),
        "progresso": calcular_progresso(matricula, dados),
    }
    abaixo = {
        nome for nome, valor in valores.items() if valor is not None and valor < limite
    }
    return {
        "discente": matricula.discente,
        **valores,
        "media": calcular_media(matricula, dados),
        "abaixo": abaixo,
        "em_atencao": bool(abaixo),
    }


def indicadores_da_turma(turma):
    dados = _dados_da_turma(turma)
    limite = float(turma.limite_atencao)
    matriculas = (
        Matricula.objects.filter(turma=turma, status="ATIVA")
        .select_related("discente")
        .order_by("discente__first_name", "discente__username")
    )
    linhas = [_indicadores(matricula, dados, limite) for matricula in matriculas]
    return sorted(linhas, key=lambda linha: not linha["em_atencao"])


def listar_alunos_em_atencao(turma):
    return [linha for linha in indicadores_da_turma(turma) if linha["em_atencao"]]


def indicadores_do_aluno(turma, discente):
    matricula = (
        Matricula.objects.filter(turma=turma, discente=discente, status="ATIVA")
        .select_related("discente")
        .first()
    )
    if matricula is None:
        return None
    return _indicadores(matricula, _dados_da_turma(turma), float(turma.limite_atencao))
