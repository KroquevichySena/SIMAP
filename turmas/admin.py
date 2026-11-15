from django.contrib import admin

from .models import Instituicao, Matricula, Turma

admin.site.register(Instituicao)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome", "periodo", "docente", "perfil_do_responsavel", "ativa")
    list_filter = ("ativa", "docente__perfil")
    list_select_related = ("docente",)

    @admin.display(description="Perfil do responsável")
    def perfil_do_responsavel(self, obj):
        return obj.docente.get_perfil_display()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "docente":
            from django.contrib.auth import get_user_model

            kwargs["queryset"] = get_user_model().objects.filter(perfil="DOCENTE", is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ("turma", "discente", "status")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "discente":
            from django.contrib.auth import get_user_model

            kwargs["queryset"] = get_user_model().objects.filter(perfil="DISCENTE", is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
