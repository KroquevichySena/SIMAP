from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

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


class AceiteTermos(models.Model):
    """Registro de auditoria: uma linha por usuário e por versão dos Termos aceita."""

    id = models.BigAutoField(primary_key=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aceites_termos',
    )
    versao = models.CharField('Versão aceita', max_length=10)
    aceito_em = models.DateTimeField('Aceito em', auto_now_add=True)
    ip_address = models.GenericIPAddressField('Endereço IP', null=True, blank=True)

    class Meta:
        ordering = ['-aceito_em']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'versao'], name='uq_aceite_usuario_versao'
            ),
        ]

    def __str__(self):
        return f"{self.usuario} aceitou a versão {self.versao} em {self.aceito_em:%d/%m/%Y %H:%M}"