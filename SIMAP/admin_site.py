from django import forms
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm


class CoordenacaoAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_coordenacao:
            raise forms.ValidationError("O painel administrativo é exclusivo da coordenação.", code="invalid_login")


class SimapAdminSite(AdminSite):
    login_form = CoordenacaoAdminAuthenticationForm

    def has_permission(self, request):
        # O perfil não concede automaticamente flags nem permissões técnicas do Django.
        return super().has_permission(request) and request.user.is_coordenacao
