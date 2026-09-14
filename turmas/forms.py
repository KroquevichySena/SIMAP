from django import forms
from .models import Turma, Matricula


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['nome', 'periodo', 'docente', 'ativa']

class MatriculaForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = ['turma', 'discente', 'status']