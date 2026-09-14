from django.contrib import admin

from .models import Atividade, ConclusaoAtividade, TrilhaAprendizagem


class AtividadeInline(admin.TabularInline):
    model = Atividade
    extra = 1


@admin.register(TrilhaAprendizagem)
class TrilhaAdmin(admin.ModelAdmin):
    list_display = ["titulo", "turma", "ordem", "publicada", "total_atividades"]
    list_filter = ["publicada", "turma"]
    search_fields = ["titulo", "turma__nome"]
    inlines = [AtividadeInline]


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ["titulo", "trilha", "tipo", "ordem", "prazo", "publicada"]
    list_filter = ["tipo", "publicada", "trilha__turma"]
    search_fields = ["titulo", "trilha__titulo"]


@admin.register(ConclusaoAtividade)
class ConclusaoAtividadeAdmin(admin.ModelAdmin):
    list_display = ("discente", "atividade", "data_conclusao")
    list_filter = ("atividade__trilha__turma",)
    search_fields = ("discente__username", "atividade__titulo")
