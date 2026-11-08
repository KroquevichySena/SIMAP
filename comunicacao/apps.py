from django.apps import AppConfig


class ComunicacaoConfig(AppConfig):
    name = "comunicacao"
    verbose_name = "Comunicação"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import sinais  # noqa: F401
