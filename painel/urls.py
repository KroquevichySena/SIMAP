from django.urls import path

from . import views

app_name = "painel"

urlpatterns = [
    path("docente/", views.PainelDocenteView.as_view(), name="docente"),
    path("docente/turma/<int:pk>/limite/", views.DefinirLimiteView.as_view(), name="definir_limite"),
]
