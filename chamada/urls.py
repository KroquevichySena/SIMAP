from django.urls import path
from . import views

# O app_name é fundamental para organizar os links (namespacing)
app_name = 'chamada'

urlpatterns = [
    # A rota será acessada via /chamada/abrir/
    path('abrir/', views.abrir_chamada, name='abrir_chamada'),
]