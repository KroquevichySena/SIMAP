from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario


class CadastroUsuarioForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ["first_name", "last_name", "username", "email", "perfil", "rgm"]
        labels = {"username": "Usuário de acesso", "rgm": "RGM"}
        help_texts = {
            "username": "Identificador que a pessoa utilizará para entrar no SIMAP.",
            "rgm": "Obrigatório para discentes. Para docentes, deixe em branco.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("first_name", "last_name", "email", "perfil"):
            self.fields[nome].required = True
        self.fields["password1"].label = "Senha inicial"
        self.fields["password2"].label = "Confirme a senha inicial"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "simap-input"

    def clean(self):
        dados = super().clean()
        if dados.get("perfil") == "DISCENTE" and not dados.get("rgm"):
            self.add_error("rgm", "Informe o RGM do discente.")
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        # Os privilégios administrativos nunca vêm do formulário ou do POST.
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.is_active = True
        if commit:
            usuario.save()
        return usuario


class AceitePrimeiroAcessoForm(forms.Form):
    aceite_termos = forms.BooleanField(
        label="Li e aceito os Termos de Uso e a Política de Privacidade",
        error_messages={"required": "É necessário aceitar os termos para continuar."},
        widget=forms.CheckboxInput(attrs={"class": "simap-checkbox"}),
    )
    versao = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["versao"].initial = settings.TERMOS_DE_USO_VERSAO

    def clean_versao(self):
        versao = self.cleaned_data["versao"]
        if versao != settings.TERMOS_DE_USO_VERSAO:
            raise forms.ValidationError("Os termos foram atualizados. Recarregue esta página antes de aceitar.")
        return versao
