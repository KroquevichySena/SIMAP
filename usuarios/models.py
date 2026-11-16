from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UsuarioManager


class Usuario(AbstractUser):
    PERFIL_CHOICES = [
        ('COORDENACAO', 'Coordenação'),
        ('DOCENTE', 'Docente'),
        ('DISCENTE', 'Discente'),
    ]

    rgm = models.CharField(max_length=20, blank=True)
    perfil = models.CharField(max_length=12, choices=PERFIL_CHOICES)
    objects = UsuarioManager()
    troca_senha_obrigatoria = models.BooleanField(
        "Troca de senha pendente", default=False,
        help_text="Exige uma nova senha pessoal antes de acessar as funcionalidades.",
    )

    @property
    def is_docente(self) -> bool:
        return self.perfil == 'DOCENTE'

    @property
    def is_discente(self) -> bool:
        return self.perfil == 'DISCENTE'

    @property
    def is_coordenacao(self) -> bool:
        """O perfil de negócio é explícito e independente dos privilégios do Django."""
        return self.is_active and self.perfil == 'COORDENACAO'

    @property
    def pode_consultar_auditoria(self) -> bool:
        return self.is_coordenacao


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
