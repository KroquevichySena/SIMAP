from django.apps import AppConfig


class EntregasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'entregas'

    def ready(self):
        # Quando o registro sai do banco, o arquivo também sai do disco.
        from comunicacao.arquivos import conectar_limpeza_do_disco

        from .models import AnexoSubmissao

        conectar_limpeza_do_disco(AnexoSubmissao)
