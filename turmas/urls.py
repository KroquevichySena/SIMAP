from django.urls import path

from . import views

urlpatterns = [
        path('', views.lista_turmas, name='lista_turmas' ),
        path('nova/', views.criar_turma, name='criar_turma'),
        path('matricular/', views.criar_matricula, name='criar_matricula'),
        path('<int:pk>/alunos/', views.matriculas_turma, name='matriculas_turma'),
        path('matricula/<int:pk>/status/', views.alterar_status_matricula, name='alterar_status_matricula'),

    ]
