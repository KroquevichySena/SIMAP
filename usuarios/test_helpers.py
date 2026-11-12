"""Estado inicial de usuários que já concluíram o primeiro acesso nos testes."""
from django.conf import settings

from .models import AceiteTermos


def registrar_aceites_atuais(usuarios):
    # A montagem da fixture representa um aceite anterior ao cenário testado.
    AceiteTermos.objects.bulk_create([
        AceiteTermos(usuario=usuario, versao=settings.TERMOS_DE_USO_VERSAO)
        for usuario in usuarios
    ], ignore_conflicts=True)
