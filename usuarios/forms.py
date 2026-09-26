from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django import forms

from .models import AceiteTermos


class LoginComTermosForm(AuthenticationForm):
    aceite_termos = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()

        user = self.get_user()
        if user is None:
            return cleaned_data  # credenciais inválidas, erro já tratado pelo Django

        ja_aceitou = AceiteTermos.objects.filter(
            usuario=user, versao=settings.TERMOS_DE_USO_VERSAO
        ).exists()

        if not ja_aceitou and not cleaned_data.get('aceite_termos'):
            self.add_error(
                'aceite_termos',
                'É necessário aceitar os Termos de Uso e a Política de Privacidade para continuar.',
            )

        return cleaned_data
