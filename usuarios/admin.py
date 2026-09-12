from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm

from.models import Usuario

@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Admin adaptado para a realidade do model atual (herdeiro do AbstractUser)."""

    change_password_form = AdminPasswordChangeForm
    ordering = ["first_name"]
    list_display = ["first_name", "email", "perfil", "is_active", "date_joined"]
    list_filter = ["perfil", "is_active", "is_staff"]
    search_fields = ["first_name", "email", "rgm"]

    fieldsets = (
        (None, {"fields": ("username", "password")}), # Username retornado pois o AbstractUser exige
        ("Dados pessoais", {"fields": ("first_name", "last_name", "email", "rgm")}),
        ("Perfil e permissões", {
            "fields": ("perfil", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "perfil", "password1", "password2"),
        }),
    )