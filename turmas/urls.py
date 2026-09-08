from django.urls import path
from . import views

urlpatterns = [
        path('', views.lista_turmas, name='lista_turmas' ),
        path('nova/', views.criar_turma, name='criar_turma'),

    ]