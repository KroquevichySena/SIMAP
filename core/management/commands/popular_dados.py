"""
Enche o banco com dados de exemplo para demonstrar as trilhas de aprendizagem.

Como usar:
    python manage.py popular_dados
    python manage.py popular_dados --limpar    (apaga os dados de exemplo antes)

É só para desenvolvimento e apresentação. Em produção o comando se recusa a
rodar, para ninguém encher o sistema real de dados fictícios.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Atividade, ConclusaoAtividade, TrilhaAprendizagem
from turmas.models import Matricula, Turma

Usuario = get_user_model()

SENHA_PADRAO = "DemonstracaoLocal2026!"
GRUPO_DEMO = "SIMAP - demonstracao ficticia"
TURMA_DEMO = "DEMO - Algoritmos e Programação I"
PERIODO_DEMO = "2026.2"
COORDENACAO = ("demo.coordenacao", "Coordenação", "Demonstração")

DOCENTES = [
    ("demo.docente", "Docente", "Demonstração"),
]

DISCENTES = [
    ("demo.aluno01", "Aluno", "Demonstração 01", "DEMO-0001"),
    ("demo.aluno02", "Aluno", "Demonstração 02", "DEMO-0002"),
    ("demo.aluno03", "Aluno", "Demonstração 03", "DEMO-0003"),
    ("demo.aluno04", "Aluno", "Demonstração 04", "DEMO-0004"),
]

TRILHAS = [
    {
        "titulo": "Módulo 1 - Variáveis e tipos de dados",
        "descricao": ("Primeiros conceitos de programação: como armazenar e representar informação na memória."),
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
                    "Leia o capítulo 1 do material da disciplina e liste três dúvidas que surgiram durante a leitura."
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
                    "Monte a tabela verdade dos operadores E, OU e NÃO para todas as combinações possíveis de entrada."
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
    help = "Cria cenário fictício com três perfis, turma, matrículas e trilhas (somente desenvolvimento)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Recria somente a turma fictícia e seu conteúdo. Preserva contas e senhas existentes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEBUG:
            raise CommandError("Este comando só deve ser executado com DEBUG=True (desenvolvimento).")

        if options["limpar"]:
            self._limpar()

        self.grupo, _ = Group.objects.get_or_create(name=GRUPO_DEMO)
        self._criar_coordenacao()
        docente = self._criar_docentes()[0]
        discentes = self._criar_discentes()
        turma = self._criar_turma(docente)
        self._matricular(turma, discentes)
        trilhas = self._criar_trilhas(turma)
        self._registrar_progresso(trilhas, discentes)

        self._resumo(docente, discentes, turma)

    # Cada etapa abaixo monta uma parte do cenário de demonstração.
    def _limpar(self):
        self.stdout.write("Recriando somente a turma fictícia; contas e outros dados serão preservados.")
        turmas = Turma.objects.filter(
            nome=TURMA_DEMO,
            periodo=PERIODO_DEMO,
            docente__username__in=[d[0] for d in DOCENTES],
            docente__groups__name=GRUPO_DEMO,
        )
        # Se outras pessoas passaram a utilizar essa turma, não apague seus dados.
        logins = [COORDENACAO[0]] + [d[0] for d in DOCENTES] + [d[0] for d in DISCENTES]
        from chamada.models import Registro_de_Presenca
        from comunicacao.models import Publicacao, Resposta
        from entregas.models import Submissao

        externos = (
            Matricula.objects.filter(turma__in=turmas).exclude(discente__username__in=logins).exists()
            or ConclusaoAtividade.objects.filter(atividade__trilha__turma__in=turmas)
            .exclude(discente__username__in=logins)
            .exists()
            or Submissao.objects.filter(atividade__trilha__turma__in=turmas)
            .exclude(aluno__username__in=logins)
            .exists()
            or Registro_de_Presenca.objects.filter(chamada__turma__in=turmas)
            .exclude(discente__username__in=logins)
            .exists()
            or Publicacao.objects.filter(turma__in=turmas).exclude(autor__username__in=logins).exists()
            or Resposta.objects.filter(publicacao__turma__in=turmas).exclude(autor__username__in=logins).exists()
        )
        if externos:
            raise CommandError("A turma de demonstração contém dados de outras contas. A limpeza foi cancelada.")
        turmas.delete()

    def _conta_demo(self, username, **dados):
        usuario = Usuario.objects.filter(username=username).first()
        if usuario is not None:
            if (
                not usuario.groups.filter(pk=self.grupo.pk).exists()
                or usuario.perfil != dados["perfil"]
                or usuario.is_staff != dados.get("is_staff", False)
                or usuario.is_superuser != dados.get("is_superuser", False)
            ):
                raise CommandError(f"A conta {username} não corresponde ao cenário fictício. Nenhum dado foi alterado.")
            return usuario, False
        usuario = Usuario.objects.create_user(
            username=username,
            password=SENHA_PADRAO,
            email=f"{username}@example.test",
            troca_senha_obrigatoria=True,
            **dados,
        )
        usuario.groups.add(self.grupo)
        return usuario, True

    def _criar_coordenacao(self):
        username, nome, sobrenome = COORDENACAO
        self._conta_demo(
            username,
            first_name=nome,
            last_name=sobrenome,
            perfil="COORDENACAO",
            is_staff=True,
            is_superuser=True,
        )

    def _criar_docentes(self):
        criados = []
        for username, nome, sobrenome in DOCENTES:
            usuario, novo = self._conta_demo(
                username,
                first_name=nome,
                last_name=sobrenome,
                perfil="DOCENTE",
                is_staff=False,
            )
            if novo:
                self.stdout.write(f"  docente criado: {username}")
            else:
                self.stdout.write(f"  docente já existia: {username}")
            criados.append(usuario)
        return criados

    def _criar_discentes(self):
        criados = []
        for username, nome, sobrenome, rgm in DISCENTES:
            usuario, novo = self._conta_demo(
                username,
                first_name=nome,
                last_name=sobrenome,
                perfil="DISCENTE",
                rgm=rgm,
            )
            if novo:
                self.stdout.write(f"  discente criado: {username}")
            else:
                self.stdout.write(f"  discente já existia: {username}")
            criados.append(usuario)
        return criados

    def _criar_turma(self, docente):
        turma, novo = Turma.objects.get_or_create(
            nome=TURMA_DEMO,
            periodo=PERIODO_DEMO,
            docente=docente,
            defaults={"ativa": True},
        )
        self.stdout.write(f"  turma {'criada' if novo else 'já existia'}: {turma.nome}")
        return turma

    def _matricular(self, turma, discentes):
        # O último aluno fica sem matrícula de propósito: assim dá para mostrar
        # que ele não enxerga trilha nenhuma, como pede a ficha.
        for discente in discentes[:-1]:
            _, novo = Matricula.objects.get_or_create(turma=turma, discente=discente, defaults={"status": "ATIVA"})
            if novo:
                self.stdout.write(f"  matriculado: {discente.username}")
        self.stdout.write(f"  {discentes[-1].username} deixado sem matrícula (caso de teste)")

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
                prazo = agora + timedelta(days=item["dias_prazo"]) if item["dias_prazo"] else None
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
        """O primeiro aluno já começa com parte das atividades feitas, para a barra de progresso não aparecer zerada."""
        primeira_trilha = trilhas[0]
        aluno = discentes[0]
        atividades = list(primeira_trilha.atividades.order_by("ordem")[:2])
        for atividade in atividades:
            ConclusaoAtividade.objects.get_or_create(atividade=atividade, discente=aluno)
        self.stdout.write(f"  progresso: {aluno.username} concluiu {len(atividades)} atividades")

    def _resumo(self, docente, discentes, turma):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
        self.stdout.write("")
        self.stdout.write("Cenário fictício. Senhas não são exibidas no resumo nem devem aparecer nas evidências.")
        self.stdout.write("A senha temporária local está definida no comando; contas existentes mantêm sua senha.")
        self.stdout.write("")
        self.stdout.write("  COORDENAÇÃO -> " + COORDENACAO[0] + " (veja /contas/usuarios/)")
        self.stdout.write("  DOCENTE   -> " + docente.username + "   (veja /docente/trilhas/)")
        self.stdout.write("  DISCENTE  -> " + discentes[0].username + "   (veja /minhas-trilhas/, já tem progresso)")
        self.stdout.write("  DISCENTE  -> " + discentes[1].username + "   (matriculado, progresso zerado)")
        self.stdout.write("  SEM VÍNCULO -> " + discentes[-1].username + " (não deve ver trilha nenhuma)")
        self.stdout.write("")
        self.stdout.write(
            f"Turma: {turma.nome} - {turma.periodo} | "
            f"{TrilhaAprendizagem.objects.filter(turma=turma).count()} trilhas | "
            f"{Atividade.objects.filter(trilha__turma=turma).count()} atividades"
        )
