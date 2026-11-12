"""Destinos internos e verificação do aceite vigente."""
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.shortcuts import resolve_url
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import AceiteTermos


def aceitou_versao_atual(usuario):
    return AceiteTermos.objects.filter(
        usuario=usuario, versao=settings.TERMOS_DE_USO_VERSAO
    ).exists()


def destino_seguro(request, destino=None):
    destino = destino if destino is not None else request.POST.get("next", request.GET.get("next", ""))
    padrao = resolve_url(settings.LOGIN_REDIRECT_URL)
    if not destino or not destino.startswith("/") or destino.startswith("//"):
        return padrao
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}, require_https=request.is_secure()):
        return padrao
    try:
        rota = resolve(urlsplit(destino).path)
        if rota.url_name in {"primeiro_acesso", "login", "logout"}:
            return padrao
    except Resolver404:
        pass
    return destino


def url_primeiro_acesso(destino):
    return reverse("primeiro_acesso") + "?" + urlencode({"next": destino})
