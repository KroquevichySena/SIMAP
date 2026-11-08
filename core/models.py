"""
Os modelos das trilhas de aprendizagem: a trilha, as atividades dentro dela
e o registro de quais atividades cada aluno já concluiu.

Turma e matrícula ficam no app turmas.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from comunicacao.models import ArquivoSeguro

from . import youtube


TIPO_TEORICA = 'TEORICA'
TIPO_PRATICA = 'PRATICA'  # Reservado para versões futuras (exige sandbox)

TIPO_ATIVIDADE_CHOICES = (
    (TIPO_TEORICA, "Teórica"),
    (TIPO_PRATICA, "Prática (código)"),
)


class TrilhaAprendizagem(models.Model):
    """Um módulo da turma, com as atividades em sequência (ex.: "Módulo 1 - Variáveis")."""

    turma = models.ForeignKey(
        "turmas.Turma", on_delete=models.CASCADE, related_name="trilhas", verbose_name="Turma"
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
    """Uma atividade que o docente publica dentro de uma trilha."""

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


class ConclusaoAtividade(models.Model):
    """
    O progresso do aluno: cada linha diz que ele concluiu uma atividade.
    Para saber o percentual de uma trilha, basta contar essas linhas.
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
        limit_choices_to={"perfil": 'DISCENTE', "is_active": True},
        verbose_name="Discente",
    )
    data_conclusao = models.DateTimeField("Concluída em", auto_now_add=True)

    class Meta:
        verbose_name = "Conclusão de atividade"
        verbose_name_plural = "Conclusões de atividades"
        ordering = ["-data_conclusao"]
        constraints = [
            # O mesmo aluno não pode concluir a mesma atividade duas vezes,
            # senão o progresso passaria de 100%.
            models.UniqueConstraint(
                fields=["atividade", "discente"], name="uq_conclusao_atividade_discente"
            ),
        ]
        indexes = [
            models.Index(fields=["discente", "atividade"], name="idx_conclusao_disc_ativ"),
        ]

    def __str__(self):
        return f"{self.discente} - {self.atividade}"


class MaterialDeApoio(ArquivoSeguro):
    """
    Arquivo que o professor anexa a uma trilha ou a uma atividade (slides,
    lista de exercícios, código de exemplo...).

    Passa pela mesma validação dos anexos da comunicação: só tipos da lista,
    conteúdo conferido e nada de executável, macro ou PDF com JavaScript.
    """

    trilha = models.ForeignKey(
        TrilhaAprendizagem, on_delete=models.CASCADE, null=True, blank=True,
        related_name="materiais", verbose_name="Trilha",
    )
    atividade = models.ForeignKey(
        Atividade, on_delete=models.CASCADE, null=True, blank=True,
        related_name="materiais", verbose_name="Atividade",
    )

    class Meta(ArquivoSeguro.Meta):
        verbose_name = "Material de apoio"
        verbose_name_plural = "Materiais de apoio"
        constraints = [
            # Cada material pertence a uma trilha OU a uma atividade.
            models.CheckConstraint(
                condition=(
                    models.Q(trilha__isnull=False, atividade__isnull=True)
                    | models.Q(trilha__isnull=True, atividade__isnull=False)
                ),
                name="ck_material_um_unico_dono",
            ),
        ]

    @property
    def turma(self):
        return self.trilha.turma if self.trilha_id else self.atividade.trilha.turma


class VideoDeApoio(models.Model):
    """
    Vídeo do YouTube indicado pelo professor numa trilha ou numa atividade.

    Guardamos o código do vídeo, não o link colado: o endereço do player é
    sempre montado pelo SIMAP (ver core/youtube.py).
    """

    trilha = models.ForeignKey(
        TrilhaAprendizagem, on_delete=models.CASCADE, null=True, blank=True, related_name="videos"
    )
    atividade = models.ForeignKey(
        Atividade, on_delete=models.CASCADE, null=True, blank=True, related_name="videos"
    )
    codigo = models.CharField("código do vídeo", max_length=11)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "vídeo de apoio"
        verbose_name_plural = "vídeos de apoio"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(trilha__isnull=False, atividade__isnull=True)
                    | models.Q(trilha__isnull=True, atividade__isnull=False)
                ),
                name="ck_video_um_unico_dono",
            )
        ]

    def __str__(self):
        return self.endereco_para_assistir

    @property
    def endereco_do_player(self):
        return youtube.endereco_do_player(self.codigo)

    @property
    def endereco_para_assistir(self):
        return youtube.endereco_para_assistir(self.codigo)
