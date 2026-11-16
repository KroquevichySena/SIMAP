from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import SenhaTemporariaAdminForm
from .models import AceiteTermos, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    Reaproveita a tela de usuários padrão do Django e só acrescenta os campos
    do SIMAP (perfil e RGM), em vez de reescrever o formulário inteiro.
    """

    list_display = ("username", "first_name", "last_name", "email", "perfil", "is_active", "is_staff")
    list_filter = ("perfil", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "rgm")
    change_password_form = SenhaTemporariaAdminForm
    readonly_fields = ("troca_senha_obrigatoria",)

    fieldsets = UserAdmin.fieldsets + (
        ("SIMAP", {"fields": ("perfil", "rgm", "troca_senha_obrigatoria")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("SIMAP", {"fields": ("perfil", "rgm")}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.troca_senha_obrigatoria = True
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return request.user.is_authenticated and request.user.is_coordenacao and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return (
            request.user.is_authenticated and request.user.is_coordenacao and super().has_view_permission(request, obj)
        )

    def has_add_permission(self, request):
        return request.user.is_authenticated and request.user.is_coordenacao and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return (
            request.user.is_authenticated
            and request.user.is_coordenacao
            and super().has_change_permission(request, obj)
        )

    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_authenticated
            and request.user.is_coordenacao
            and super().has_delete_permission(request, obj)
        )


@admin.register(AceiteTermos)
class AceiteTermosAdmin(admin.ModelAdmin):
    list_display = ("usuario", "versao", "aceito_em", "ip_address")
    list_filter = ("versao",)
    search_fields = ("usuario__username", "usuario__email")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
