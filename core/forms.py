"""
Formulários de trilha e de atividade.

Um cuidado importante: as listas de turmas e trilhas mostram só o que é do
docente logado. E não é só visual: se alguém forjar um POST com o ID da turma
de outro professor, o formulário recusa, porque aquele ID não está na lista.
"""
from django import forms
from django.utils import timezone

from turmas.models import Turma

from .models import Atividade, TrilhaAprendizagem


class BootstrapFormMixin:
    """Coloca as classes do Bootstrap nos campos, para o {{ form.as_p }} já sair bonito."""

    def _aplicar_bootstrap(self):
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class TrilhaAprendizagemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TrilhaAprendizagem
        fields = ["turma", "titulo", "descricao", "ordem", "publicada"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "titulo": forms.TextInput(
                attrs={"placeholder": "Ex.: Módulo 1 - Variáveis e Tipos"}
            ),
        }

    def __init__(self, *args, docente=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Só aparecem (e só são aceitas) as turmas ativas do próprio docente.
        if docente is not None:
            self.fields["turma"].queryset = Turma.objects.filter(
                docente=docente, ativa=True
            ).order_by("-periodo", "nome")
        else:
            self.fields["turma"].queryset = Turma.objects.none()
        self.fields["turma"].empty_label = "Selecione a turma"
        self._aplicar_bootstrap()


class AtividadeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ["trilha", "titulo", "enunciado", "tipo", "ordem", "prazo", "publicada"]
        widgets = {
            "enunciado": forms.Textarea(attrs={"rows": 6}),
            "prazo": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, docente=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Mesma ideia: só as trilhas das turmas desse docente.
        if docente is not None:
            self.fields["trilha"].queryset = (
                TrilhaAprendizagem.objects.filter(turma__docente=docente)
                .select_related("turma")
                .order_by("turma__nome", "ordem")
            )
        else:
            self.fields["trilha"].queryset = TrilhaAprendizagem.objects.none()
        self.fields["trilha"].empty_label = "Selecione a trilha"

        if self.instance and self.instance.pk and self.instance.prazo:
            self.initial["prazo"] = timezone.localtime(self.instance.prazo).strftime(
                "%Y-%m-%dT%H:%M"
            )
        self._aplicar_bootstrap()

    def clean_prazo(self):
        prazo = self.cleaned_data.get("prazo")
        if prazo and not self.instance.pk and prazo < timezone.now():
            raise forms.ValidationError("O prazo informado já expirou. Escolha uma data futura.")
        return prazo
