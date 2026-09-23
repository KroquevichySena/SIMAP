from django.urls import path

from . import views

app_name = "entregas"

urlpatterns = [
    path("docente/atividades/<int:pk>/corrigir/", views.CorrigirAtividadeView.as_view(), name="corrigir"),
    path("docente/submissoes/<int:pk>/avaliar/", views.GravarNotaView.as_view(), name="avaliar"),
    path("docente/submissoes/<int:pk>/analise/tentar-novamente/", views.RetentarAnaliseView.as_view(), name="retentar_analise"),
    path("docente/atividades/<int:pk>/notificar-pendentes/", views.NotificarPendentesView.as_view(), name="notificar_pendentes"),
    path("atividades/<int:pk>/submeter/", views.SubmeterAtividadeView.as_view(), name="submeter"),

]
