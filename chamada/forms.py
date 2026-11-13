from django import forms

from .models import Chamada, Registro_de_Presenca
from turmas.models import Matricula, Turma


class AbrirChamadaForm(forms.ModelForm):
    limite_uso = forms.IntegerField(
        label="Limite de presenças",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Automático'}),
        help_text="Deixe em branco para usar o total de alunos com matrícula ativa. "
        "Em dias com poucos alunos, informe quantos estão na sala.",
    )

    class Meta:
        model = Chamada
        fields = ['turma', 'ciclo_segundos', 'limite_uso']
        widgets = {
            'turma': forms.Select(attrs={'class': 'form-select'}),
            'ciclo_segundos': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'ciclo_segundos': "Quando o tempo acaba, a chamada fecha. Você pode renovar se alguém chegou atrasado.",
        }

    def __init__(self, *args, **kwargs):
        professor = kwargs.pop('professor', None)
        super().__init__(*args, **kwargs)

        if professor:
            self.fields['turma'].queryset = Turma.objects.filter(docente=professor, ativa=True)

    def save(self, commit=True):
        chamada = super().save(commit=False)
        if not self.cleaned_data.get('limite_uso'):
            ativos = Matricula.objects.filter(turma=chamada.turma, status='ATIVA').count()
            chamada.limite_uso = max(ativos, 1)
        chamada.iniciar_ciclo()
        if commit:
            chamada.save()
        return chamada


class ConfirmarPresencaForm(forms.Form):
    """Formulário enxuto: usuário, turma da aula e token — pensado pra prazo curto."""


    turma = forms.ModelChoiceField(
        label="Turma",
        queryset=Turma.objects.filter(ativa=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    token_chamada = forms.CharField(
        label="Token",
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-uppercase',
            'placeholder': 'Ex: AULA01',
            'autofocus': True
        }),
    )

    def __init__(self, *args, **kwargs):
        self.discente = kwargs.pop('discente', None)
        super().__init__(*args, **kwargs)

    def clean_token_chamada(self):
        return self.cleaned_data.get('token_chamada', '').upper()

    def clean(self):
        cleaned_data = super().clean()
        turma = cleaned_data.get('turma')
        token = cleaned_data.get('token_chamada')

        discente = self.discente

        if not (turma and token and discente):
            return cleaned_data  # já tem erro de campo individual, não precisa empilhar

        #o aluno só confirma presença em turma na qual está de fato matriculado .
        if not Matricula.objects.filter(turma=turma, discente=discente, status='ATIVA').exists():
            raise forms.ValidationError("Você não está matriculado nesta turma.")

        try:
            chamada = Chamada.objects.get(token_chamada=token, turma=turma)
        except Chamada.DoesNotExist:
            raise forms.ValidationError("Token inválido para a turma selecionada.")

        if not chamada.esta_valida:
            motivo = "expirou" if chamada.esta_expirada else "atingiu o limite de uso"
            raise forms.ValidationError(f"Essa chamada já {motivo}.")

        if Registro_de_Presenca.objects.filter(chamada=chamada, discente=discente).exists():
            raise forms.ValidationError("Você já confirmou presença nesta chamada.")

        self.chamada = chamada
        return cleaned_data
