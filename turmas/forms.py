from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .coordenadas import CoordenadaInvalida, ler_coordenadas
from .models import Instituicao, Matricula, Turma


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["nome", "periodo", "ativa", "limite_atencao"]
        labels = {
            "nome": "Nome da turma",
            "periodo": "Período",
            "ativa": "Turma ativa",
            "limite_atencao": "Limite de atenção (%)",
        }
        help_texts = {
            "nome": "Máximo de 100 caracteres.",
            "periodo": "Informe o período letivo. Exemplo: 2026/2.",
            "ativa": "Turmas inativas não aparecem na seleção de novas matrículas.",
            "limite_atencao": (
                "O aluno é sinalizado se frequência, entregas ou progresso calculável "
                "ficar abaixo deste percentual. Padrão: 60%."
            ),
        }
        widgets = {
            "nome": forms.TextInput(attrs={"class": "simap-input", "placeholder": "Ex.: Algoritmos e Programação I"}),
            "periodo": forms.TextInput(attrs={"class": "simap-input", "placeholder": "Ex.: 2026/2"}),
            "ativa": forms.CheckboxInput(attrs={"class": "simap-checkbox"}),
            "limite_atencao": forms.NumberInput(attrs={"class": "simap-input", "min": 0, "max": 100, "step": "0.1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["limite_atencao"].required = False

    def clean_limite_atencao(self):
        limite = self.cleaned_data.get("limite_atencao")
        return self.instance.limite_atencao if limite is None else limite


class LimiteAtencaoForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["limite_atencao"]
        labels = {"limite_atencao": "Limite de atenção (%)"}
        help_texts = {
            "limite_atencao": (
                "Sinaliza o aluno quando algum indicador calculável de frequência, entregas ou progresso "
                "ficar abaixo do limite. Valores iguais ao limite não geram alerta."
            )
        }
        widgets = {
            "limite_atencao": forms.NumberInput(attrs={"class": "simap-input", "min": 0, "max": 100, "step": "0.1"})
        }


class MatriculaForm(forms.ModelForm):
    def __init__(self, *args, docente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turma"].queryset = Turma.objects.filter(
            docente=docente,
            ativa=True,
        )
        self.fields["turma"].empty_label = "Selecione uma turma"
        self.fields["discente"].empty_label = "Selecione um discente"
        self.fields["discente"].queryset = get_user_model().objects.filter(
            perfil="DISCENTE",
            is_active=True,
        )

    class Meta:
        model = Matricula
        fields = ["turma", "discente", "status"]
        labels = {"turma": "Turma", "discente": "Discente", "status": "Situação da matrícula"}
        help_texts = {
            "turma": "Somente as turmas ativas sob sua responsabilidade.",
            "discente": "Somente discentes com conta ativa no sistema.",
            "status": "A matrícula ativa permite ao aluno acessar os conteúdos da turma.",
        }
        widgets = {
            "turma": forms.Select(attrs={"class": "simap-input"}),
            "discente": forms.Select(attrs={"class": "simap-input"}),
            "status": forms.Select(attrs={"class": "simap-input"}),
        }


class InstituicaoForm(forms.ModelForm):
    coordenadas = forms.CharField(
        label="Coordenadas",
        required=False,
        max_length=60,
        widget=forms.TextInput(attrs={"class": "simap-input", "placeholder": "Ex.: 23°31'02.1\"S 46°10'58.5\"W"}),
        help_text="Cole como aparece no Google Maps, com a latitude primeiro. Também aceita -23.517250, -46.182917. "
        "Deixe em branco para não conferir a localização na chamada.",
    )
    turmas = forms.ModelMultipleChoiceField(
        label="Turmas desta instituição",
        queryset=Turma.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "simap-checkbox"}),
        help_text="A chamada das turmas marcadas vai conferir se o aluno está dentro do raio. "
        "Aparecem aqui só as turmas desta instituição e as que ainda não têm nenhuma.",
    )

    class Meta:
        model = Instituicao
        fields = ["nome", "raio_metros", "precisao_minima"]
        labels = {"nome": "Nome da instituição"}
        help_texts = {
            "raio_metros": "Distância máxima entre o aluno e a instituição. De 50 a 1000 metros.",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"class": "simap-input", "placeholder": "Ex.: Campus Mogi das Cruzes"}),
            "raio_metros": forms.NumberInput(attrs={"class": "simap-input", "min": 50, "max": 1000}),
            "precisao_minima": forms.NumberInput(attrs={"class": "simap-input", "min": 20, "max": 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Turma de outra instituição não aparece nem é aceita num POST forjado.
        disponiveis = Q(instituicao__isnull=True)
        if self.instance.pk:
            disponiveis |= Q(instituicao=self.instance)
            self.fields["turmas"].initial = self.instance.turmas.all()
            if self.instance.tem_localizacao:
                self.fields["coordenadas"].initial = f"{self.instance.latitude}, {self.instance.longitude}"
        self.fields["turmas"].queryset = (
            Turma.objects.filter(disponiveis).select_related("docente").order_by("-ativa", "nome")
        )
        self.fields["turmas"].label_from_instance = self._nome_da_turma

    @staticmethod
    def _nome_da_turma(turma):
        docente = turma.docente.get_full_name() or turma.docente.username
        situacao = "" if turma.ativa else " · inativa"
        return f"{turma} ({docente}){situacao}"

    def clean_coordenadas(self):
        texto = self.cleaned_data.get("coordenadas", "").strip()
        if not texto:
            return None
        try:
            return ler_coordenadas(texto)
        except CoordenadaInvalida as erro:
            raise forms.ValidationError(str(erro)) from erro

    def clean(self):
        dados = super().clean()
        # O modelo guarda latitude e longitude separadas; o campo de texto só serve para colar do Maps.
        if "coordenadas" in dados:
            self.instance.latitude, self.instance.longitude = dados["coordenadas"] or (None, None)
        return dados

    def save(self, commit=True):
        instituicao = super().save(commit=commit)
        if commit:
            self._vincular_turmas(instituicao)
        return instituicao

    def _vincular_turmas(self, instituicao):
        marcadas = {turma.pk for turma in self.cleaned_data["turmas"]}
        # Salvamos turma por turma, e não com update(), para a auditoria
        # registrar cada mudança de vínculo pelos sinais do post_save.
        for turma in instituicao.turmas.exclude(pk__in=marcadas):
            turma.instituicao = None
            turma.save(update_fields=["instituicao"])
        for turma in Turma.objects.filter(pk__in=marcadas).exclude(instituicao=instituicao):
            turma.instituicao = instituicao
            turma.save(update_fields=["instituicao"])


class TurmaDaInstituicaoForm(TurmaForm):
    """A coordenação cria a turma já dentro da instituição e escolhe o docente."""

    class Meta(TurmaForm.Meta):
        fields = ["nome", "periodo", "docente", "ativa", "limite_atencao"]
        labels = {**TurmaForm.Meta.labels, "docente": "Docente responsável"}
        widgets = {**TurmaForm.Meta.widgets, "docente": forms.Select(attrs={"class": "simap-input"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["docente"].queryset = get_user_model().objects.filter(
            perfil="DOCENTE", is_active=True
        ).order_by("first_name", "username")
        self.fields["docente"].empty_label = "Selecione o docente"
        self.fields["docente"].label_from_instance = lambda u: u.get_full_name() or u.username
