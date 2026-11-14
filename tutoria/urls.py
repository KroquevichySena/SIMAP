from django.urls import path

from . import views

app_name = "tutoria"

urlpatterns = [
    path("atividades/<int:pk>/", views.AjudaAtividadeView.as_view(), name="atividade"),
    path("atividades/<int:pk>/pedir/", views.PedirAjudaView.as_view(), name="pedir"),
]
