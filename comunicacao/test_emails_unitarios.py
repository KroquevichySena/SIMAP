"""Envio dos e-mails acadêmicos (RF33), sem banco e sem enviar e-mail de verdade."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import emails_academicos as emails
from .models import EmailAcademico

Tipo = EmailAcademico.Tipo
Status = EmailAcademico.Status


def _avaliacao(nota=8.5, feedback="Bom trabalho."):
    return SimpleNamespace(nota=nota, feedback_professor=feedback)


def _aviso_de_feedback(**ajustes):
    turma = SimpleNamespace(ativa=True)
    trilha = SimpleNamespace(publicada=True, turma=turma)
    atividade = SimpleNamespace(pk=4, publicada=True, trilha=trilha)
    avaliacao = _avaliacao()
    avaliacao.submissao = SimpleNamespace(aluno_id=2, atividade=atividade)
    aluno = SimpleNamespace(is_active=True, is_discente=True, email="bia@example.test")
    aviso = SimpleNamespace(
        tipo=Tipo.FEEDBACK, destinatario=aluno, destinatario_id=2,
        avaliacao=avaliacao, assinatura=emails.assinatura_feedback(avaliacao),
    )
    for caminho, valor in ajustes.items():
        alvo, campo = {"atividade": (atividade, "publicada"), "turma": (turma, "ativa"),
                       "aluno": (aluno, "is_active")}[caminho]
        setattr(alvo, campo, valor)
    return aviso


def _aviso_de_atencao(em_atencao=True, episodio=1):
    docente = SimpleNamespace(is_active=True, is_docente=True, email="ana@example.test")
    discente = SimpleNamespace(is_active=True, is_discente=True)
    turma = SimpleNamespace(pk=1, ativa=True, docente_id=1)
    matricula = SimpleNamespace(turma=turma, discente=discente, discente_id=2)
    estado = SimpleNamespace(em_atencao=em_atencao, episodio=1)
    aviso = SimpleNamespace(tipo=Tipo.ATENCAO, destinatario=docente, destinatario_id=1,
                            matricula=matricula, episodio=episodio)
    return aviso, estado


class AssinaturaTest(SimpleTestCase):
    def test_mesma_nota_e_feedback_geram_a_mesma_assinatura(self):
        self.assertEqual(emails.assinatura_feedback(_avaliacao(8.5)), emails.assinatura_feedback(_avaliacao("8.50")))

    def test_mudar_o_feedback_muda_a_assinatura(self):
        original = emails.assinatura_feedback(_avaliacao())

        self.assertNotEqual(original, emails.assinatura_feedback(_avaliacao(feedback="x")))

    @override_settings(SIMAP_PUBLIC_URL="https://simap.onrender.com/")
    def test_link_usa_o_endereco_publico(self):
        self.assertEqual(emails._acesso("/painel/", "Entre"), "Entre\nhttps://simap.onrender.com/painel/")

    @override_settings(SIMAP_PUBLIC_URL="")
    def test_sem_endereco_publico_vai_so_a_instrucao(self):
        self.assertEqual(emails._acesso("/painel/", "Entre"), "Entre")


@mock.patch.object(emails.Matricula.objects, "filter")
class MensagemDeFeedbackTest(SimpleTestCase):
    def test_aviso_valido_nao_leva_nota_nem_feedback(self, matriculas):
        matriculas.return_value.exists.return_value = True

        assunto, corpo = emails._mensagem(_aviso_de_feedback())

        self.assertEqual(assunto, "SIMAP: feedback disponível")
        self.assertNotIn("8.5", corpo)
        self.assertNotIn("Bom trabalho", corpo)

    def test_casos_em_que_o_aviso_e_cancelado(self, matriculas):
        matriculas.return_value.exists.return_value = True
        avisos = {
            "aluno desativado": _aviso_de_feedback(aluno=False),
            "atividade despublicada": _aviso_de_feedback(atividade=False),
            "turma inativa": _aviso_de_feedback(turma=False),
        }
        nota_mudou = _aviso_de_feedback()
        nota_mudou.assinatura = "versao-antiga"
        avisos["avaliação revisada depois"] = nota_mudou
        for motivo, aviso in avisos.items():
            with self.subTest(motivo=motivo):
                self.assertIsNone(emails._mensagem(aviso))

    def test_aluno_que_saiu_da_turma_nao_recebe(self, matriculas):
        matriculas.return_value.exists.return_value = False

        self.assertIsNone(emails._mensagem(_aviso_de_feedback()))


@mock.patch.object(emails, "indicadores_do_aluno", return_value={"em_atencao": True})
@mock.patch.object(emails.EstadoAlertaAtencao.objects, "filter")
class MensagemDeAtencaoTest(SimpleTestCase):
    def test_aviso_valido_vai_para_o_docente(self, estados, _indicadores):
        aviso, estado = _aviso_de_atencao()
        estados.return_value.first.return_value = estado

        assunto, corpo = emails._mensagem(aviso)

        self.assertEqual(assunto, "SIMAP: aluno em situação de atenção")
        self.assertIn("não representa um diagnóstico", corpo)

    def test_aluno_que_saiu_da_atencao_cancela_o_aviso(self, estados, indicadores):
        aviso, estado = _aviso_de_atencao()
        estados.return_value.first.return_value = estado
        indicadores.return_value = {"em_atencao": False}

        self.assertIsNone(emails._mensagem(aviso))

    def test_aviso_de_episodio_antigo_e_cancelado(self, estados, _indicadores):
        aviso, estado = _aviso_de_atencao(episodio=0)
        estados.return_value.first.return_value = estado

        self.assertIsNone(emails._mensagem(aviso))


@mock.patch.object(emails, "send_mail", return_value=1)
@mock.patch.object(emails, "_mensagem", return_value=("Assunto", "Corpo"))
@mock.patch.object(emails.EmailAcademico.objects, "select_related")
@mock.patch.object(emails.EmailAcademico.objects, "filter")
class EnviarAvisoTest(SimpleTestCase):
    def _preparar(self, filtro, select_related, aviso=None, reservado=1):
        filtro.return_value.update.return_value = reservado
        aviso = aviso or SimpleNamespace(tipo=Tipo.ATENCAO, destinatario=SimpleNamespace(email="ana@example.test"))
        select_related.return_value.get.return_value = aviso
        return filtro.return_value

    def _status_final(self, registro):
        return registro.update.call_args.kwargs["status"]

    def test_envia_e_marca_como_enviado(self, filtro, select_related, _mensagem, send_mail):
        registro = self._preparar(filtro, select_related)

        self.assertEqual(emails.enviar_aviso(1), "enviado")
        self.assertEqual(self._status_final(registro), Status.ENVIADO)
        self.assertEqual(send_mail.call_args.args[3], ["ana@example.test"])

    def test_aviso_ja_reservado_por_outro_envio_e_ignorado(self, filtro, select_related, _mensagem, send_mail):
        self._preparar(filtro, select_related, reservado=0)

        self.assertEqual(emails.enviar_aviso(1), "ignorado")
        send_mail.assert_not_called()

    def test_mensagem_que_nao_se_aplica_mais_e_cancelada(self, filtro, select_related, mensagem, send_mail):
        registro = self._preparar(filtro, select_related)
        mensagem.return_value = None

        self.assertEqual(emails.enviar_aviso(1), "cancelado")
        self.assertEqual(self._status_final(registro), Status.CANCELADO)

    def test_destinatario_sem_email_continua_pendente(self, filtro, select_related, _mensagem, send_mail):
        aviso = SimpleNamespace(tipo=Tipo.ATENCAO, destinatario=SimpleNamespace(email=""))
        registro = self._preparar(filtro, select_related, aviso)

        self.assertEqual(emails.enviar_aviso(1), "sem_email")
        self.assertEqual(self._status_final(registro), Status.PENDENTE)

    def test_feedback_de_atividade_em_rascunho_espera_a_publicacao(self, filtro, select_related, _m, send_mail):
        atividade = SimpleNamespace(publicada=False, trilha=SimpleNamespace(publicada=True))
        aviso = SimpleNamespace(tipo=Tipo.FEEDBACK,
                                avaliacao=SimpleNamespace(submissao=SimpleNamespace(atividade=atividade)))
        self._preparar(filtro, select_related, aviso)

        self.assertEqual(emails.enviar_aviso(1), "aguardando_publicacao")
        send_mail.assert_not_called()

    def test_falha_no_envio_volta_para_pendente(self, filtro, select_related, _mensagem, send_mail):
        registro = self._preparar(filtro, select_related)
        send_mail.side_effect = ConnectionError("Mailgun fora do ar")

        with self.assertLogs("simap.integracoes", level="ERROR"):
            self.assertEqual(emails.enviar_aviso(1), "falha")
        self.assertEqual(self._status_final(registro), Status.PENDENTE)

    def test_backend_que_nao_confirma_o_envio_e_falha(self, filtro, select_related, _mensagem, send_mail):
        self._preparar(filtro, select_related)
        send_mail.return_value = 0

        with self.assertLogs("simap.integracoes", level="ERROR"):
            self.assertEqual(emails.enviar_aviso(1), "falha")


class ProcessarPendentesTest(SimpleTestCase):
    def test_conta_o_resultado_de_cada_aviso(self):
        fila = mock.MagicMock()
        fila.order_by.return_value.values_list.return_value.__getitem__.return_value = [1, 2, 3]
        with mock.patch.object(emails.EmailAcademico.objects, "filter", return_value=fila), \
                mock.patch.object(emails, "enviar_aviso", side_effect=["enviado", "falha", "enviado"]):
            self.assertEqual(emails.processar_pendentes(), {"enviado": 2, "falha": 1})
