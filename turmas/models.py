from django.db import models
from django.conf import settings

class Turma(models.Model):
    nome = models.CharField(max_length=100)
    periodo = models.CharField(max_length=10)
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    ativa = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

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