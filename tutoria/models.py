from django.conf import settings
from django.db import models

from core.models import Atividade


class PedidoDeAjuda(models.Model):
    """
    Cada vez que o aluno aperta um botão de "Preciso de ajuda".

    Guardamos o pedido e a resposta para três coisas: limitar quantos pedidos
    o aluno faz, mostrar de novo as dicas quando ele reabre a atividade e o
    professor saber quanto de ajuda cada aluno usou.
    """

    class Tipo(models.TextChoices):
        DICA = "DICA", "Dica"
        CONCEITO = "CONCEITO", "Explicação do conceito"
        MATERIAL = "MATERIAL", "Material de estudo"
        CODIGO = "CODIGO", "Análise do código"

    class Status(models.TextChoices):
        RESPONDIDO = "RESPONDIDO", "Respondido"
        BARRADO = "BARRADO", "Resposta barrada (entregava a solução)"
        ERRO = "ERRO", "Falha ao falar com a IA"

    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pedidos_de_ajuda")
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE, related_name="pedidos_de_ajuda")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    nivel = models.PositiveSmallIntegerField(default=0, help_text="Nível da dica (1 a 3). Zero nos outros tipos.")
    codigo_enviado = models.TextField(blank=True)
    erro_enviado = models.TextField(blank=True)
    resposta = models.TextField(blank=True)
    fontes = models.JSONField(default=list, blank=True)
    sugestoes_de_busca = models.TextField(blank=True, help_text="HTML das sugestões do Google, exigido ao usar a busca.")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RESPONDIDO)
    criado_em = models.DateTimeField(auto_now_add=True)

    # Código e resposta não vão para o histórico da auditoria (só quem e quando).
    AUDITORIA_CAMPOS_OCULTOS = ("codigo_enviado", "erro_enviado", "resposta", "fontes", "sugestoes_de_busca")

    class Meta:
        ordering = ["criado_em", "id"]
        verbose_name = "pedido de ajuda"
        verbose_name_plural = "pedidos de ajuda"
        indexes = [models.Index(fields=["aluno", "atividade", "criado_em"], name="idx_ajuda_aluno_ativ")]

    def __str__(self):
        return f"{self.get_tipo_display()} para {self.aluno} em {self.atividade}"

    @property
    def titulo(self):
        if self.tipo == self.Tipo.DICA:
            return f"💡 Dica nível {self.nivel}"
        return {"CONCEITO": "📖 Explicação do conceito", "MATERIAL": "🔎 Material de estudo",
                "CODIGO": "🐞 Análise do seu código"}[self.tipo]
