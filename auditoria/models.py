"""
O registro de auditoria do SIMAP.

Cada linha responde a quatro perguntas: quem fez, o que fez, quando e de
onde. Registramos acessos às páginas, logins, logouts, tentativas de login
erradas, acessos negados e qualquer criação, alteração ou exclusão nos dados
acadêmicos.

Um registro de auditoria não pode ser editado nem apagado depois de gravado,
senão ele perde o valor como prova. A única forma de remover é o expurgo por
prazo (comando limpar_auditoria), que a LGPD exige, e até o expurgo deixa
um registro dizendo que aconteceu.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Acao(models.TextChoices):
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    LOGIN_FALHA = "LOGIN_FALHA", "Tentativa de login com falha"
    ACESSO = "ACESSO", "Acesso a página"
    ACESSO_NEGADO = "ACESSO_NEGADO", "Acesso negado"
    CRIACAO = "CRIACAO", "Criação"
    ALTERACAO = "ALTERACAO", "Alteração"
    EXCLUSAO = "EXCLUSAO", "Exclusão"
    EXPURGO = "EXPURGO", "Expurgo por retenção"


class RegistroImutavelError(Exception):
    """Alguém tentou editar ou apagar um registro de auditoria."""


class RegistroAuditoria(models.Model):
    # Essa tabela só cresce, então usamos o ID de 8 bytes em vez do padrão.
    id = models.BigAutoField(primary_key=True)

    data_hora = models.DateTimeField("Data e hora", default=timezone.now)
    acao = models.CharField("Ação", max_length=20, choices=Acao.choices)

    # Quem fez. Se o usuário for excluído do sistema, a ligação vira nula,
    # mas o login continua guardado em texto para o histórico fazer sentido.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_auditoria",
        verbose_name="Usuário",
    )
    usuario_login = models.CharField("Login do usuário", max_length=150, blank=True)

    # O que foi feito e em qual objeto.
    entidade = models.CharField(
        "Entidade", max_length=100, blank=True,
        help_text="Modelo afetado, no formato app.Modelo.",
    )
    objeto_id = models.CharField("ID do objeto", max_length=64, blank=True)
    objeto_repr = models.CharField("Objeto", max_length=200, blank=True)
    descricao = models.CharField("Descrição", max_length=255, blank=True)
    dados = models.JSONField(
        "Dados", null=True, blank=True,
        help_text="Valores do objeto ou campos alterados (antes/depois).",
    )

    # De onde veio a requisição.
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("Navegador", max_length=255, blank=True)
    metodo = models.CharField("Método HTTP", max_length=10, blank=True)
    caminho = models.CharField("Caminho", max_length=255, blank=True)
    status_http = models.PositiveSmallIntegerField("Status HTTP", null=True, blank=True)

    class Meta:
        verbose_name = "Registro de auditoria"
        verbose_name_plural = "Registros de auditoria"
        ordering = ["-data_hora", "-id"]
        # Índices pensados nas consultas mais comuns da tela: por período,
        # por usuário, por tipo de ação e pelo histórico de um objeto.
        indexes = [
            models.Index(fields=["-data_hora"], name="idx_audit_data"),
            models.Index(fields=["usuario", "-data_hora"], name="idx_audit_usuario_data"),
            models.Index(fields=["acao", "-data_hora"], name="idx_audit_acao_data"),
            models.Index(fields=["entidade", "objeto_id"], name="idx_audit_entidade_obj"),
        ]

    def __str__(self):
        return f"{self.data_hora:%d/%m/%Y %H:%M:%S} · {self.origem} · {self.get_acao_display()}"

    @property
    def origem(self):
        # Quando não há usuário, a ação veio do próprio sistema
        # (um comando no terminal, por exemplo).
        return self.usuario_login or "sistema"

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise RegistroImutavelError("Registros de auditoria não podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavelError(
            "Registros de auditoria não podem ser excluídos um a um. "
            "Use o comando limpar_auditoria, que respeita o prazo de retenção."
        )
