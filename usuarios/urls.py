from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import RedefinirSenhaForm

urlpatterns = [
    path("login/", views.LoginView.as_view(template_name="usuarios/login.html"), name="login"),
    path("primeiro-acesso/", views.PrimeiroAcessoView.as_view(), name="primeiro_acesso"),
    path("trocar-senha-temporaria/", views.TrocarSenhaTemporariaView.as_view(), name="trocar_senha_temporaria"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuarios_lista"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_criar"),
    path("usuarios/<int:pk>/<str:acao>/", views.UsuarioAcaoView.as_view(), name="usuario_acao"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("termos-de-uso/", views.TermosDeUsoView.as_view(), name="termos_de_uso"),
    path("termos-de-uso/versoes/", views.VersoesTermosView.as_view(), name="versoes_termos"),
    path("termos-de-uso/versoes/nova/", views.NovaVersaoTermosView.as_view(), name="nova_versao_termos"),
    path("termos-de-uso/versoes/<str:numero>/", views.TermosDeUsoView.as_view(), name="termos_de_uso_versao"),
    path(
        "recuperar-senha/",
        auth_views.PasswordResetView.as_view(template_name="usuarios/recuperar_senha.html"),
        name="password_reset",
    ),
    path(
        "recuperar-senha/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="usuarios/recuperar_senha_enviado.html"),
        name="password_reset_done",
    ),
    path(
        "resetar-senha/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="usuarios/resetar_senha.html", form_class=RedefinirSenhaForm
        ),
        name="password_reset_confirm",
    ),
    path(
        "resetar-senha/concluido/",
        auth_views.PasswordResetCompleteView.as_view(template_name="usuarios/resetar_senha_concluido.html"),
        name="password_reset_complete",
    ),
]
