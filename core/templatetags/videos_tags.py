from django import template

from core.youtube import codigos_no_texto

register = template.Library()


@register.filter
def codigos_dos_videos(videos):
    """Lista de códigos a partir dos VideoDeApoio de uma trilha ou atividade."""
    return [video.codigo for video in videos]


@register.filter
def videos_do_youtube(texto):
    """Até 3 vídeos do YouTube citados num texto (mural, comentários, respostas)."""
    return codigos_no_texto(texto)
