from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Admin adaptado para o model customizado (sem campo 'username')."""

    change_password_form = AdminPasswordChangeForm
    ordering = ["nome"]
    list_display = ["nome", "email", "perfil", "is_active", "data_cadastro"]
    list_filter = ["perfil", "is_active", "is_staff"]
    search_fields = ["nome", "email", "registro_academico"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("nome", "registro_academico")}),
        ("Perfil e permissões", {
            "fields": ("perfil", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Datas", {"fields": ("last_login", "data_cadastro")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nome", "perfil", "password1", "password2"),
        }),
    )