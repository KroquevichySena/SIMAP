from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .permissoes import destinatarios_permitidos
from .seguranca import EXTENSOES_PERMITIDAS, validar_anexo

ACEITAR = ",".join(sorted(EXTENSOES_PERMITIDAS))


class VariosArquivosInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class VariosArquivosField(forms.FileField):
    """Campo que aceita vários arquivos de uma vez (receita da documentação do Django)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariosArquivosInput(attrs={"accept": ACEITAR}))
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        arquivos = data if isinstance(data, (list, tuple)) else [data]
        return [super(VariosArquivosField, self).clean(arquivo, initial) for arquivo in arquivos]


class MensagemBaseForm(forms.Form):
    texto = forms.CharField(
        label="Mensagem",
        max_length=settings.COMUNICACAO_TAMANHO_MAXIMO_TEXTO,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Escreva aqui. Links começando com https:// viram clicáveis."}),
    )
    anexos = VariosArquivosField(
        label="Anexos",
        help_text="Até {n} arquivos de até {mb} MB: PDF, Word, Excel, PowerPoint, imagens, texto e código-fonte.".format(
            n=settings.COMUNICACAO_MAXIMO_ANEXOS,
            mb=settings.COMUNICACAO_TAMANHO_MAXIMO_ANEXO // (1024 * 1024),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anexos_validados = []

    def clean_anexos(self):
        arquivos = self.cleaned_data.get("anexos") or []
        if len(arquivos) > settings.COMUNICACAO_MAXIMO_ANEXOS:
            raise ValidationError(
                f"Envie no máximo {settings.COMUNICACAO_MAXIMO_ANEXOS} arquivos por mensagem."
            )
        erros = []
        validados = []
        for arquivo in arquivos:
            try:
                validados.append((arquivo, validar_anexo(arquivo)))
            except ValidationError as erro:
                erros.extend(erro.messages)
        if erros:
            raise ValidationError(erros)
        self.anexos_validados = validados
        return arquivos


class PublicacaoForm(MensagemBaseForm):
    destinatario = forms.ModelChoiceField(
        label="Para",
        queryset=None,
        required=False,
        empty_label="Toda a turma (mural)",
        help_text="Escolha uma pessoa para enviar uma mensagem privada, que só ela verá.",
    )

    field_order = ["destinatario", "texto", "anexos"]

    def __init__(self, *args, usuario, turma, permitir_privada=True, **kwargs):
        super().__init__(*args, **kwargs)
        if permitir_privada:
            campo = self.fields["destinatario"]
            campo.queryset = destinatarios_permitidos(usuario, turma)
            campo.label_from_instance = lambda u: u.get_full_name() or u.username
        else:
            del self.fields["destinatario"]


class RespostaForm(MensagemBaseForm):
    pass
