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


class VersaoTermos(models.Model):
    """
    Uma versão publicada dos Termos de Uso e da Política de Privacidade.

    A versão vigente é sempre a última publicada. Uma versão publicada não é
    editada nem apagada: para mudar o texto, publica-se uma nova, e assim fica
    guardado exatamente o que cada pessoa aceitou (ver AceiteTermos.versao).
    """

    numero = models.CharField('Número da versão', max_length=10, unique=True)
    resumo = models.TextField(
        'Em resumo', blank=True, help_text='Um ponto por linha. Aparece em destaque antes do texto integral.',
    )
    texto = models.TextField('Texto integral')
    o_que_mudou = models.TextField(
        'O que mudou nesta versão', blank=True,
        help_text='Mostrado a quem precisa aceitar de novo. Um ponto por linha.',
    )
    publicada_em = models.DateTimeField('Publicada em', auto_now_add=True)
    publicada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='versoes_termos_publicadas', verbose_name='Publicada por',
    )

    # O texto fica guardado nesta própria tabela; a auditoria registra só quem
    # publicou e quando, sem duplicar o documento inteiro.
    AUDITORIA_CAMPOS_OCULTOS = ('resumo', 'texto', 'o_que_mudou')

    class Meta:
        ordering = ['-pk']
        verbose_name = 'versão dos termos'
        verbose_name_plural = 'versões dos termos'

    def __str__(self):
        return f"Versão {self.numero}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Uma versão publicada dos termos não pode ser alterada. Publique uma nova versão.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Uma versão publicada dos termos não pode ser apagada.")
