from django.urls import path

from . import views
from turmas.views import configurar_turma

app_name = "painel"

urlpatterns = [
    path("docente/", views.PainelDocenteView.as_view(), name="docente"),
    # A URL antiga continua aceitando envios, pela mesma validação da área de turmas.
    path("docente/turma/<int:pk>/limite/", configurar_turma, name="definir_limite"),
    path(
        "docente/turma/<int:turma_pk>/aluno/<int:aluno_pk>/",
        views.DetalheAlunoView.as_view(),
        name="detalhe_aluno",
    ),
    path("discente/", views.PainelDiscenteView.as_view(), name="discente"),
]
