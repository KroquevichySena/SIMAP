from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Instituicao(models.Model):
    nome = models.CharField(max_length=120)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    raio_metros = models.PositiveIntegerField(
        "Raio aceito (m)", default=150,
        validators=[MinValueValidator(50), MaxValueValidator(1000)],
    )
    precisao_minima = models.PositiveIntegerField(
        "Precisão mínima aceita (m)", default=100,
        validators=[MinValueValidator(20), MaxValueValidator(500)],
        help_text="Se o GPS do celular errar mais que isso, a presença vai para análise.",
    )

    class Meta:
        verbose_name = "instituição"
        verbose_name_plural = "instituições"

    def __str__(self):
        return self.nome

    @property
    def tem_localizacao(self):
        return self.latitude is not None and self.longitude is not None


class Turma(models.Model):
    nome = models.CharField(max_length=100)
    periodo = models.CharField(max_length=10)
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    instituicao = models.ForeignKey(
        Instituicao, on_delete=models.SET_NULL, null=True, blank=True, related_name="turmas"
    )
    ativa = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    limite_atencao = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )


    def __str__(self):
        return f"{self.nome} - {self.periodo}"

class Matricula(models.Model):
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
        ]
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE)
    discente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ATIVA')
    data_matricula = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['turma', 'discente'],
                name='matricula_unica_por_turma'
            )
        ]

    def __str__(self):
        return f"{self.turma} - {self.discente}"
