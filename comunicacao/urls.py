from django.urls import path

from . import views

app_name = "comunicacao"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("turmas/<int:turma_id>/", views.MuralView.as_view(), name="mural"),
    path("atividades/<int:atividade_id>/", views.ComentariosAtividadeView.as_view(), name="atividade"),
    path("publicacoes/<int:pk>/", views.PublicacaoView.as_view(), name="publicacao"),
    path("publicacoes/<int:pk>/apagar/", views.ApagarPublicacaoView.as_view(), name="publicacao_apagar"),
    path("respostas/<int:pk>/apagar/", views.ApagarRespostaView.as_view(), name="resposta_apagar"),
    path("anexos/<int:pk>/", views.BaixarAnexoView.as_view(), name="anexo"),
    path("notificacoes/", views.NotificacoesView.as_view(), name="notificacoes"),
    path("notificacoes/<int:pk>/abrir/", views.AbrirNotificacaoView.as_view(), name="notificacao_abrir"),
    path("notificacoes/marcar-todas/", views.MarcarTodasLidasView.as_view(), name="notificacoes_marcar_todas"),
]
