"""
Tela para consultar a auditoria.

Só a coordenação (superusuários) pode ver. O log guarda dados pessoais de
todo mundo, como IP, navegador e as páginas que cada um acessou, então não
faz sentido um docente ou um aluno enxergar isso. É o princípio da
necessidade da LGPD: só vê quem realmente precisa.
"""
import csv
import ipaddress
from datetime import datetime, time

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views.generic import ListView

from .models import Acao, RegistroAuditoria

LIMITE_EXPORTACAO = 50_000


class SuperusuarioRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Apenas a coordenação pode consultar a auditoria.")


def _data(valor, fim_do_dia=False):
    try:
        dia = datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return timezone.make_aware(datetime.combine(dia, time.max if fim_do_dia else time.min))


class _Eco:
    """Finge ser um arquivo, para o csv.writer escrever direto na resposta."""

    def write(self, valor):
        return valor


def _celula_segura(valor):
    """
    Evita a "injeção de fórmula" no CSV.

    Se alguém digitar algo como =HYPERLINK(...) no campo de usuário do
    login, o Excel executaria isso como fórmula ao abrir a planilha. Colocar
    um apóstrofo na frente faz o Excel tratar como texto comum.
    """
    texto = "" if valor is None else str(valor)
    if texto[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + texto
    return texto


class RegistroAuditoriaListView(SuperusuarioRequiredMixin, ListView):
    model = RegistroAuditoria
    template_name = "auditoria/registro_list.html"
    context_object_name = "registros"
    paginate_by = 50

    def get_queryset(self):
        qs = RegistroAuditoria.objects.select_related("usuario")
        g = self.request.GET

        if acao := g.get("acao"):
            if acao in Acao.values:
                qs = qs.filter(acao=acao)
        if usuario := g.get("usuario", "").strip():
            qs = qs.filter(usuario_login__icontains=usuario)
        if entidade := g.get("entidade", "").strip():
            qs = qs.filter(entidade__icontains=entidade)
        if ip := g.get("ip", "").strip():
            qs = qs.filter(ip=ip) if _ip_ok(ip) else qs.none()
        if inicio := _data(g.get("de")):
            qs = qs.filter(data_hora__gte=inicio)
        if fim := _data(g.get("ate"), fim_do_dia=True):
            qs = qs.filter(data_hora__lte=fim)
        if texto := g.get("q", "").strip():
            qs = qs.filter(
                Q(descricao__icontains=texto)
                | Q(objeto_repr__icontains=texto)
                | Q(caminho__icontains=texto)
            )
        return qs

    def get(self, request, *args, **kwargs):
        if request.GET.get("formato") == "csv":
            return self._exportar_csv()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtros = self.request.GET.copy()
        filtros.pop("page", None)
        filtros.pop("formato", None)
        ctx["acoes"] = Acao.choices
        ctx["filtros"] = self.request.GET
        ctx["filtros_url"] = filtros.urlencode()
        return ctx

    def _exportar_csv(self):
        registros = self.get_queryset()[:LIMITE_EXPORTACAO]
        escritor = csv.writer(_Eco(), delimiter=";")
        cabecalho = ["data_hora", "acao", "usuario", "entidade", "objeto_id",
                     "objeto", "descricao", "ip", "metodo", "caminho", "status_http"]

        def linhas():
            yield "\ufeff"  # sem essa marca o Excel bagunça os acentos
            yield escritor.writerow(cabecalho)
            for r in registros.iterator(chunk_size=2000):
                yield escritor.writerow([
                    _celula_segura(v) for v in (
                        timezone.localtime(r.data_hora).strftime("%d/%m/%Y %H:%M:%S"),
                        r.get_acao_display(), r.origem, r.entidade, r.objeto_id,
                        r.objeto_repr, r.descricao, r.ip, r.metodo, r.caminho,
                        r.status_http,
                    )
                ])

        nome = f"auditoria_simap_{timezone.localtime():%Y%m%d_%H%M}.csv"
        resposta = StreamingHttpResponse(linhas(), content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        return resposta


def _ip_ok(valor):
    try:
        ipaddress.ip_address(valor)
        return True
    except ValueError:
        return False
