"""Testes do editor de código das atividades práticas."""
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from core.models import Atividade, CasoDeTeste, TIPO_PRATICA, TrilhaAprendizagem
from core.test_materiais import TrilhasBase

from .models import RascunhoCodigo, Submissao


class EditorBase(TrilhasBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pratica = Atividade.objects.create(
            trilha=cls.trilha, titulo="Tabuada", enunciado="Mostre a tabuada.", ordem=1,
            tipo=TIPO_PRATICA, codigo_inicial="numero = int(input())\n",
        )
        CasoDeTeste.objects.create(atividade=cls.pratica, entrada="7", saida_esperada="7 x 1 = 7", ordem=0)
        cls.teorica = Atividade.objects.create(trilha=cls.trilha, titulo="Conceitos", enunciado="x", ordem=2)

    def url(self, nome, atividade=None):
        return reverse(f"entregas:{nome}", args=[(atividade or self.pratica).pk])


class TelaDoEditorTest(EditorBase):

    def test_aluno_abre_o_editor_com_o_codigo_inicial_e_os_casos(self):
        self.entrar(self.aluno)
        resposta = self.client.get(self.url("resolver"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "data-editor-codigo")
        self.assertContains(resposta, "numero = int(input())")
        self.assertContains(resposta, '<script id="casos-aluno" type="application/json">')
        self.assertContains(resposta, "7 x 1 = 7")
        self.assertContains(resposta, 'data-url-rascunho="%s"' % self.url("salvar_rascunho"))
        # A página só carrega o CodeMirror com a checagem de integridade.
        self.assertContains(resposta, 'integrity="sha384-')

    def test_minhas_trilhas_mostra_o_botao_do_editor_so_na_pratica(self):
        self.entrar(self.aluno)
        resposta = self.client.get(reverse("core:minhas_trilhas"))
        self.assertContains(resposta, self.url("resolver"))
        self.assertNotContains(resposta, self.url("resolver", self.teorica))

    def test_quem_nao_pode_ver_a_atividade_recebe_404(self):
        for pessoa in (self.intruso, self.inativo):
            with self.subTest(pessoa=pessoa.username):
                self.entrar(pessoa)
                self.assertEqual(self.client.get(self.url("resolver")).status_code, 404)
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(self.url("resolver", self.teorica)).status_code, 404)
        TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).update(publicada=False)
        self.assertEqual(self.client.get(self.url("resolver")).status_code, 404)

    def test_professor_nao_usa_a_tela_do_aluno(self):
        self.entrar(self.prof)
        self.assertIn(self.client.get(self.url("resolver")).status_code, (302, 403))

    def test_codigo_com_tag_de_script_nao_quebra_a_pagina(self):
        RascunhoCodigo.objects.create(atividade=self.pratica, aluno=self.aluno, codigo='print("</textarea><script>alert(1)</script>")')
        CasoDeTeste.objects.create(atividade=self.pratica, entrada="", saida_esperada="</script><script>alert(2)</script>", ordem=1)
        self.entrar(self.aluno)
        resposta = self.client.get(self.url("resolver"))
        self.assertNotContains(resposta, "<script>alert(1)</script>")
        self.assertNotContains(resposta, "<script>alert(2)</script>")
        self.assertContains(resposta, "&lt;/textarea&gt;&lt;script&gt;alert(1)")

    @override_settings(SIMAP_PYODIDE_URL="https://minha-copia.exemplo.com/pyodide")
    def test_endereco_do_pyodide_e_configuravel(self):
        self.entrar(self.aluno)
        self.assertContains(self.client.get(self.url("resolver")), 'data-pyodide-url="https://minha-copia.exemplo.com/pyodide/"')


