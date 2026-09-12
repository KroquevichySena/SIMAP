from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.DashboardRedirectView.as_view(), name="dashboard"),

    # --- Área do Docente: Trilhas ---
    path("docente/trilhas/", views.TrilhaListView.as_view(), name="trilha_list"),
    path("docente/trilhas/nova/", views.TrilhaCreateView.as_view(), name="trilha_create"),
    path("docente/trilhas/<int:pk>/editar/", views.TrilhaUpdateView.as_view(), name="trilha_update"),
    path("docente/trilhas/<int:pk>/excluir/", views.TrilhaDeleteView.as_view(), name="trilha_delete"),

    # --- Área do Docente: Atividades ---
    path("docente/atividades/", views.AtividadeListView.as_view(), name="atividade_list"),
    path("docente/atividades/nova/", views.AtividadeCreateView.as_view(), name="atividade_create"),
    path("docente/atividades/<int:pk>/editar/", views.AtividadeUpdateView.as_view(), name="atividade_update"),
    path("docente/atividades/<int:pk>/excluir/", views.AtividadeDeleteView.as_view(), name="atividade_delete"),

    # --- Área do Discente ---
    path("minhas-trilhas/", views.MinhasTrilhasListView.as_view(), name="minhas_trilhas"),
]