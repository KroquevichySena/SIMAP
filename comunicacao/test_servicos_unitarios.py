"""Quem é notificado em cada publicação e resposta, sem banco."""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from . import servicos
from .models import Notificacao

Usuario = get_user_model()


def _pessoa(pk, nome=""):
    primeiro, _, ultimo = nome.partition(" ")
    return Usuario(pk=pk, username=f"user{pk}", first_name=primeiro, last_name=ultimo)


class _Base(SimpleTestCase):
    def setUp(self):
        self.docente = _pessoa(1, "Ana Prof")
        self.aluno = _pessoa(2, "Bia Aluna")
        self.colega = _pessoa(3)
        self.turma = SimpleNamespace(nome="Algoritmos", docente_id=1, docente=self.docente)
        patches = [
            mock.patch.object(servicos.Notificacao.objects, "bulk_create"),
            mock.patch.object(servicos, "salvar_arquivos"),
            mock.patch.object(servicos.permissoes, "alunos_da_turma", return_value=[self.aluno, self.colega]),
        ]
        self.bulk_create, self.salvar, _ = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

    def notificados(self):
        return [n.destinatario.pk for n in self.bulk_create.call_args.args[0]]

    def tipo(self):
        return {n.tipo for n in self.bulk_create.call_args.args[0]}


@mock.patch.object(servicos.Publicacao.objects, "create")
class PublicarTest(_Base):
    def _publicar(self, create, autor, **extra):
        create.return_value = mock.MagicMock(get_absolute_url=lambda: "/comunicacao/p/1/")
        # publicar() roda dentro de transaction.atomic; aqui chamamos a função sem a transação.
        return servicos.publicar.__wrapped__(autor, self.turma, "Olá", **extra)

    def test_post_do_professor_no_mural_avisa_os_alunos(self, create):
        self._publicar(create, self.docente)

        self.assertEqual(self.notificados(), [2, 3])
        self.assertEqual(self.tipo(), {Notificacao.Tipo.PUBLICACAO})

    def test_post_do_aluno_no_mural_avisa_so_o_professor(self, create):
        self._publicar(create, self.aluno)

        self.assertEqual(self.notificados(), [1])

    def test_comentario_em_atividade(self, create):
        atividade = SimpleNamespace(titulo="Lista 1")

        self._publicar(create, self.docente, atividade=atividade)

        self.assertEqual(self.tipo(), {Notificacao.Tipo.COMENTARIO})
        self.assertIn("Lista 1", self.bulk_create.call_args.args[0][0].mensagem)

    def test_mensagem_privada_avisa_so_o_destinatario(self, create):
        self._publicar(create, self.docente, destinatario=self.aluno)

        self.assertEqual(self.notificados(), [2])
        self.assertEqual(self.tipo(), {Notificacao.Tipo.PRIVADA})

    def test_anexos_sao_salvos_na_publicacao(self, create):
        self._publicar(create, self.docente, anexos=["arquivo"])

        self.assertEqual(self.salvar.call_args.args[1], ["arquivo"])


class NotificarTest(_Base):
    def test_ninguem_recebe_aviso_duplicado_nem_do_proprio_post(self):
        total = servicos._notificar(
            [self.aluno, self.aluno, self.docente], Notificacao.Tipo.RESPOSTA, "m" * 300, "/", exceto=self.docente
        )

        self.assertEqual(total, 1)
        self.assertEqual(len(self.bulk_create.call_args.args[0][0].mensagem), 255)

    def test_nome_usa_o_login_quando_nao_ha_nome(self):
        self.assertEqual(servicos._nome(self.colega), "user3")
        self.assertEqual(servicos._nome(self.docente), "Ana Prof")

    def test_aviso_para_todos_os_alunos_da_turma(self):
        total = servicos.notificar_alunos(self.turma, Notificacao.Tipo.TRILHA, "Nova trilha", "/")

        self.assertEqual(total, 2)


@mock.patch.object(servicos.Resposta.objects, "create")
class ResponderTest(_Base):
    def _responder(self, create, autor, publicacao, pode_ver=True):
        create.return_value = mock.MagicMock(pk=50, get_absolute_url=lambda: "/comunicacao/r/50/")
        with mock.patch.object(servicos.permissoes, "pode_ver_publicacao", return_value=pode_ver):
            servicos.responder.__wrapped__(autor, publicacao, "Resposta")

    def _publicacao(self, autor, privada=False, destinatario=None, quem_respondeu=()):
        publicacao = mock.MagicMock(autor=autor, privada=privada, destinatario=destinatario, texto="Dúvida")
        publicacao.turma = self.turma
        publicacao.respostas.select_related.return_value.exclude.return_value = [
            SimpleNamespace(autor=p) for p in quem_respondeu
        ]
        return publicacao

    def test_resposta_publica_avisa_autor_participantes_e_professor(self, create):
        publicacao = self._publicacao(self.aluno, quem_respondeu=[self.colega])

        self._responder(create, self.colega, publicacao)

        self.assertEqual(sorted(self.notificados()), [1, 2])

    def test_resposta_em_mensagem_privada_avisa_o_destinatario(self, create):
        publicacao = self._publicacao(self.docente, privada=True, destinatario=self.aluno)

        self._responder(create, self.docente, publicacao)

        self.assertEqual(self.notificados(), [2])

    def test_quem_nao_pode_mais_ver_nao_e_avisado(self, create):
        self._responder(create, self.colega, self._publicacao(self.aluno), pode_ver=False)

        self.assertEqual(self.notificados(), [])
