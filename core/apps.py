from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Quando o registro sai do banco, o arquivo também sai do disco.
        from comunicacao.arquivos import conectar_limpeza_do_disco

        from .models import MaterialDeApoio

        conectar_limpeza_do_disco(MaterialDeApoio)
