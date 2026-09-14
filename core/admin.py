from django.contrib import admin

from .models import Atividade, ConclusaoAtividade, TrilhaAprendizagem


@admin.register(TrilhaAprendizagem)
class TrilhaAprendizagemAdmin(admin.ModelAdmin):
    list_display = ("titulo", "turma", "ordem", "publicada", "total_atividades")
    list_filter = ("publicada", "turma")
    search_fields = ("titulo", "turma__nome")


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("titulo", "trilha", "tipo", "ordem", "prazo", "publicada")
    list_filter = ("publicada", "tipo", "trilha__turma")
    search_fields = ("titulo", "trilha__titulo")


@admin.register(ConclusaoAtividade)
class ConclusaoAtividadeAdmin(admin.ModelAdmin):
    list_display = ("discente", "atividade", "data_conclusao")
    list_filter = ("atividade__trilha__turma",)
    search_fields = ("discente__username", "atividade__titulo")
