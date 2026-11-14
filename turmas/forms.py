from django import forms
from .models import Turma, Matricula
from django.contrib.auth import get_user_model


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['nome', 'periodo', 'ativa', 'limite_atencao']
        labels = {'nome': 'Nome da turma', 'periodo': 'Período', 'ativa': 'Turma ativa', 'limite_atencao': 'Limite de atenção (%)'}
        help_texts = {
            'nome': 'Máximo de 100 caracteres.',
            'periodo': 'Informe o período letivo. Exemplo: 2026/2.',
            'ativa': 'Turmas inativas não aparecem na seleção de novas matrículas.',
            'limite_atencao': 'O aluno é sinalizado se frequência, entregas ou progresso calculável ficar abaixo deste percentual. Padrão: 60%.',
        }
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'simap-input', 'placeholder': 'Ex.: Algoritmos e Programação I'}),
            'periodo': forms.TextInput(attrs={'class': 'simap-input', 'placeholder': 'Ex.: 2026/2'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'simap-checkbox'}),
            'limite_atencao': forms.NumberInput(attrs={'class': 'simap-input', 'min': 0, 'max': 100, 'step': '0.1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['limite_atencao'].required = False

    def clean_limite_atencao(self):
        limite = self.cleaned_data.get('limite_atencao')
        return self.instance.limite_atencao if limite is None else limite


class LimiteAtencaoForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['limite_atencao']
        labels = {'limite_atencao': 'Limite de atenção (%)'}
        help_texts = {'limite_atencao': 'Sinaliza o aluno quando algum indicador calculável de frequência, entregas ou progresso ficar abaixo do limite. Valores iguais ao limite não geram alerta.'}
        widgets = {'limite_atencao': forms.NumberInput(attrs={'class': 'simap-input', 'min': 0, 'max': 100, 'step': '0.1'})}


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
