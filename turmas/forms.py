from django import forms
from .models import Turma, Matricula
from django.contrib.auth import get_user_model


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['nome', 'periodo', 'ativa']
        labels = {'nome': 'Nome da turma', 'periodo': 'Período', 'ativa': 'Turma ativa'}
        help_texts = {
            'nome': 'Máximo de 100 caracteres.',
            'periodo': 'Informe o período letivo. Exemplo: 2026/2.',
            'ativa': 'Turmas inativas não aparecem na seleção de novas matrículas.',
        }
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'simap-input', 'placeholder': 'Ex.: Algoritmos e Programação I'}),
            'periodo': forms.TextInput(attrs={'class': 'simap-input', 'placeholder': 'Ex.: 2026/2'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'simap-checkbox'}),
        }

class MatriculaForm(forms.ModelForm):
    def __init__(self, *args, docente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['turma'].queryset = Turma.objects.filter(
            docente=docente,
            ativa=True,
        )
        self.fields['turma'].empty_label = 'Selecione uma turma'
        self.fields['discente'].empty_label = 'Selecione um discente'
        self.fields['discente'].queryset = get_user_model().objects.filter(
            perfil='DISCENTE',
            is_active=True,
        )

    class Meta:
        model = Matricula
        fields = ['turma', 'discente', 'status']
        labels = {'turma': 'Turma', 'discente': 'Discente', 'status': 'Situação da matrícula'}
        help_texts = {
            'turma': 'Somente as turmas ativas sob sua responsabilidade.',
            'discente': 'Somente discentes com conta ativa no sistema.',
            'status': 'A matrícula ativa permite ao aluno acessar os conteúdos da turma.',
        }
        widgets = {
            'turma': forms.Select(attrs={'class': 'simap-input'}),
            'discente': forms.Select(attrs={'class': 'simap-input'}),
            'status': forms.Select(attrs={'class': 'simap-input'}),
        }
