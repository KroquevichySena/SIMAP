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

