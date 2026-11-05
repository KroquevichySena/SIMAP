from .models import Notificacao


def notificacoes(request):
    """Deixa o sino da barra de navegação com o número de notificações não lidas."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    nao_lidas = Notificacao.objects.filter(destinatario=usuario, lida=False)
    return {
        "notificacoes_nao_lidas": nao_lidas.count(),
        "notificacoes_recentes": nao_lidas[:5],
    }
