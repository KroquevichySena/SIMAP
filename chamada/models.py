from django.db import models
from django.conf import settings

class Chamada(models.Model):
    """Modelo usado para gerar
      chamadas dentro do Simap"""

    turma = models.ForeignKey(
        "core.Turma",
        on_delete=models.CASCADE,
        related_name="chamadas",
        verbose_name="Turma",
    )

    token_chamada = models.CharField(max_length=6, unique=True)
    data_criacao = models.DateTimeField("Data de Criação", auto_now_add=True)
    data_expiracao = models.DateTimeField("Data de Expiração")

    class Meta:
        verbose_name = "chamada"
        verbose_name_plural = "chamadas"
        ordering = ["-data_criacao"]

    def __str__(self):
        return f"Chamada {self.token_chamada} - Turma: {self.turma.nome}"

class Registro_de_Presenca(models.Model):
    """ Modelo usado para registrar a 
    presença dos alunos nas chamadas"""

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