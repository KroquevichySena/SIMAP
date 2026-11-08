"""
Formulários de trilha e de atividade.

Um cuidado importante: as listas de turmas e trilhas mostram só o que é do
docente logado. E não é só visual: se alguém forjar um POST com o ID da turma
de outro professor, o formulário recusa, porque aquele ID não está na lista.
"""
from django import forms
from django.utils import timezone

from comunicacao.arquivos import validar_arquivos
from comunicacao.forms import VariosArquivosField
from turmas.models import Turma

from .models import Atividade, CasoDeTeste, MaterialDeApoio, TrilhaAprendizagem
from .youtube import codigo_do_video, endereco_para_assistir

MAXIMO_VIDEOS = 10


class BootstrapFormMixin:
    """Coloca as classes do Bootstrap nos campos, para o {{ form.as_p }} já sair bonito."""

    def _aplicar_bootstrap(self):
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class MaterialDeApoioMixin(forms.Form):
    """
    Campos de material de apoio, comuns à trilha e à atividade.

    - "materiais": arquivos novos, validados como os anexos da comunicação.
    - "remover_materiais": na edição, os arquivos que o professor quer tirar.
    """

    materiais = VariosArquivosField(
        label="Material de apoio (opcional)",
        help_text="PDF, Word, Excel, PowerPoint, imagens, texto ou código-fonte. "
        "Até 5 arquivos por vez, de até 10 MB cada. Executáveis, compactados e "
        "documentos com macro são bloqueados.",
    )
    remover_materiais = forms.ModelMultipleChoiceField(
        label="Remover material já enviado",
        queryset=MaterialDeApoio.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    videos = forms.CharField(
        label="Vídeos do YouTube (opcional)",
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 2,
            "placeholder": "https://www.youtube.com/watch?v=...\nhttps://youtu.be/...",
        }),
        help_text=f"Cole um link por linha (até {MAXIMO_VIDEOS}). Só links do YouTube são aceitos; "
        "o vídeo aparece com o player na tela do aluno.",
    )

    def _preparar_materiais(self):
        self.materiais_validados = []
        self.videos_validados = []
        if self.instance.pk and not self.is_bound:
            self.initial["videos"] = "\n".join(
                v.endereco_para_assistir for v in self.instance.videos.all()
            )
        if self.instance.pk:
            campo = self.fields["remover_materiais"]
            campo.queryset = self.instance.materiais.all()
            campo.label_from_instance = lambda m: f"{m.nome_original} ({m.tamanho_legivel})"
            if not campo.queryset.exists():
                del self.fields["remover_materiais"]
        else:
            del self.fields["remover_materiais"]

    def clean_videos(self):
        texto = self.cleaned_data.get("videos") or ""
        codigos, invalidos = [], []
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            codigo = codigo_do_video(linha)
            if codigo is None:
                invalidos.append(linha[:80])
            elif codigo not in codigos:
                codigos.append(codigo)
        if invalidos:
            raise forms.ValidationError(
                "Estes links não são vídeos do YouTube: " + "; ".join(invalidos)
            )
        if len(codigos) > MAXIMO_VIDEOS:
            raise forms.ValidationError(f"Indique no máximo {MAXIMO_VIDEOS} vídeos.")
        self.videos_validados = codigos
        return "\n".join(endereco_para_assistir(c) for c in codigos)

    def clean_materiais(self):
        arquivos = self.cleaned_data.get("materiais") or []
        self.materiais_validados = validar_arquivos(arquivos)
        return arquivos


class TrilhaAprendizagemForm(MaterialDeApoioMixin, BootstrapFormMixin, forms.ModelForm):
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
        self._preparar_materiais()
        self._aplicar_bootstrap()


class AtividadeForm(MaterialDeApoioMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Atividade
        fields = [
            "trilha", "titulo", "enunciado", "tipo", "codigo_inicial", "ordem", "prazo", "publicada",
            "ajuda_ia", "ajuda_ia_nivel_maximo",
        ]
        widgets = {
            "enunciado": forms.Textarea(attrs={"rows": 6}),
            "codigo_inicial": forms.Textarea(attrs={
                "rows": 5, "spellcheck": "false", "class": "form-control font-monospace",
                "placeholder": "def soma(a, b):\n    # complete aqui\n    pass",
            }),
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
        # Espaços no começo do código importam em Python: nada de "strip".
        self.fields["codigo_inicial"].strip = False
        self.fields["ajuda_ia_nivel_maximo"].required = False
        # Um envio sem os campos da IA (formulário antigo, teste, API) não
        # pode desligar a ajuda sem querer: a caixa desmarcada some do POST.
        if self.is_bound and "ajuda_ia_nivel_maximo" not in self.data:
            del self.fields["ajuda_ia"]
            del self.fields["ajuda_ia_nivel_maximo"]

        if self.instance and self.instance.pk and self.instance.prazo:
            self.initial["prazo"] = timezone.localtime(self.instance.prazo).strftime(
                "%Y-%m-%dT%H:%M"
            )
        self._preparar_materiais()
        self._aplicar_bootstrap()

    def is_valid(self):
        # Os casos de teste vêm num formset à parte, mas fazem parte do mesmo
        # formulário para o professor: se um caso estiver errado, nada é salvo.
        valido = super().is_valid()
        casos = getattr(self, "casos", None)
        return valido and (casos is None or not casos.is_bound or casos.is_valid())

    def clean_ajuda_ia_nivel_maximo(self):
        return self.cleaned_data.get("ajuda_ia_nivel_maximo") or self.instance.ajuda_ia_nivel_maximo or 3

    def clean_prazo(self):
        prazo = self.cleaned_data.get("prazo")
        if prazo and not self.instance.pk and prazo < timezone.now():
            raise forms.ValidationError("O prazo informado já expirou. Escolha uma data futura.")
        return prazo


MAXIMO_CASOS_DE_TESTE = 10
LIMITE_TEXTO_CASO = 5000


class CasoDeTesteForm(forms.ModelForm):
    class Meta:
        model = CasoDeTeste
        fields = ["entrada", "saida_esperada"]
        widgets = {
            "entrada": forms.Textarea(attrs={
                "rows": 3, "spellcheck": "false", "class": "form-control form-control-sm font-monospace",
                "placeholder": "7",
            }),
            "saida_esperada": forms.Textarea(attrs={
                "rows": 3, "spellcheck": "false", "class": "form-control form-control-sm font-monospace",
                "placeholder": "Tabuada de: 7\n7 x 1 = 7",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Espaços no começo de uma linha da saída fazem parte da resposta
        # (um desenho com asteriscos, por exemplo).
        for campo in ("entrada", "saida_esperada"):
            self.fields[campo].strip = False

    def clean(self):
        dados = super().clean()
        for campo in ("entrada", "saida_esperada"):
            if len(dados.get(campo) or "") > LIMITE_TEXTO_CASO:
                self.add_error(campo, f"Use no máximo {LIMITE_TEXTO_CASO} caracteres.")
        return dados


CasoDeTesteFormSet = forms.inlineformset_factory(
    Atividade,
    CasoDeTeste,
    form=CasoDeTesteForm,
    extra=1,
    max_num=MAXIMO_CASOS_DE_TESTE,
    validate_max=True,
    can_delete=True,
)
