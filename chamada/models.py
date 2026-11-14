import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

LETRAS_DO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class Chamada(models.Model):
    """Modelo usado para gerar
      chamadas dentro do Simap"""

    CICLOS = [(15, "15 segundos"), (30, "30 segundos"), (45, "45 segundos"), (60, "60 segundos")]

    turma = models.ForeignKey(
        "turmas.Turma",
        on_delete=models.CASCADE,
        related_name="chamadas",
        verbose_name="Turma",
    )

    token_chamada = models.CharField(max_length=6, unique=True)
    data_criacao = models.DateTimeField("Data de Criação", auto_now_add=True)
    data_expiracao = models.DateTimeField("Data de Expiração")
    limite_uso = models.PositiveSmallIntegerField(
        "Limite de uso do token",
        default=1,
        help_text="Quantidade máxima de alunos que podem confirmar presença com este token.",
    )
    ciclo_segundos = models.PositiveSmallIntegerField("Tempo do QR code", choices=CICLOS, default=30)
    renovacoes = models.PositiveSmallIntegerField(default=0)
    finalizada_em = models.DateTimeField("Finalizada em", null=True, blank=True)

    class Meta:
        verbose_name = "chamada"
        verbose_name_plural = "chamadas"
        ordering = ["-data_criacao"]

    def __str__(self):
        return f"Chamada {self.token_chamada} - Turma: {self.turma.nome}"

    @property
    def esta_expirada(self):
        return timezone.now() > self.data_expiracao

    @property
    def vagas_esgotadas(self):
        return self.presencas.count() >= self.limite_uso

    @property
    def esta_valida(self):
        return not self.esta_expirada and not self.vagas_esgotadas

    @property
    def qr_aberto(self):
        return self.finalizada_em is None and not self.esta_expirada

    @staticmethod
    def gerar_token():
        while True:
            token = "".join(secrets.choice(LETRAS_DO_CODIGO) for _ in range(6))
            if not Chamada.objects.filter(token_chamada=token).exists():
                return token

    def iniciar_ciclo(self):
        """Gera um código novo e conta o tempo do QR a partir de agora."""
        self.token_chamada = self.gerar_token()
        self.data_expiracao = timezone.now() + timedelta(seconds=self.ciclo_segundos)

    def renovar(self):
        self.iniciar_ciclo()
        self.renovacoes += 1
        self.save(update_fields=["token_chamada", "data_expiracao", "renovacoes"])

    def finalizar(self):
        agora = timezone.now()
        self.finalizada_em = agora
        if self.data_expiracao > agora:
            self.data_expiracao = agora
        self.save(update_fields=["finalizada_em", "data_expiracao"])


class Registro_de_Presenca(models.Model):
    """ Modelo usado para registrar a
    presença dos alunos nas chamadas"""

    CONFIRMADA = "CONFIRMADA"
    EM_ANALISE = "EM_ANALISE"
    RECUSADA = "RECUSADA"
    SITUACOES = [
        (CONFIRMADA, "Confirmada"),
        (EM_ANALISE, "Em análise"),
        (RECUSADA, "Recusada"),
    ]
    ORIGENS = [("QR", "QR code"), ("CODIGO", "Código digitado")]

    chamada = models.ForeignKey(
        Chamada,
        on_delete=models.CASCADE,
        related_name="presencas",
    )

    discente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"perfil": 'DISCENTE', "is_active": True},
        verbose_name="Aluno",
    )

    data_registro = models.DateTimeField("Registro em", auto_now_add=True)
    situacao = models.CharField(max_length=10, choices=SITUACOES, default=CONFIRMADA)
    motivo = models.CharField(max_length=200, blank=True)
    origem = models.CharField(max_length=6, choices=ORIGENS, default="CODIGO")
    distancia_m = models.PositiveIntegerField("Distância até a instituição (m)", null=True, blank=True)
    dispositivo = models.CharField(max_length=36, blank=True)

    class Meta:
        verbose_name = "Registro de Presenca"
        verbose_name_plural = "registros de Presenca"
        constraints = [
            # Regra no banco que impede o mesmo
            # aluno registre presença duas vezes
            # na mesma chamada
            models.UniqueConstraint(
                fields=["chamada", "discente"],
                name="uq_presenca_unica_por_aluno"
            ),
        ]

    def __str__(self):
        return f"{self.discente.first_name} presente em {self.chamada}"
