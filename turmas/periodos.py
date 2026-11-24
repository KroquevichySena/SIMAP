"""
Semestres letivos oferecidos no cadastro de turmas.

O período é escolhido numa lista, no formato "AAAA/S" (ano e semestre), em vez
de digitado: assim todas as turmas usam o mesmo formato. A lista vai do ano
anterior ao próximo, e o semestre atual vem selecionado nas turmas novas.
"""
from django.utils import timezone


def periodo_atual(hoje=None):
    hoje = hoje or timezone.localdate()
    return f"{hoje.year}/{1 if hoje.month <= 6 else 2}"


def opcoes_de_periodo(hoje=None):
    ano = (hoje or timezone.localdate()).year
    return [f"{a}/{s}" for a in range(ano - 1, ano + 2) for s in (1, 2)]
