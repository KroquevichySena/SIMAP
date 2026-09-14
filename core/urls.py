from django.urls import path

from . import views

# IMPORTANTE: sem app_name, para manter o padrão de 'turmas.urls'

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),

    # --- Trilhas (docente) ---
    path("trilhas/", views.TrilhaListView.as_view(), name="listar_trilhas"),
    path("trilhas/nova/", views.TrilhaCreateView.as_view(), name="criar_trilha"),
    path("trilhas/<int:pk>/editar/", views.TrilhaUpdateView.as_view(), name="editar_trilha"),
    path("trilhas/<int:pk>/excluir/", views.TrilhaDeleteView.as_view(), name="excluir_trilha"),

    # --- Atividades (docente) ---
    path("atividades/", views.AtividadeListView.as_view(), name="listar_atividades"),
    path("atividades/nova/", views.AtividadeCreateView.as_view(), name="criar_atividade"),
    path("atividades/<int:pk>/editar/", views.AtividadeUpdateView.as_view(), name="editar_atividade"),
    path("atividades/<int:pk>/excluir/", views.AtividadeDeleteView.as_view(), name="excluir_atividade"),

    # --- Discente ---
    path("minhas-trilhas/", views.MinhasTrilhasListView.as_view(), name="minhas_trilhas"),
    path(
        "atividades/<int:pk>/concluir/",
        views.ConcluirAtividadeView.as_view(),
        name="concluir_atividade",
    ),
]
