from django import forms
from django.contrib.auth.forms import AdminPasswordChangeForm, PasswordChangeForm, SetPasswordForm, UserCreationForm
from django.utils.html import format_html

from .models import Usuario, VersaoTermos
from .termos import FORMATO_NUMERO, chave_numero, numero_vigente


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
        # Esta tela cadastra contas acadêmicas; não concede a gestão da plataforma.
        self.fields["perfil"].choices = [("DOCENTE", "Docente"), ("DISCENTE", "Discente")]
        for nome in ("first_name", "last_name", "email", "perfil"):
            self.fields[nome].required = True
        self.fields["password1"].label = "Senha temporária"
        self.fields["password2"].label = "Confirme a senha temporária"
        self.fields["password1"].help_text = format_html(
            "{}<p>{}</p>", self.fields["password1"].help_text,
            "A pessoa deverá substituí-la por uma senha diferente no primeiro acesso.",
        )
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
        usuario.troca_senha_obrigatoria = True
        if commit:
            usuario.save()
        return usuario


class SenhaPessoalMixin:
    """A troca e a recuperação só liberam o acesso depois de salvar a nova senha."""

    def clean(self):
        dados = super().clean()
        senha = dados.get("new_password2")
        if senha and self.user.troca_senha_obrigatoria and self.user.check_password(senha):
            self.add_error("new_password2", "Escolha uma senha diferente da senha temporária.")
        return dados

    def save(self, commit=True):
        self.user.troca_senha_obrigatoria = False
        return super().save(commit=commit)


class TrocaSenhaTemporariaForm(SenhaPessoalMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Senha atual"
        self.fields["new_password1"].label = "Sua nova senha"
        self.fields["new_password2"].label = "Confirme sua nova senha"


class RedefinirSenhaForm(SenhaPessoalMixin, SetPasswordForm):
    pass


class SenhaTemporariaAdminForm(AdminPasswordChangeForm):
    """Uma senha definida pela coordenação no Admin também é temporária."""

    def save(self, commit=True):
        self.user.troca_senha_obrigatoria = True
        return super().save(commit=commit)


class AceitePrimeiroAcessoForm(forms.Form):
    aceite_termos = forms.BooleanField(
        label=(
            "Li e aceito os Termos de Uso e a Política de Privacidade, inclusive o envio das minhas "
            "submissões e dos meus pedidos de ajuda ao serviço de inteligência artificial (Cláusula 12)"
        ),
        error_messages={"required": "É necessário aceitar os termos para continuar."},
        widget=forms.CheckboxInput(attrs={"class": "simap-checkbox"}),
    )
    versao = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["versao"].initial = numero_vigente()

    def clean_versao(self):
        versao = self.cleaned_data["versao"]
        if versao != numero_vigente():
            raise forms.ValidationError("Os termos foram atualizados. Recarregue esta página antes de aceitar.")
        return versao


class ConfirmacaoGestaoUsuarioForm(forms.Form):
    confirmar = forms.BooleanField(
        label="Confirmo que desejo realizar esta ação nesta conta.",
        error_messages={"required": "Confirme a ação antes de continuar."},
        widget=forms.CheckboxInput(attrs={"class": "simap-checkbox"}),
    )


class NovaVersaoTermosForm(forms.ModelForm):
    """Publicação de uma nova versão dos termos pela coordenação."""

    confirmar = forms.BooleanField(
        required=False,
        label="Entendo que, ao publicar, todos os usuários precisarão aceitar esta versão no próximo acesso.",
        widget=forms.CheckboxInput(attrs={"class": "simap-checkbox"}),
    )

    class Meta:
        model = VersaoTermos
        fields = ["numero", "o_que_mudou", "resumo", "texto"]
        widgets = {
            "numero": forms.TextInput(attrs={"class": "simap-input", "placeholder": "Ex.: 1.4"}),
            "o_que_mudou": forms.Textarea(attrs={"class": "simap-input", "rows": 4}),
            "resumo": forms.Textarea(attrs={"class": "simap-input", "rows": 6}),
            "texto": forms.Textarea(attrs={"class": "simap-input simap-termos-editor", "rows": 24}),
        }
        help_texts = {
            "numero": "Números separados por ponto, maior que a versão vigente.",
            "texto": (
                "Formato: \"# \" abre uma cláusula, \"## \" um subtítulo, \"- \" um item de lista, "
                "\"> \" uma citação e \"---\" o rodapé. Use **negrito** e *itálico*. "
                "Uma linha em branco separa os parágrafos."
            ),
        }

    def __init__(self, *args, publicar=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirmar"].required = publicar
        self.fields["confirmar"].error_messages["required"] = "Confirme antes de publicar a nova versão."

    def clean_numero(self):
        numero = self.cleaned_data["numero"].strip()
        if not FORMATO_NUMERO.match(numero):
            raise forms.ValidationError("Use apenas números separados por ponto, como 1.4 ou 2.0.")
        vigente = numero_vigente()
        if FORMATO_NUMERO.match(vigente) and chave_numero(numero) <= chave_numero(vigente):
            raise forms.ValidationError(f"A nova versão precisa ser maior que a vigente ({vigente}).")
        return numero

    def clean_texto(self):
        texto = self.cleaned_data["texto"]
        if not any(linha.startswith("# ") for linha in texto.splitlines()):
            raise forms.ValidationError("O texto precisa ter ao menos uma cláusula, começando com \"# \".")
        return texto
