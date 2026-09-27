from django.urls import path

from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.RegistroAuditoriaListView.as_view(), name="registro_list"),
]
