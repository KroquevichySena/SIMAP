from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """No admin a auditoria também é só leitura: ninguém cria, edita ou apaga."""

    list_display = ("data_hora", "acao", "origem", "entidade", "objeto_repr", "ip", "status_http")
    list_filter = ("acao", "entidade", "data_hora")
    search_fields = ("usuario_login", "descricao", "objeto_repr", "caminho", "ip")
    date_hierarchy = "data_hora"
    list_per_page = 50
    readonly_fields = [f.name for f in RegistroAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser
