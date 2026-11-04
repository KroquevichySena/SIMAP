from django import forms
from .models import Turma, Matricula
from django.contrib.auth import get_user_model


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['nome', 'periodo', 'ativa']

class MatriculaForm(forms.ModelForm):
    def __init__(self, *args, docente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['turma'].queryset = Turma.objects.filter(
        docente=docente,
        ativa=True,
        )
        self.fields['discente'].queryset = get_user_model().objects.filter(
            perfil='DISCENTE',
            is_active=True,
        )

    class Meta:
        model = Matricula
        fields = ['turma', 'discente', 'status']