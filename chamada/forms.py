from django import forms
from django.contrib.auth import get_user_model

from .models import Chamada, Registro_de_Presenca
from turmas.models import Matricula, Turma

Usuario = get_user_model()

class AbrirChamadaForm(forms.ModelForm):
    class Meta:
        model = Chamada
        fields = ['turma', 'token_chamada', 'data_expiracao', 'limite_uso']
        widgets = {
            'data_expiracao': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'token_chamada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: AULA01 (Máx 6 letras)'}),
            'turma': forms.Select(attrs={'class': 'form-control'}),
            'limite_uso': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
      
    def __init__(self, *args, **kwargs):
        professor = kwargs.pop('professor', None)
        super().__init__(*args, **kwargs)
        
        if professor:
            self.fields['turma'].queryset = Turma.objects.filter(docente=professor, ativa=True)
            
    def clean_token_chamada(self):
        token = self.cleaned_data.get('token_chamada')
        if token:
            return token.upper()
        return token

class ConfirmarPresencaForm(forms.Form):
    """Formulário enxuto: usuário, turma da aula e token — pensado pra prazo curto."""

    username = forms.CharField(
        label="Usuário",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Seu usuário',
            'autofocus': True,
        }),
    )
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
        }),
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            self.discente = Usuario.objects.get(
                username=username, perfil='DISCENTE', is_active=True
            )
        except Usuario.DoesNotExist:
            raise forms.ValidationError("Usuário não encontrado ou não é um discente ativo.")
        return username

    def clean_token_chamada(self):
        return self.cleaned_data.get('token_chamada', '').upper()

    def clean(self):
        cleaned_data = super().clean()
        turma = cleaned_data.get('turma')
        token = cleaned_data.get('token_chamada')
        discente = getattr(self, 'discente', None)

        if not (turma and token and discente):
            return cleaned_data  # já tem erro de campo individual, não precisa empilhar

        # ANTI-TAMPERING: o aluno só confirma presença em turma na qual está
        # de fato matriculado (não basta escolher a turma no <select>).
        if not Matricula.objects.filter(turma=turma, discente=discente).exists():
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

    def save(self):
        return Registro_de_Presenca.objects.create(chamada=self.chamada, discente=self.discente)
