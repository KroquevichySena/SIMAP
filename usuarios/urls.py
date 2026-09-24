from django.urls import path
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='usuarios/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('recuperar-senha/', 
     auth_views.PasswordResetView.as_view(template_name='usuarios/recuperar_senha.html'),
     name='password_reset'),

    path('recuperar-senha/enviado/', 
     auth_views.PasswordResetDoneView.as_view(template_name='usuarios/recuperar_senha_enviado.html'),
     name='password_reset_done'),

    path('resetar-senha/<uidb64>/<token>/', 
     auth_views.PasswordResetConfirmView.as_view(template_name='usuarios/resetar_senha.html'),
     name='password_reset_confirm'),

    path('resetar-senha/concluido/', 
     auth_views.PasswordResetCompleteView.as_view(template_name='usuarios/resetar_senha_concluido.html'),
     name='password_reset_complete'),
]