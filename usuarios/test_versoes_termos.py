"""Versões dos termos publicadas pela coordenação, com reaceite e histórico preservado."""
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from auditoria.models import Acao, RegistroAuditoria

from .acesso import aceitou_versao_atual, url_primeiro_acesso
from .models import AceiteTermos, VersaoTermos
from .termos import formatar, numero_vigente
from .test_helpers import registrar_aceites_atuais

TEXTO = (
    "# Primeira\n\nParágrafo com **negrito** e *itálico*.\n\n## Sub\n\n- item a\n- item b\n\n"
    "> citação\n\n# Segunda\n\nFim.\n\n---\n\nRodapé."
)


class FormatoDoTextoTest(SimpleTestCase):
    def test_marcacoes_viram_os_blocos_da_pagina(self):
        doc = formatar(TEXTO)
        self.assertEqual(doc["indice"], [{"numero": 1, "titulo": "Primeira"}, {"numero": 2, "titulo": "Segunda"}])
        self.assertIn('<h2 id="clausula-2" class="simap-termos-clausula"><span>2</span> Segunda</h2>', doc["corpo"])
        self.assertIn("<strong>negrito</strong> e <em>itálico</em>", doc["corpo"])
        self.assertIn('<h3 class="simap-termos-subtitulo">Sub</h3>', doc["corpo"])
        self.assertIn('<ol type="a"><li>item a</li><li>item b</li></ol>', doc["corpo"])
        self.assertIn('<blockquote class="simap-termos-aceite">citação</blockquote>', doc["corpo"])
        self.assertEqual(doc["rodape"], "<p>Rodapé.</p>")

    def test_html_digitado_e_escapado(self):
        doc = formatar('# Título <img src=x onerror="alert(1)">\n\n<script>alert(1)</script> **<b>x</b>**')
        self.assertNotIn("<script>", doc["corpo"])
        self.assertNotIn("<img", doc["corpo"])
        self.assertIn("&lt;script&gt;", doc["corpo"])
        self.assertIn("<strong>&lt;b&gt;x&lt;/b&gt;</strong>", doc["corpo"])


class VersaoInicialTest(TestCase):
    def test_migracao_cadastra_a_versao_1_3_com_as_doze_clausulas(self):
        versao = VersaoTermos.objects.get()
        self.assertEqual(versao.numero, "1.3")
        self.assertEqual(numero_vigente(), "1.3")
        self.assertEqual(len(formatar(versao.texto)["indice"]), 12)
        self.assertEqual(versao.publicada_em.date().isoformat(), "2026-11-15")

    def test_pagina_publica_mostra_a_versao_do_banco(self):
        resposta = self.client.get(reverse("termos_de_uso"))
        self.assertContains(resposta, "Versão 1.3 · vigente desde 15/11/2026")
        self.assertContains(resposta, 'id="clausula-12"')

    def test_versao_publicada_nao_pode_ser_alterada_nem_apagada(self):
        versao = VersaoTermos.objects.get()
        versao.texto = "# Outro"
        with self.assertRaises(ValueError):
            versao.save()
        with self.assertRaises(ValueError):
            versao.delete()
        self.assertEqual(VersaoTermos.objects.get().numero, "1.3")


