from django.db import models
from django.conf import settings

class Turma(models.Model):
    nome = models.CharField(max_length=100)
    semestre = models.CharField(max_length=10)
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome} - {self.semestre}"


