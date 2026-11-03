from django import forms
from .models import Turma, Matricula


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
    class Meta:
        model = Matricula
        fields = ['turma', 'discente', 'status']