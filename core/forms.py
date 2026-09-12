from django import forms

from .models import Atividade, TrilhaAprendizagem, Turma


class TrilhaAprendizagemForm(forms.ModelForm):
    class Meta:
        model = TrilhaAprendizagem
        fields = ["turma", "titulo", "descricao", "ordem", "publicada"]
        widgets = {
            "turma": forms.Select(attrs={"class": "form-select"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ordem": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        # ANTI-TAMPERING: recebe o docente logado para restringir o queryset de 'turma'
        docente = kwargs.pop('docente', None)
        super().__init__(*args, **kwargs)
        if docente is not None:
            self.fields['turma'].queryset = Turma.objects.filter(
                docente=docente, ativa=True
            )


class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ["trilha", "titulo", "enunciado", "tipo", "ordem", "prazo", "publicada"]
        widgets = {
            "trilha": forms.Select(attrs={"class": "form-select"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "enunciado": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control"}),
            "prazo": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        # ANTI-TAMPERING: recebe o docente logado para restringir o queryset de 'trilha'
        docente = kwargs.pop('docente', None)
        super().__init__(*args, **kwargs)
        if docente is not None:
            self.fields['trilha'].queryset = TrilhaAprendizagem.objects.filter(
                turma__docente=docente
            )
