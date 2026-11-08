from django import forms

from turmas.models import Turma


class LimiteAtencaoForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["limite_atencao"]
        widgets = {
            "limite_atencao": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.1", "min": 0, "max": 100}
            ),
        }
