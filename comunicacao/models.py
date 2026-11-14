"""
Comunicação entre professor e alunos, no formato de comentários.

Não é um chat em tempo real: alguém publica e os outros respondem, como num
mural. Uma publicação pode ser de três tipos, conforme os campos preenchidos:

- Mural da turma: sem atividade e sem destinatário. Todos da turma veem.
- Comentário de atividade: com atividade. Todos da turma veem.
- Mensagem privada: com destinatário. Só o autor e o destinatário veem.

Respostas e anexos ficam pendurados na publicação, e as notificações avisam
cada pessoa do que é novo para ela.
"""
import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse


def caminho_do_anexo(instancia, nome_arquivo):
    # O nome que o usuário deu ao arquivo nunca vira caminho no disco. Ele só
    # é guardado no banco para aparecer na tela; no disco o nome é aleatório.
    # A pasta é a do app dono do arquivo (comunicacao/, core/, entregas/).
    extensao = os.path.splitext(nome_arquivo)[1].lower()
    return f"{instancia._meta.app_label}/{uuid.uuid4().hex}{extensao}"


class ArquivoSeguro(models.Model):
    """
    Base de todo arquivo enviado por usuário no SIMAP.

    Só chega aqui o que passou por seguranca.validar_anexo(). Os anexos da
    comunicação, o material de apoio das trilhas e os arquivos das entregas
    herdam daqui, então todos têm a mesma validação, o mesmo armazenamento
    com nome aleatório e o mesmo download protegido.
    """

    arquivo = models.FileField("Arquivo", upload_to=caminho_do_anexo, max_length=255)
    nome_original = models.CharField("Nome do arquivo", max_length=255)
    extensao = models.CharField("Extensão", max_length=10)
    tipo_conteudo = models.CharField("Tipo de conteúdo", max_length=120)
    tamanho = models.PositiveIntegerField("Tamanho (bytes)")
    sha256 = models.CharField("Hash SHA-256", max_length=64)
    enviado_em = models.DateTimeField("Enviado em", auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["id"]

    def __str__(self):
        return self.nome_original

    @property
    def eh_imagem(self):
        return self.tipo_conteudo.startswith("image/")

    @property
    def tamanho_legivel(self):
        if self.tamanho < 1024:
            return f"{self.tamanho} B"
        if self.tamanho < 1024 * 1024:
            return f"{self.tamanho / 1024:.0f} KB"
        return f"{self.tamanho / (1024 * 1024):.1f} MB"


class Publicacao(models.Model):
    class Tipo(models.TextChoices):
        MURAL = "MURAL", "Mural da turma"
        ATIVIDADE = "ATIVIDADE", "Comentário de atividade"
        PRIVADA = "PRIVADA", "Mensagem privada"

    # O conteúdo das mensagens não é copiado para a auditoria (LGPD): ela
    # registra quem publicou e quando, mas não o que foi escrito.
    AUDITORIA_CAMPOS_OCULTOS = ("texto",)

    turma = models.ForeignKey(
        "turmas.Turma", on_delete=models.CASCADE, related_name="publicacoes", verbose_name="Turma"
    )
    atividade = models.ForeignKey(
        "core.Atividade", on_delete=models.CASCADE, null=True, blank=True,
        related_name="comentarios", verbose_name="Atividade",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="publicacoes", verbose_name="Autor",
    )
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="mensagens_recebidas", verbose_name="Destinatário",
        help_text="Preenchido só nas mensagens privadas.",
    )
    texto = models.TextField("Mensagem")
    criada_em = models.DateTimeField("Publicada em", auto_now_add=True)

    class Meta:
        verbose_name = "Publicação"
        verbose_name_plural = "Publicações"
        ordering = ["-criada_em", "-id"]
        constraints = [
            # Uma mensagem privada não fica presa a uma atividade.
            models.CheckConstraint(
                condition=Q(atividade__isnull=True) | Q(destinatario__isnull=True),
                name="ck_publicacao_privada_sem_atividade",
            ),
        ]
        indexes = [
            models.Index(fields=["turma", "-criada_em"], name="idx_pub_turma_data"),
            models.Index(fields=["atividade", "-criada_em"], name="idx_pub_atividade_data"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.autor} ({self.criada_em:%d/%m/%Y %H:%M})"

    def get_absolute_url(self):
        return reverse("comunicacao:publicacao", args=[self.pk])

    @property
    def tipo(self):
        if self.destinatario_id:
            return self.Tipo.PRIVADA
        if self.atividade_id:
            return self.Tipo.ATIVIDADE
        return self.Tipo.MURAL

    def get_tipo_display(self):
        return self.Tipo(self.tipo).label

    @property
    def privada(self):
        return self.destinatario_id is not None


class Resposta(models.Model):
    AUDITORIA_CAMPOS_OCULTOS = ("texto",)

    publicacao = models.ForeignKey(
        Publicacao, on_delete=models.CASCADE, related_name="respostas", verbose_name="Publicação"
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="respostas_comunicacao", verbose_name="Autor",
    )
    texto = models.TextField("Resposta")
    criada_em = models.DateTimeField("Respondida em", auto_now_add=True)

    class Meta:
        verbose_name = "Resposta"
        verbose_name_plural = "Respostas"
        ordering = ["criada_em", "id"]

    def __str__(self):
        return f"Resposta de {self.autor} ({self.criada_em:%d/%m/%Y %H:%M})"

    def get_absolute_url(self):
        return f"{self.publicacao.get_absolute_url()}#resposta-{self.pk}"


class Anexo(ArquivoSeguro):
    """Arquivo enviado numa publicação ou numa resposta, já validado."""

    publicacao = models.ForeignKey(
        Publicacao, on_delete=models.CASCADE, null=True, blank=True, related_name="anexos"
    )
    resposta = models.ForeignKey(
        Resposta, on_delete=models.CASCADE, null=True, blank=True, related_name="anexos"
    )

    class Meta(ArquivoSeguro.Meta):
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"
        constraints = [
            # Todo anexo pertence a exatamente uma publicação OU uma resposta.
            models.CheckConstraint(
                condition=(
                    Q(publicacao__isnull=False, resposta__isnull=True)
                    | Q(publicacao__isnull=True, resposta__isnull=False)
                ),
                name="ck_anexo_um_unico_dono",
            ),
        ]

    @property
    def publicacao_de_origem(self):
        return self.publicacao if self.publicacao_id else self.resposta.publicacao


class Notificacao(models.Model):
    class Tipo(models.TextChoices):
        PUBLICACAO = "PUBLICACAO", "Nova publicação"
        COMENTARIO = "COMENTARIO", "Novo comentário em atividade"
        PRIVADA = "PRIVADA", "Nova mensagem privada"
        RESPOSTA = "RESPOSTA", "Nova resposta"
        TRILHA = "TRILHA", "Nova trilha"
        ATIVIDADE = "ATIVIDADE", "Nova atividade"
        PRAZO = "PRAZO", "Prazo terminando"

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notificacoes", verbose_name="Destinatário",
    )
    tipo = models.CharField("Tipo", max_length=12, choices=Tipo.choices)
    mensagem = models.CharField("Mensagem", max_length=255)
    # Sempre um caminho interno do SIMAP (começa com "/"), nunca um site externo.
    url = models.CharField("Link", max_length=255)
    lida = models.BooleanField("Lida", default=False)
    criada_em = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-criada_em", "-id"]
        indexes = [
            models.Index(fields=["destinatario", "lida", "-criada_em"], name="idx_notif_dest_lida"),
        ]

    def __str__(self):
        return self.mensagem
