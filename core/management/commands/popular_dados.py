"""
Popula o banco com dados fictícios para demonstrar a Funcionalidade 7
(Trilhas de Aprendizagem e Publicação de Atividades).

Uso:
    python manage.py popular_dados
    python manage.py popular_dados --limpar    (apaga os dados de demo antes)

ATENÇÃO: comando destinado a desenvolvimento e demonstração. Não executar
em ambiente de produção.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Atividade, ConclusaoAtividade, TrilhaAprendizagem
from turmas.models import Matricula, Turma

Usuario = get_user_model()

SENHA_PADRAO = "Simap@2026"

DOCENTES = [
    ("prof.alessandro", "Alessandro", "Horas"),
]

DISCENTES = [
    ("aluno.kaiky", "Kaiky", "Kroquevichy", "11231102733"),
    ("aluno.carlos", "Carlos Eduardo", "Pereira", "11231102525"),
    ("aluno.vinicius", "Vinicius", "Santana", "11231103599"),
    ("aluno.mariana", "Mariana", "Lopes", "11231104001"),
]

TRILHAS = [
    {
        "titulo": "Módulo 1 - Variáveis e tipos de dados",
        "descricao": (
            "Primeiros conceitos de programação: como armazenar e representar "
            "informação na memória."
        ),
        "ordem": 1,
        "publicada": True,
        "atividades": [
            {
                "titulo": "Questionário de tipos primitivos",
                "enunciado": (
                    "Explique com suas palavras a diferença entre os tipos "
                    "inteiro, ponto flutuante, booleano e texto. Dê um exemplo "
                    "de uso para cada um deles."
                ),
                "ordem": 1,
                "dias_prazo": 7,
            },
            {
                "titulo": "Exercício de declaração de variáveis",
                "enunciado": (
                    "Escreva, em pseudocódigo, a declaração de variáveis para "
                    "armazenar: o nome de um aluno, sua idade e sua média final."
                ),
                "ordem": 2,
                "dias_prazo": 10,
            },
            {
                "titulo": "Leitura dirigida - Capítulo 1",
                "enunciado": (
                    "Leia o capítulo 1 do material da disciplina e liste três "
                    "dúvidas que surgiram durante a leitura."
                ),
                "ordem": 3,
                "dias_prazo": None,
            },
        ],
    },
    {
        "titulo": "Módulo 2 - Estruturas condicionais",
        "descricao": "Tomada de decisão em algoritmos: se, senão e aninhamentos.",
        "ordem": 2,
        "publicada": True,
        "atividades": [
            {
                "titulo": "Tabela verdade dos operadores lógicos",
                "enunciado": (
                    "Monte a tabela verdade dos operadores E, OU e NÃO para "
                    "todas as combinações possíveis de entrada."
                ),
                "ordem": 1,
                "dias_prazo": 14,
            },
            {
                "titulo": "Algoritmo de aprovação escolar",
                "enunciado": (
                    "Descreva um algoritmo que, dada a média de um aluno, "
                    "informe se ele está aprovado (média maior ou igual a 7), "
                    "em recuperação (entre 5 e 7) ou reprovado."
                ),
                "ordem": 2,
                "dias_prazo": 14,
            },
        ],
    },
    {
        "titulo": "Módulo 3 - Estruturas de repetição",
        "descricao": "Laços de repetição e critérios de parada. Em preparação.",
        "ordem": 3,
        "publicada": False,  # rascunho: não deve aparecer para o discente
        "atividades": [
            {
                "titulo": "Comparativo entre enquanto e para",
                "enunciado": "Quando usar cada tipo de laço? Justifique.",
                "ordem": 1,
                "dias_prazo": None,
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Popula o banco com dados fictícios da Funcionalidade 7 (trilhas e atividades)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove os dados de demonstração antes de recriá-los.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEBUG:
            raise CommandError(
                "Este comando só deve ser executado com DEBUG=True (desenvolvimento)."
            )

        if options["limpar"]:
            self._limpar()

        docente = self._criar_docentes()[0]
        discentes = self._criar_discentes()
        turma = self._criar_turma(docente)
        self._matricular(turma, discentes)
        trilhas = self._criar_trilhas(turma)
        self._registrar_progresso(trilhas, discentes)

        self._resumo(docente, discentes, turma)

    # ------------------------------------------------------------------ etapas
    def _limpar(self):
        self.stdout.write("Removendo dados de demonstração anteriores...")
        ConclusaoAtividade.objects.all().delete()
        Atividade.objects.all().delete()
        TrilhaAprendizagem.objects.all().delete()
        Matricula.objects.all().delete()
        Turma.objects.filter(nome="Algoritmos e Programação I").delete()
        logins = [d[0] for d in DOCENTES] + [d[0] for d in DISCENTES]
        Usuario.objects.filter(username__in=logins).delete()

    def _criar_docentes(self):
        criados = []
        for username, nome, sobrenome in DOCENTES:
            usuario, novo = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nome,
                    "last_name": sobrenome,
                    "perfil": "DOCENTE",
                    "is_staff": True,
                },
            )
            if novo:
                usuario.set_password(SENHA_PADRAO)
                usuario.save()
                self.stdout.write(f"  docente criado: {username}")
            else:
                self.stdout.write(f"  docente já existia: {username}")
            criados.append(usuario)
        return criados

    def _criar_discentes(self):
        criados = []
        for username, nome, sobrenome, rgm in DISCENTES:
            usuario, novo = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nome,
                    "last_name": sobrenome,
                    "perfil": "DISCENTE",
                    "rgm": rgm,
                },
            )
            if novo:
                usuario.set_password(SENHA_PADRAO)
                usuario.save()
                self.stdout.write(f"  discente criado: {username}")
            else:
                self.stdout.write(f"  discente já existia: {username}")
            criados.append(usuario)
        return criados

    def _criar_turma(self, docente):
        turma, novo = Turma.objects.get_or_create(
            nome="Algoritmos e Programação I",
            periodo="2026.2",
            defaults={"docente": docente, "ativa": True},
        )
        self.stdout.write(
            f"  turma {'criada' if novo else 'já existia'}: {turma.nome}"
        )
        return turma

    def _matricular(self, turma, discentes):
        # O último aluno fica SEM matrícula, para demonstrar que ele não
        # enxerga nenhuma trilha (critério de aceitação da ficha).
        for discente in discentes[:-1]:
            _, novo = Matricula.objects.get_or_create(
                turma=turma, discente=discente, defaults={"status": "ATIVA"}
            )
            if novo:
                self.stdout.write(f"  matriculado: {discente.username}")
        self.stdout.write(
            f"  {discentes[-1].username} deixado sem matrícula (caso de teste)"
        )

    def _criar_trilhas(self, turma):
        agora = timezone.now()
        trilhas = []
        for dados in TRILHAS:
            trilha, novo = TrilhaAprendizagem.objects.get_or_create(
                turma=turma,
                titulo=dados["titulo"],
                defaults={
                    "descricao": dados["descricao"],
                    "ordem": dados["ordem"],
                    "publicada": dados["publicada"],
                },
            )
            if novo:
                self.stdout.write(f"  trilha criada: {trilha.titulo}")

            for item in dados["atividades"]:
                prazo = (
                    agora + timedelta(days=item["dias_prazo"])
                    if item["dias_prazo"]
                    else None
                )
                Atividade.objects.get_or_create(
                    trilha=trilha,
                    titulo=item["titulo"],
                    defaults={
                        "enunciado": item["enunciado"],
                        "tipo": "TEORICA",
                        "ordem": item["ordem"],
                        "prazo": prazo,
                        "publicada": True,
                    },
                )
            trilhas.append(trilha)
        return trilhas

    def _registrar_progresso(self, trilhas, discentes):
        """Deixa o primeiro aluno com progresso parcial, para a barra não ficar zerada."""
        primeira_trilha = trilhas[0]
        aluno = discentes[0]
        atividades = list(primeira_trilha.atividades.order_by("ordem")[:2])
        for atividade in atividades:
            ConclusaoAtividade.objects.get_or_create(
                atividade=atividade, discente=aluno
            )
        self.stdout.write(
            f"  progresso: {aluno.username} concluiu {len(atividades)} atividades"
        )

    def _resumo(self, docente, discentes, turma):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
        self.stdout.write("")
        self.stdout.write(f"Senha de todos os usuários: {SENHA_PADRAO}")
        self.stdout.write("")
        self.stdout.write("  DOCENTE   -> " + docente.username + "   (veja /trilhas/)")
        self.stdout.write(
            "  DISCENTE  -> " + discentes[0].username + "   (veja /minhas-trilhas/, já tem progresso)"
        )
        self.stdout.write(
            "  DISCENTE  -> " + discentes[1].username + "   (matriculado, progresso zerado)"
        )
        self.stdout.write(
            "  SEM VÍNCULO -> " + discentes[-1].username + " (não deve ver trilha nenhuma)"
        )
        self.stdout.write("")
        self.stdout.write(
            f"Turma: {turma.nome} - {turma.periodo} | "
            f"{TrilhaAprendizagem.objects.filter(turma=turma).count()} trilhas | "
            f"{Atividade.objects.filter(trilha__turma=turma).count()} atividades"
        )
