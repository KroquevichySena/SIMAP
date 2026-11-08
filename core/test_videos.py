"""Testes dos vídeos do YouTube nas trilhas, atividades e mensagens."""
from django.test import SimpleTestCase
from django.urls import reverse

from comunicacao import servicos
from comunicacao.models import Publicacao

from .models import Atividade, TrilhaAprendizagem, VideoDeApoio
from .test_materiais import TrilhasBase
from .youtube import codigo_do_video, codigos_no_texto

CODIGO = "dQw4w9WgXcQ"


class ReconhecerLinkTest(SimpleTestCase):

    def test_formatos_aceitos(self):
        for link in [
            f"https://www.youtube.com/watch?v={CODIGO}",
            f"https://youtube.com/watch?v={CODIGO}&t=42s",
            f"https://m.youtube.com/watch?list=PL1&v={CODIGO}",
            f"https://youtu.be/{CODIGO}?si=abc",
            f"https://www.youtube.com/shorts/{CODIGO}",
            f"https://www.youtube.com/embed/{CODIGO}",
            f"https://www.youtube.com/live/{CODIGO}",
            f"http://www.youtube-nocookie.com/embed/{CODIGO}",
        ]:
            with self.subTest(link=link):
                self.assertEqual(codigo_do_video(link), CODIGO)

    def test_links_recusados(self):
        for link in [
            f"https://www.youtube.com.site-falso.com/watch?v={CODIGO}",
            f"https://site-falso.com/youtube.com/watch?v={CODIGO}",
            f"https://www.youtube.com@site-falso.com/watch?v={CODIGO}",
            f"https://usuario:senha@www.youtube.com/watch?v={CODIGO}",
            f"https://www.youtube.com:8080/watch?v={CODIGO}",
            f"javascript:alert('{CODIGO}')",
            f"ftp://youtu.be/{CODIGO}",
            "https://www.youtube.com/watch?v=curto",
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ"><script>',
            "https://www.youtube.com/channel/UC123",
            "https://vimeo.com/123456",
            "",
        ]:
            with self.subTest(link=link):
                self.assertIsNone(codigo_do_video(link))

    def test_videos_no_meio_do_texto(self):
        texto = (f"Assistam https://youtu.be/{CODIGO}. Repetido: https://www.youtube.com/watch?v={CODIGO} "
                 "e este outro (https://youtu.be/abcdefghijk), mas não https://vimeo.com/1")
        self.assertEqual(codigos_no_texto(texto), [CODIGO, "abcdefghijk"])


class VideosNoFormularioTest(TrilhasBase):

    def test_professor_adiciona_videos_a_atividade(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:atividade_create"), self.dados_atividade(
            videos=f"https://youtu.be/{CODIGO}\n\nhttps://www.youtube.com/watch?v=abcdefghijk\nhttps://youtu.be/{CODIGO}",
        ))
        self.assertRedirects(resposta, reverse("core:atividade_list"))
        atividade = Atividade.objects.get(titulo="Exercício 1")
        self.assertEqual(list(atividade.videos.values_list("codigo", flat=True)), [CODIGO, "abcdefghijk"])

    def test_link_que_nao_e_do_youtube_e_recusado(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:trilha_create"), self.dados_trilha(
            videos=f"https://www.youtube.com.site-falso.com/watch?v={CODIGO}",
        ))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não são vídeos do YouTube")
        self.assertFalse(TrilhaAprendizagem.objects.filter(titulo="Módulo 2").exists())

    def test_edicao_mostra_os_links_e_apagar_a_linha_remove_o_video(self):
        VideoDeApoio.objects.create(trilha=self.trilha, codigo=CODIGO)
        self.entrar(self.prof)
        url = reverse("core:trilha_update", args=[self.trilha.pk])
        self.assertContains(self.client.get(url), f"https://www.youtube.com/watch?v={CODIGO}")

        self.client.post(url, {
            "turma": self.turma.pk, "titulo": self.trilha.titulo, "descricao": "", "ordem": 1,
            "publicada": "on", "videos": "",
        })
        self.assertFalse(self.trilha.videos.exists())

    def test_limite_de_videos(self):
        self.entrar(self.prof)
        links = "\n".join(f"https://youtu.be/{i:011d}" for i in range(11))
        resposta = self.client.post(reverse("core:trilha_create"), self.dados_trilha(videos=links))
        self.assertContains(resposta, "no máximo 10 vídeos")


class VideosNaTelaTest(TrilhasBase):

    def test_aluno_ve_o_player_sem_cookies(self):
        VideoDeApoio.objects.create(trilha=self.trilha, codigo=CODIGO)
        atividade = Atividade.objects.create(trilha=self.trilha, titulo="Ex", enunciado="x", ordem=1)
        VideoDeApoio.objects.create(atividade=atividade, codigo="abcdefghijk")
        self.entrar(self.aluno)
        resposta = self.client.get(reverse("core:minhas_trilhas"))
        self.assertContains(resposta, f'src="https://www.youtube-nocookie.com/embed/{CODIGO}"')
        self.assertContains(resposta, 'src="https://www.youtube-nocookie.com/embed/abcdefghijk"')
        self.assertContains(resposta, 'referrerpolicy="strict-origin-when-cross-origin"')

    def test_video_de_trilha_em_rascunho_nao_aparece(self):
        TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).update(publicada=False)
        VideoDeApoio.objects.create(trilha=self.trilha, codigo=CODIGO)
        self.entrar(self.aluno)
        self.assertNotContains(self.client.get(reverse("core:minhas_trilhas")), CODIGO)

    def test_link_do_youtube_no_mural_vira_player(self):
        publicacao = servicos.publicar(
            self.prof, self.turma, f"Vídeo da aula: https://youtu.be/{CODIGO} e um falso "
            f"https://www.youtube.com.site-falso.com/watch?v=abcdefghijk"
        )
        self.entrar(self.aluno)
        for url in (reverse("comunicacao:mural", args=[self.turma.pk]), publicacao.get_absolute_url()):
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertContains(resposta, f"youtube-nocookie.com/embed/{CODIGO}")
                self.assertNotContains(resposta, "youtube-nocookie.com/embed/abcdefghijk")

    def test_link_do_youtube_na_resposta_vira_player(self):
        publicacao = servicos.publicar(self.aluno, self.turma, "Professor, tem algum vídeo?")
        servicos.responder(self.prof, publicacao, f"Veja este: https://www.youtube.com/watch?v={CODIGO}")
        self.entrar(self.aluno)
        self.assertContains(self.client.get(publicacao.get_absolute_url()), f"youtube-nocookie.com/embed/{CODIGO}")
        self.assertEqual(Publicacao.objects.count(), 1)
