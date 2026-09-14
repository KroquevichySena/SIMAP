from django.db import models
from django.contrib.auth.models import AbstractUser

class Usuario(AbstractUser):
    PERFIL_CHOICES = [
        ('DOCENTE', 'Docente'),
        ('DISCENTE', 'Discente'),
    ]

    rgm = models.CharField(max_length=20, blank=True)
    perfil = models.CharField(max_length=10, choices=PERFIL_CHOICES)

    @property
    def is_docente(self) -> bool:
        return self.perfil == 'DOCENTE'

    @property
    def is_discente(self) -> bool:
        return self.perfil == 'DISCENTE'