class RascunhoTest(EditorBase):

    def test_rascunho_e_salvo_e_volta_ao_abrir(self):
        self.entrar(self.aluno)
        resposta = self.client.post(self.url("salvar_rascunho"), {"codigo": "print('meu rascunho')"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("salvo_em", resposta.json())
        self.client.post(self.url("salvar_rascunho"), {"codigo": "print('versão 2')"})
        self.assertEqual(RascunhoCodigo.objects.get().codigo, "print('versão 2')")
        self.assertContains(self.client.get(self.url("resolver")), "print(&#x27;versão 2&#x27;)")

    def test_rascunho_grande_demais_e_recusado(self):
        self.entrar(self.aluno)
        with self.settings(EDITOR_TAMANHO_MAXIMO_CODIGO=10):
            resposta = self.client.post(self.url("salvar_rascunho"), {"codigo": "x" * 11})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(RascunhoCodigo.objects.exists())

    def test_rascunho_exige_csrf(self):
        from django.test import Client

        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno)
        self.assertEqual(cliente.post(self.url("salvar_rascunho"), {"codigo": "x"}).status_code, 403)

    def test_intruso_nao_salva_rascunho(self):
        self.entrar(self.intruso)
        self.assertEqual(self.client.post(self.url("salvar_rascunho"), {"codigo": "x"}).status_code, 404)

    @mock.patch("entregas.views.gerar_analise")
    def test_entrega_pelo_editor_apaga_o_rascunho_e_trava_a_edicao(self, _analise):
        self.entrar(self.aluno)
        self.client.post(self.url("salvar_rascunho"), {"codigo": "rascunho"})
        self.client.post(self.url("submeter"), {"resposta_texto": "print(7)"})
        self.assertEqual(Submissao.objects.get().resposta_texto, "print(7)")
        self.assertFalse(RascunhoCodigo.objects.exists())

        resposta = self.client.get(self.url("resolver"))
        self.assertContains(resposta, "print(7)")
        self.assertContains(resposta, 'data-somente-leitura="1"')
        self.assertNotContains(resposta, "data-url-rascunho")
        self.assertEqual(self.client.post(self.url("salvar_rascunho"), {"codigo": "y"}).status_code, 409)


class CasosNoFormularioTest(EditorBase):

    def dados(self, **extra):
        dados = self.dados_atividade(titulo="Soma", tipo=TIPO_PRATICA, codigo_inicial="def soma(a, b):\n    pass\n")
        dados.update({"casos-TOTAL_FORMS": "2", "casos-INITIAL_FORMS": "0", "casos-MIN_NUM_FORMS": "0", "casos-MAX_NUM_FORMS": "10",
                      "casos-0-entrada": "1\n2", "casos-0-saida_esperada": "3",
                      "casos-1-entrada": "", "casos-1-saida_esperada": ""})
        dados.update(extra)
        return dados

    def test_professor_cadastra_codigo_inicial_e_casos(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:atividade_create"), self.dados())
        self.assertRedirects(resposta, reverse("core:atividade_list"))
        atividade = Atividade.objects.get(titulo="Soma")
        self.assertEqual(atividade.codigo_inicial, "def soma(a, b):\n    pass\n")
        self.assertEqual(list(atividade.casos_de_teste.values_list("entrada", "saida_esperada")), [("1\n2", "3")])

    def test_caso_sem_saida_esperada_impede_salvar(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:atividade_create"), self.dados(**{"casos-1-entrada": "5"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Atividade.objects.filter(titulo="Soma").exists())

    def test_professor_remove_um_caso_na_edicao(self):
        caso = self.pratica.casos_de_teste.get()
        self.entrar(self.prof)
        dados = self.dados_atividade(titulo="Tabuada", tipo=TIPO_PRATICA)
        dados.update({"casos-TOTAL_FORMS": "1", "casos-INITIAL_FORMS": "1", "casos-MIN_NUM_FORMS": "0", "casos-MAX_NUM_FORMS": "10",
                      "casos-0-id": str(caso.pk), "casos-0-entrada": caso.entrada,
                      "casos-0-saida_esperada": caso.saida_esperada, "casos-0-DELETE": "on"})
        resposta = self.client.post(reverse("core:atividade_update", args=[self.pratica.pk]), dados)
        self.assertRedirects(resposta, reverse("core:atividade_list"))
        self.assertFalse(self.pratica.casos_de_teste.exists())

    def test_formulario_sem_casos_nao_apaga_os_existentes(self):
        self.entrar(self.prof)
        self.client.post(reverse("core:atividade_update", args=[self.pratica.pk]),
                         self.dados_atividade(titulo="Tabuada", tipo=TIPO_PRATICA))
        self.assertEqual(self.pratica.casos_de_teste.count(), 1)


@mock.patch("entregas.views.gerar_analise")
class CorrecaoComEditorTest(EditorBase):

    def test_professor_ve_o_codigo_no_editor_somente_leitura(self, _analise):
        Submissao.objects.create(atividade=self.pratica, aluno=self.aluno, resposta_texto="print('oi')")
        self.entrar(self.prof)
        resposta = self.client.get(reverse("entregas:corrigir", args=[self.pratica.pk]))
        self.assertContains(resposta, "data-editor-codigo")
        self.assertContains(resposta, 'data-somente-leitura="1"')
        self.assertContains(resposta, "print(&#x27;oi&#x27;)")

    def test_atividade_teorica_continua_sem_editor(self, _analise):
        Submissao.objects.create(atividade=self.teorica, aluno=self.aluno, resposta_texto="resposta")
        self.entrar(self.prof)
        resposta = self.client.get(reverse("entregas:corrigir", args=[self.teorica.pk]))
        self.assertNotContains(resposta, "data-editor-codigo")
        self.assertNotContains(resposta, "codemirror")


class EspacosImportamTest(EditorBase):

    def test_espacos_no_codigo_inicial_e_na_saida_sao_mantidos(self):
        self.entrar(self.prof)
        dados = self.dados_atividade(titulo="Triângulo", tipo=TIPO_PRATICA, codigo_inicial="    # indentado\n")
        dados.update({"casos-TOTAL_FORMS": "1", "casos-INITIAL_FORMS": "0", "casos-MIN_NUM_FORMS": "0", "casos-MAX_NUM_FORMS": "10",
                      "casos-0-entrada": "", "casos-0-saida_esperada": "  *\n ***\n*****"})
        self.client.post(reverse("core:atividade_create"), dados)
        atividade = Atividade.objects.get(titulo="Triângulo")
        self.assertEqual(atividade.codigo_inicial, "    # indentado\n")
        self.assertEqual(atividade.casos_de_teste.get().saida_esperada, "  *\n ***\n*****")
