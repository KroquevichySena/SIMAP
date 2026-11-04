from django.urls import path

from . import views

app_name = "painel"

urlpatterns = [
    path("docente/", views.PainelDocenteView.as_view(), name="docente"),
    path("docente/turma/<int:pk>/limite/", views.DefinirLimiteView.as_view(), name="definir_limite"),
    path(
        "docente/turma/<int:turma_pk>/aluno/<int:aluno_pk>/",
        views.DetalheAlunoView.as_view(),
        name="detalhe_aluno",
    ),
    path("discente/", views.PainelDiscenteView.as_view(), name="discente"),
]
