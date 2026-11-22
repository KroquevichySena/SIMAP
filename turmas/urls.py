from django.urls import path

from . import views

urlpatterns = [
        path('', views.lista_turmas, name='lista_turmas' ),
        path('nova/', views.criar_turma, name='criar_turma'),
        path('matricular/', views.criar_matricula, name='criar_matricula'),
        path('<int:pk>/alunos/', views.matriculas_turma, name='matriculas_turma'),
        path('<int:pk>/configuracoes/', views.configurar_turma, name='configurar_turma'),
        path('matricula/<int:pk>/status/', views.alterar_status_matricula, name='alterar_status_matricula'),
        path('instituicoes/', views.InstituicaoListView.as_view(), name='lista_instituicoes'),
        path('instituicoes/nova/', views.InstituicaoCreateView.as_view(), name='criar_instituicao'),
        path('instituicoes/<int:pk>/editar/', views.InstituicaoUpdateView.as_view(), name='editar_instituicao'),
        path(
            'instituicoes/<int:pk>/turmas/nova/',
            views.TurmaDaInstituicaoCreateView.as_view(),
            name='criar_turma_instituicao',
        ),

    ]
