from django.contrib import admin

from .models import Atividade, Matricula, TrilhaAprendizagem, Turma


class MatriculaInline(admin.TabularInline):
    model = Matricula
    extra = 1
    autocomplete_fields = ["discente"]


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ["nome", "periodo", "docente", "ativa", "data_criacao"]
    list_filter = ["ativa", "periodo"]
    search_fields = ["nome", "periodo", "docente__first_name"]
    autocomplete_fields = ["docente"]
    inlines = [MatriculaInline]


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ["discente", "turma", "status", "data_matricula"]
    list_filter = ["status", "turma"]
    search_fields = ["discente__first_name", "discente__email"]
    autocomplete_fields = ["discente", "turma"]


class AtividadeInline(admin.TabularInline):
    model = Atividade
    extra = 1


@admin.register(TrilhaAprendizagem)
class TrilhaAdmin(admin.ModelAdmin):
    list_display = ["titulo", "turma", "ordem", "publicada", "total_atividades"]
    list_filter = ["publicada", "turma"]
    search_fields = ["titulo"]
    inlines = [AtividadeInline]


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ["titulo", "trilha", "tipo", "ordem", "prazo", "publicada"]
    list_filter = ["tipo", "publicada", "trilha__turma"]
    search_fields = ["titulo"]