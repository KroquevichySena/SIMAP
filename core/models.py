"""
Entidades do núcleo acadêmico do SIMAP:
Turma, Matrícula, Trilha de Aprendizagem e Atividade.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone



# CHOICES (smallint)

MATRICULA_ATIVA = 1
MATRICULA_TRANCADA = 2
MATRICULA_CANCELADA = 3

STATUS_MATRICULA_CHOICES = (
    (MATRICULA_ATIVA, "Ativa"),
    (MATRICULA_TRANCADA, "Trancada"),
    (MATRICULA_CANCELADA, "Cancelada"),
)

TIPO_TEORICA = 1
TIPO_PRATICA = 2  # Reservado para versões futuras (exige sandbox)

TIPO_ATIVIDADE_CHOICES = (
    (TIPO_TEORICA, "Teórica"),
    (TIPO_PRATICA, "Prática (código)"),
)


class Turma(models.Model):
    """Turma criada e gerenciada por um Docente."""

    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # Impede exclusão de docente com turmas vinculadas
        related_name="turmas_ministradas",
        limit_choices_to={"perfil": 'DOCENTE', "is_active": True},
        verbose_name="Docente responsável",
    )

    nome = models.CharField("Nome da turma", max_length=100)
    periodo = models.CharField("Período", max_length=20, help_text="Ex.: 2026/1")
    ativa = models.BooleanField("Turma ativa", default=True, db_index=True)
    data_criacao = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        ordering = ["-periodo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["docente", "nome", "periodo"],
                name="uq_turma_docente_nome_periodo",
            ),
        ]

    def __str__(self):
        return f"{self.nome} - {self.periodo}"

    def clean(self):
        """Garante integridade semântica: o responsável deve ter perfil Docente."""
        super().clean()
        if self.docente_id and self.docente.perfil != 'DOCENTE':
            raise ValidationError({"docente": "O responsável pela turma deve ter perfil Docente."})


class Matricula(models.Model):
    """Vínculo entre um Discente e uma Turma."""

    turma = models.ForeignKey(
        Turma, on_delete=models.CASCADE, related_name="matriculas", verbose_name="Turma"
    )

    discente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="matriculas",
        limit_choices_to={"perfil": 'DISCENTE', "is_active": True},
        verbose_name="Discente",
    )

    status = models.SmallIntegerField(
        "Situação", choices=STATUS_MATRICULA_CHOICES, default=MATRICULA_ATIVA, db_index=True
    )
    data_matricula = models.DateField("Data da matrícula", default=timezone.localdate)

    class Meta:
        verbose_name = "Matrícula"
        verbose_name_plural = "Matrículas"
        # 1ª ALTERAÇÃO: mudou de 'discente__nome' para 'discente__first_name'
        ordering = ["turma", "discente__first_name"] 
        constraints = [
            # Impede matrícula duplicada do mesmo aluno na mesma turma
            models.UniqueConstraint(
                fields=["turma", "discente"], name="uq_matricula_turma_discente"
            ),
        ]
        indexes = [
            # Otimiza a consulta principal do discente (turmas ativas dele)
            models.Index(fields=["discente", "status"], name="idx_matricula_discente_status"),
        ]

    def __str__(self):
        # 2ª ALTERAÇÃO: mudou de 'self.discente.nome' para 'self.discente.first_name'
        return f"{self.discente.first_name} em {self.turma}"

    def clean(self):
        super().clean()
        if self.discente_id and self.discente.perfil != 'DISCENTE':
            raise ValidationError({"discente": "Somente usuários com perfil Discente podem ser matriculados."})


class TrilhaAprendizagem(models.Model):
    """Agrupamento ordenado de atividades dentro de uma turma."""

    turma = models.ForeignKey(
        Turma, on_delete=models.CASCADE, related_name="trilhas", verbose_name="Turma"
    )

    titulo = models.CharField("Título da trilha", max_length=150)
    descricao = models.TextField("Descrição", blank=True)
    ordem = models.SmallIntegerField(
        "Ordem de exibição", default=1, help_text="Menor número aparece primeiro."
    )
    publicada = models.BooleanField(
        "Visível aos discentes", default=True,
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
                condition=models.Q(ordem__gte=0), name="ck_trilha_ordem_nao_negativa"
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
    tipo = models.SmallIntegerField(
        "Tipo", choices=TIPO_ATIVIDADE_CHOICES, default=TIPO_TEORICA
    )
    ordem = models.SmallIntegerField("Ordem de exibição", default=1)
    prazo = models.DateTimeField(
        "Prazo de entrega", null=True, blank=True,
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
                condition=models.Q(ordem__gte=0), name="ck_atividade_ordem_nao_negativa"
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