from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from core.models import Atividade


class Submissao(models.Model):
    """Resposta enviada pelo aluno para uma atividade."""

    atividade = models.ForeignKey(
        Atividade,
        on_delete=models.CASCADE,
        related_name="submissoes",
        verbose_name="Atividade",
    )
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissoes",
        limit_choices_to={"perfil": "DISCENTE"},
        verbose_name="Aluno",
    )
    resposta_texto = models.TextField("Resposta")
    data_envio = models.DateTimeField("Enviada em", auto_now_add=True)

    class Meta:
        verbose_name = "Submissão"
        verbose_name_plural = "Submissões"
        ordering = ["-data_envio"]
        constraints = [
            models.UniqueConstraint(
                fields=["atividade", "aluno"], name="uq_submissao_atividade_aluno"
            ),
        ]

    def __str__(self):
        return f"{self.aluno} - {self.atividade}"

    @property
    def is_atrasado(self) -> bool:
        return bool(self.atividade.prazo and self.data_envio > self.atividade.prazo)



STATUS_PENDENTE = "PENDENTE"
STATUS_CONCLUIDO = "CONCLUIDO"
STATUS_ERRO = "ERRO"

STATUS_ANALISE_CHOICES = (
    (STATUS_PENDENTE, "Pendente"),
    (STATUS_CONCLUIDO, "Concluído"),
    (STATUS_ERRO, "Erro de API"),
)


class AnaliseIA(models.Model):
    """Parecer automático gerado pela IA (Gemini) para uma submissão."""

    submissao = models.OneToOneField(
        Submissao,
        on_delete=models.CASCADE,
        related_name="analise_ia",
        verbose_name="Submissão",
    )
    parecer_texto = models.TextField("Parecer", blank=True)
    status = models.CharField(
        "Status", max_length=10, choices=STATUS_ANALISE_CHOICES, default=STATUS_PENDENTE
    )
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Análise de IA"
        verbose_name_plural = "Análises de IA"

    def __str__(self):
        return f"Análise de {self.submissao}"



class AvaliacaoOficial(models.Model):
    """Nota e feedback do docente para uma submissão."""

    submissao = models.OneToOneField(
        Submissao,
        on_delete=models.CASCADE,
        related_name="avaliacao_oficial",
        verbose_name="Submissão",
    )
    nota = models.DecimalField(
        "Nota",
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    feedback_professor = models.TextField("Feedback do professor", blank=True)
    avaliado_em = models.DateTimeField("Avaliado em", auto_now=True)

    class Meta:
        verbose_name = "Avaliação oficial"
        verbose_name_plural = "Avaliações oficiais"

    def __str__(self):
        return f"Nota {self.nota} - {self.submissao}"
