from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Admin do Usuario customizado — estende os fieldsets padrão do Django
    com os campos próprios do SIMAP (perfil, rgm), em vez de redeclarar tudo."""

    list_display = ("username", "first_name", "last_name", "email", "perfil", "is_active", "is_staff")
    list_filter = ("perfil", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "rgm")

    fieldsets = UserAdmin.fieldsets + (
        ("SIMAP", {"fields": ("perfil", "rgm")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("SIMAP", {"fields": ("perfil", "rgm")}),
    )
