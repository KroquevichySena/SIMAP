"""
Funcionalidade 7 — Trilhas de Aprendizagem e Publicação de Atividades.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from turmas.models import Turma

TIPO_TEORICA = 'TEORICA'
TIPO_PRATICA = 'PRATICA'  # reservado para versão futura (exige sandbox)

TIPO_ATIVIDADE_CHOICES = (
    (TIPO_TEORICA, "Teórica"),
    (TIPO_PRATICA, "Prática (código)"),
)


class TrilhaAprendizagem(models.Model):
    """Agrupamento ordenado de atividades dentro de uma turma."""

    turma = models.ForeignKey(
        Turma,
        on_delete=models.CASCADE,
        related_name="trilhas",
        verbose_name="Turma",
    )
    titulo = models.CharField("Título da trilha", max_length=150)
    descricao = models.TextField("Descrição", blank=True)
    ordem = models.SmallIntegerField(
        "Ordem de exibição", default=1, help_text="Menor número aparece primeiro."
    )
    publicada = models.BooleanField(
        "Visível aos discentes",
        default=True,
        help_text="Desmarque para preparar a trilha sem exibi-la aos alunos.",
    )
    data_criacao = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Trilha de aprendizagem"
        verbose_name_plural = "Trilhas de aprendizagem"
        ordering = ["ordem", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["turma", "titulo"], name="uq_trilha_turma_titulo"
            ),
            models.CheckConstraint(
                condition=models.Q(ordem__gte=0),
                name="ck_trilha_ordem_nao_negativa",
            ),
        ]
        indexes = [
            models.Index(fields=["turma", "ordem"], name="idx_trilha_turma_ordem"),
        ]

    def __str__(self):
        return self.titulo

    @property
    def total_atividades(self) -> int:
        return self.atividades.count()


class Atividade(models.Model):
    """Atividade publicada pelo docente dentro de uma trilha."""

    trilha = models.ForeignKey(
        TrilhaAprendizagem,
        on_delete=models.CASCADE,
        related_name="atividades",
        verbose_name="Trilha",
    )
    titulo = models.CharField("Título", max_length=150)
    enunciado = models.TextField("Enunciado")
    tipo = models.CharField(
        "Tipo", max_length=10, choices=TIPO_ATIVIDADE_CHOICES, default=TIPO_TEORICA
    )
    ordem = models.SmallIntegerField("Ordem de exibição", default=1)
    prazo = models.DateTimeField(
        "Prazo de entrega",
        null=True,
        blank=True,
        help_text="Opcional. Deixe em branco para atividade sem prazo.",
    )
    publicada = models.BooleanField("Visível aos discentes", default=True)
    data_criacao = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Atividade"
        verbose_name_plural = "Atividades"
        ordering = ["ordem", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["trilha", "titulo"], name="uq_atividade_trilha_titulo"
            ),
            models.CheckConstraint(
                condition=models.Q(ordem__gte=0),
                name="ck_atividade_ordem_nao_negativa",
            ),
        ]
        indexes = [
            models.Index(fields=["trilha", "ordem"], name="idx_atividade_trilha_ordem"),
        ]

    def __str__(self):
        return self.titulo

    @property
    def prazo_expirado(self) -> bool:
        return bool(self.prazo and self.prazo < timezone.now())


class ConclusaoAtividade(models.Model):
    """
    Registro de progresso do discente: uma linha por atividade concluída.
    Atende ao critério de aceitação "progresso registrado por atividade concluída".
    """

    atividade = models.ForeignKey(
        Atividade,
        on_delete=models.CASCADE,
        related_name="conclusoes",
        verbose_name="Atividade",
    )
    discente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="atividades_concluidas",
        verbose_name="Discente",
    )
    data_conclusao = models.DateTimeField("Concluída em", auto_now_add=True)

    class Meta:
        verbose_name = "Conclusão de atividade"
        verbose_name_plural = "Conclusões de atividades"
        ordering = ["-data_conclusao"]
        constraints = [
            # Impede contagem duplicada de progresso para a mesma atividade
            models.UniqueConstraint(
                fields=["atividade", "discente"], name="uq_conclusao_atividade_discente"
            ),
        ]
        indexes = [
            models.Index(
                fields=["discente", "atividade"], name="idx_conclusao_disc_ativ"
            ),
        ]

    def __str__(self):
        return f"{self.discente} - {self.atividade}"
