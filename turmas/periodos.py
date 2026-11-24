"""
Semestres letivos oferecidos no cadastro de turmas.

O período é escolhido numa lista, no formato "AAAA/S" (ano e semestre), em vez
de digitado: assim todas as turmas usam o mesmo formato. A lista começa no
semestre atual (não aceita semestres que já passaram) e vai até o fim do
próximo ano; o semestre atual vem selecionado nas turmas novas.
"""
from django.utils import timezone


def periodo_atual(hoje=None):
    hoje = hoje or timezone.localdate()
    return f"{hoje.year}/{1 if hoje.month <= 6 else 2}"


def opcoes_de_periodo(hoje=None):
    hoje = hoje or timezone.localdate()
    atual = periodo_atual(hoje)
    return [f"{a}/{s}" for a in (hoje.year, hoje.year + 1) for s in (1, 2) if f"{a}/{s}" >= atual]
