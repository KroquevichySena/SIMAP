from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    name = "auditoria"
    verbose_name = "Auditoria"
    # Essa tabela só cresce, então aqui vale a pena usar o ID de 8 bytes.
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Quando o Django termina de carregar os apps, ligamos os "ouvidos"
        # da auditoria: login, logout e alterações nos modelos.
        from . import sinais

        sinais.conectar()