class PublicacaoPelaCoordenacaoTest(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.coord = Usuario.objects.create_superuser("coord", password="SenhaCoordenacao123!")
        self.prof = Usuario.objects.create_user("prof", perfil="DOCENTE")
        self.aluno = Usuario.objects.create_user("aluno", perfil="DISCENTE")
        registrar_aceites_atuais(Usuario.objects.all())
        self.client.force_login(self.coord)
        self.nova = reverse("nova_versao_termos")

    def dados(self, **extra):
        return {"numero": "1.4", "o_que_mudou": "Nova cláusula sobre instituições", "resumo": "Ponto",
                "texto": TEXTO, "acao": "publicar", "confirmar": "on", **extra}

    def test_somente_a_coordenacao_acessa(self):
        self.client.force_login(self.prof)
        for url in (reverse("versoes_termos"), self.nova):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(self.nova, self.dados()).status_code, 403)
        self.assertEqual(self.client.get(reverse("termos_de_uso_versao", args=["1.3"])).status_code, 404)
        self.assertFalse(VersaoTermos.objects.filter(numero="1.4").exists())

    def test_formulario_comeca_com_o_texto_vigente_e_o_proximo_numero(self):
        resposta = self.client.get(self.nova)
        self.assertEqual(resposta.context["form"].initial["numero"], "1.4")
        self.assertEqual(resposta.context["form"].initial["texto"], VersaoTermos.objects.get().texto)

    def test_previsualizar_nao_publica(self):
        resposta = self.client.post(self.nova, self.dados(acao="previsualizar", confirmar=""))
        self.assertContains(resposta, "Pré-visualização da versão 1.4")
        self.assertContains(resposta, "<strong>negrito</strong>", html=False)
        self.assertFalse(VersaoTermos.objects.filter(numero="1.4").exists())

    def test_publicar_exige_confirmacao(self):
        resposta = self.client.post(self.nova, self.dados(confirmar=""))
        self.assertContains(resposta, "Confirme antes de publicar a nova versão.")
        self.assertFalse(VersaoTermos.objects.filter(numero="1.4").exists())

    def test_numero_precisa_ser_valido_e_maior_que_o_vigente(self):
        for numero in ("1.3", "1.2", "abc", "1.4a", ""):
            with self.subTest(numero=numero):
                resposta = self.client.post(self.nova, self.dados(numero=numero))
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors.get("numero"))
        self.assertEqual(VersaoTermos.objects.count(), 1)

    def test_texto_precisa_de_ao_menos_uma_clausula(self):
        resposta = self.client.post(self.nova, self.dados(texto="Só um parágrafo."))
        self.assertTrue(resposta.context["form"].errors.get("texto"))

    def test_publicacao_exige_novo_aceite_e_mostra_o_que_mudou(self):
        resposta = self.client.post(self.nova, self.dados())
        self.assertRedirects(resposta, reverse("versoes_termos"), fetch_redirect_response=False)
        # Quem publicou também precisa aceitar a nova versão para continuar.
        self.assertRedirects(
            self.client.get(reverse("versoes_termos")), url_primeiro_acesso(reverse("versoes_termos")),
            fetch_redirect_response=False,
        )
        versao = VersaoTermos.objects.get(numero="1.4")
        self.assertEqual(versao.publicada_por, self.coord)
        self.assertEqual(numero_vigente(), "1.4")
        self.assertFalse(aceitou_versao_atual(self.aluno))

        self.client.force_login(self.aluno)
        destino = reverse("core:dashboard")
        self.assertRedirects(self.client.get(destino), url_primeiro_acesso(destino), fetch_redirect_response=False)
        pagina = self.client.get(reverse("primeiro_acesso"))
        self.assertContains(pagina, "Versão 1.4")
        self.assertContains(pagina, "Nova cláusula sobre instituições")
        self.client.post(reverse("primeiro_acesso"), {"aceite_termos": "on", "versao": "1.4"})
        self.assertTrue(aceitou_versao_atual(self.aluno))
        self.assertEqual(AceiteTermos.objects.filter(usuario=self.aluno).count(), 2)

    def test_historico_mostra_aceites_e_permite_ler_versao_anterior(self):
        self.client.post(self.nova, self.dados())
        AceiteTermos.objects.create(usuario=self.coord, versao="1.4")
        lista = self.client.get(reverse("versoes_termos"))
        self.assertEqual([v.numero for v in lista.context["versoes"]], ["1.4", "1.3"])
        self.assertEqual([v.total_aceites for v in lista.context["versoes"]], [1, 3])
        AceiteTermos.objects.create(usuario=self.prof, versao="1.4")
        lista = self.client.get(reverse("versoes_termos"))
        self.assertContains(lista, "2 de 3 contas ativas")
        antiga = self.client.get(reverse("termos_de_uso_versao", args=["1.3"]))
        self.assertContains(antiga, "Versão 1.3 · publicada em 15/11/2026")
        self.assertContains(antiga, "A versão vigente é a 1.4")

    def test_html_no_texto_publicado_nao_chega_a_pagina(self):
        self.client.post(self.nova, self.dados(texto="# Cláusula\n\n<script>alert(1)</script>", resumo="<b>x</b>"))
        pagina = self.client.get(reverse("termos_de_uso"))
        self.assertNotContains(pagina, "<script>alert(1)</script>", html=False)
        self.assertContains(pagina, "&lt;script&gt;alert(1)&lt;/script&gt;", html=False)
        self.assertNotContains(pagina, "<b>x</b>", html=False)

    def test_publicacao_fica_na_auditoria_sem_copiar_o_texto(self):
        self.client.post(self.nova, self.dados())
        registro = RegistroAuditoria.objects.get(acao=Acao.CRIACAO, entidade="usuarios.VersaoTermos")
        self.assertEqual(registro.usuario, self.coord)
        self.assertEqual(registro.dados["numero"], "1.4")
        self.assertEqual(registro.dados["texto"], "[conteúdo não registrado]")


class BloqueioImediatoTest(TestCase):
    """As páginas abertas descobrem a nova versão sem esperar o próximo clique."""

    def setUp(self):
        self.aluno = get_user_model().objects.create_user("aluno", perfil="DISCENTE")
        registrar_aceites_atuais([self.aluno])

    def test_consulta_da_versao_vigente_e_publica_e_nao_toca_na_sessao(self):
        resposta = Client().get(reverse("termos_vigente"))
        self.assertEqual(resposta.json(), {"versao": "1.3"})
        self.assertIn("no-cache", resposta["Cache-Control"])
        self.assertNotIn("sessionid", resposta.cookies)
        VersaoTermos.objects.create(numero="1.4", texto="# Cláusula")
        self.assertEqual(Client().get(reverse("termos_vigente")).json(), {"versao": "1.4"})

    def test_consulta_nao_entra_na_auditoria(self):
        Client().get(reverse("termos_vigente"))
        self.assertFalse(RegistroAuditoria.objects.filter(caminho=reverse("termos_vigente")).exists())

    def test_pagina_logada_informa_a_versao_aceita_e_carrega_o_bloqueio(self):
        self.client.force_login(self.aluno)
        pagina = self.client.get(reverse("comunicacao:notificacoes"))
        self.assertContains(pagina, 'data-termos-versao="1.3"')
        self.assertContains(pagina, f'data-termos-vigente="{reverse("termos_vigente")}"')
        self.assertContains(pagina, "js/termos_vigentes.js")

    def test_pagina_sem_login_nao_carrega_o_bloqueio(self):
        pagina = Client().get(reverse("login"))
        self.assertNotContains(pagina, "termos_vigentes.js")
