from django import forms
from .models import Chamada
from core.models import Turma

class AbrirChamadaForm(forms.ModelForm):
    class Meta:
        model = Chamada
        fields = ['turma', 'token_chamada', 'data_expiracao']
        widgets = {
            'data_expiracao': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'token_chamada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: AULA01 (Máx 6 letras)'}),
            'turma': forms.Select(attrs={'class': 'form-control'})
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