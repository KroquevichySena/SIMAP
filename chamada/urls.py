from django.urls import path
from . import views

# O app_name é fundamental para organizar os links (namespacing)
app_name = 'chamada'

urlpatterns = [

    path('abrir/', views.abrir_chamada, name='abrir_chamada'),
    path('confirmar/', views.confirmar_presenca, name='confirmar_presenca'),
]