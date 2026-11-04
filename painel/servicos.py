from collections import defaultdict

from django.utils import timezone

from chamada.models import Chamada, Registro_de_Presenca
from core.models import Atividade, ConclusaoAtividade
from entregas.models import AvaliacaoOficial, Submissao
from turmas.models import Matricula

METRICAS = ("frequencia", "entregas", "progresso")


def _percentual(parte, total):
    if not total:
        return None
    return round(100 * parte / total, 1)


def _media(valores):
    valores = [valor for valor in valores if valor is not None]
    if not valores:
        return None
    return round(sum(valores) / len(valores), 1)


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


def _contar(matricula, itens, feitos, agora):
    aluno = matricula.discente_id
    considerados = [
        pk
        for pk, data_limite in itens
        if (aluno, pk) in feitos
        or (data_limite and matricula.data_matricula <= data_limite <= agora)
    ]
    realizados = sum(1 for pk in considerados if (aluno, pk) in feitos)
    return realizados, len(considerados)


def contar_faltas(matricula, dados):
    presentes, total = _contar(
        matricula, dados["chamadas"], dados["presencas"], dados["agora"]
    )
    return total - presentes


def calcular_frequencia(matricula, dados):
    return _percentual(
        *_contar(matricula, dados["chamadas"], dados["presencas"], dados["agora"])
    )


def calcular_taxa_entrega(matricula, dados):
    return _percentual(
        *_contar(matricula, dados["atividades"], dados["entregas"], dados["agora"])
    )


def calcular_progresso(matricula, dados):
    return _percentual(
        *_contar(matricula, dados["atividades"], dados["conclusoes"], dados["agora"])
    )


def calcular_media(matricula, dados):
    return _media(dados["notas"].get(matricula.discente_id, []))


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
        "faltas": contar_faltas(matricula, dados),
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


def resumo_da_turma(linhas):
    resumo = {nome: _media(linha[nome] for linha in linhas) for nome in METRICAS}
    resumo["media"] = _media(linha["media"] for linha in linhas)
    resumo["em_atencao"] = sum(1 for linha in linhas if linha["em_atencao"])
    resumo["total"] = len(linhas)
    return resumo


def evolucao_da_turma(turma):
    dados = _dados_da_turma(turma)
    matriculas = dict(
        Matricula.objects.filter(turma=turma, status="ATIVA").values_list(
            "discente_id", "data_matricula"
        )
    )
    notas_por_atividade = defaultdict(list)
    for atividade_id, nota in AvaliacaoOficial.objects.filter(
        submissao__atividade__trilha__turma=turma, submissao__aluno_id__in=matriculas
    ).values_list("submissao__atividade_id", "nota"):
        notas_por_atividade[atividade_id].append(nota)

    pontos = defaultdict(lambda: defaultdict(list))

    def registrar(momento, metrica, feitos, pk):
        esperados = [aluno for aluno, data in matriculas.items() if data <= momento]
        valor = _percentual(
            sum(1 for aluno in esperados if (aluno, pk) in feitos), len(esperados)
        )
        pontos[timezone.localtime(momento).date()][metrica].append(valor)

    for pk, expiracao in dados["chamadas"]:
        if expiracao <= dados["agora"]:
            registrar(expiracao, "frequencia", dados["presencas"], pk)

    for pk, prazo in dados["atividades"]:
        if prazo and prazo <= dados["agora"]:
            registrar(prazo, "entregas", dados["entregas"], pk)
            registrar(prazo, "progresso", dados["conclusoes"], pk)
            pontos[timezone.localtime(prazo).date()]["notas"].append(
                _media(notas_por_atividade[pk])
            )

    dias = sorted(pontos)
    evolucao = {"rotulos": [dia.strftime("%d/%m") for dia in dias]}
    for metrica in (*METRICAS, "notas"):
        evolucao[metrica] = [_media(pontos[dia][metrica]) for dia in dias]
    return evolucao


def dados_do_grafico(turma, linhas):
    alunos = [
        {
            "id": linha["discente"].pk,
            "nome": linha["discente"].get_full_name() or linha["discente"].username,
            "frequencia": linha["frequencia"],
            "faltas": linha["faltas"],
            "entregas": linha["entregas"],
            "progresso": linha["progresso"],
            "notas": float(linha["media"]) if linha["media"] is not None else None,
            "em_atencao": linha["em_atencao"],
        }
        for linha in linhas
    ]
    evolucao = evolucao_da_turma(turma)
    evolucao["notas"] = [float(nota) if nota is not None else None for nota in evolucao["notas"]]
    return {
        "alunos": alunos,
        "evolucao": evolucao,
        "limite": float(turma.limite_atencao),
    }
