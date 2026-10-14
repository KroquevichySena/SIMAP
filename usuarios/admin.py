from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
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

    fieldsets = UserAdmin.fieldsets + (
        ("SIMAP", {"fields": ("perfil", "rgm")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("SIMAP", {"fields": ("perfil", "rgm")}),
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