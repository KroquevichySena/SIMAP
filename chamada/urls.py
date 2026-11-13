from django.urls import path
from . import views

# O app_name é fundamental para organizar os links (namespacing)
app_name = 'chamada'

urlpatterns = [

    path('abrir/', views.abrir_chamada, name='abrir_chamada'),
    path('confirmar/', views.confirmar_presenca, name='confirmar_presenca'),
    path('confirmar/leitura/', views.confirmar_leitura, name='confirmar_leitura'),
    path('p/<str:token>/', views.ler_qr, name='ler_qr'),
    path('<int:pk>/', views.ao_vivo, name='ao_vivo'),
    path('<int:pk>/projecao/', views.projecao, name='projecao'),
    path('<int:pk>/estado/', views.estado_chamada, name='estado'),
    path('<int:pk>/renovar/', views.renovar_chamada, name='renovar'),
    path('<int:pk>/finalizar/', views.finalizar_chamada, name='finalizar'),
    path('presenca/<int:pk>/decidir/', views.decidir_presenca, name='decidir_presenca'),

]