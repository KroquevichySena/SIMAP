"""Regressões de arquivos disfarçados, conteúdo ativo e reconstrução segura."""
import hashlib
import io
import zipfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

from .arquivos_teste import PDF_OK, PNG_OK, adicionar_javascript, imagem_teste, office_teste, pdf_teste
from .seguranca import validar_anexo
from .validacao_documentos import NS_REL_DOC, NS_RELS


def validar(nome, conteudo):
    return validar_anexo(SimpleUploadedFile(nome, conteudo))


class ImagensSegurasTest(SimpleTestCase):
    def test_aceita_e_reconstroi_todos_os_formatos(self):
        for extensao, formato in (("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("gif", "GIF"), ("webp", "WEBP")):
            with self.subTest(extensao=extensao):
                dados = validar("foto." + extensao, imagem_teste(formato))
                with Image.open(io.BytesIO(dados.conteudo_seguro)) as imagem:
                    self.assertEqual(imagem.format, formato)
                    imagem.load()
                self.assertEqual(dados.tamanho, len(dados.conteudo_seguro))
                self.assertEqual(dados.sha256, hashlib.sha256(dados.conteudo_seguro).hexdigest())

    def test_rejeita_apenas_assinatura_e_imagens_truncadas(self):
        for nome, conteudo in (("foto.png", b"\x89PNG\r\n\x1a\n" + bytes(32)),
                               ("foto.webp", b"RIFF" + bytes(4) + b"WEBP" + b"texto"),
                               ("foto.jpg", imagem_teste("JPEG")[:-30])):
            with self.subTest(nome=nome), self.assertRaises(ValidationError):
                validar(nome, conteudo)

    def test_remove_conteudo_acrescentado_e_metadados(self):
        marcador = b"CONTEUDO-ALHEIO-A-IMAGEM"
        exif = Image.Exif()
        exif[270] = marcador.decode("ascii")
        conteudo = imagem_teste("WEBP", exif=exif) + marcador
        dados = validar("foto.webp", conteudo)
        self.assertNotIn(marcador, dados.conteudo_seguro)
        with Image.open(io.BytesIO(dados.conteudo_seguro)) as imagem:
            self.assertNotIn("exif", imagem.info)

    def test_rejeita_imagem_com_extensao_de_outro_formato(self):
        with self.assertRaises(ValidationError):
            validar("foto.webp", PNG_OK)

    def test_respeita_orientacao_da_foto_antes_de_remover_exif(self):
        saida = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6  # Rotação de 90 graus normalmente aplicada pelo visualizador.
        Image.new("RGB", (3, 7), "blue").save(saida, format="JPEG", exif=exif)
        dados = validar("foto.jpg", saida.getvalue())
        with Image.open(io.BytesIO(dados.conteudo_seguro)) as imagem:
            self.assertEqual(imagem.size, (7, 3))
            self.assertFalse(imagem.getexif())

    def test_limita_pixels_antes_de_decodificar(self):
        with patch("comunicacao.validacao_documentos.MAX_PIXELS", 20):
            with self.assertRaisesMessage(ValidationError, "pixels"):
                validar("foto.png", PNG_OK)

    def test_preserva_animacao_pequena_e_limita_quadros(self):
        saida = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(saida, format="GIF", save_all=True,
            append_images=[Image.new("RGB", (8, 8), "red")], duration=[100, 200], loop=0)
        dados = validar("animacao.gif", saida.getvalue())
        with Image.open(io.BytesIO(dados.conteudo_seguro)) as imagem:
            self.assertEqual(imagem.n_frames, 2)
        with patch("comunicacao.validacao_documentos.MAX_QUADROS", 1):
            with self.assertRaisesMessage(ValidationError, "quadros"):
                validar("animacao.gif", saida.getvalue())


class PdfSeguroTest(SimpleTestCase):
    def test_aceita_pdf_integro(self):
        self.assertEqual(validar("texto.pdf", PDF_OK).tamanho, len(PDF_OK))

    def test_rejeita_pdf_so_com_assinatura_truncado_ou_com_conteudo_apos_final(self):
        for conteudo in (b"%PDF-1.7\ntexto\n%%EOF", PDF_OK[:100], PDF_OK + b"conteudo extra"):
            with self.subTest(conteudo=conteudo[:20]), self.assertRaises(ValidationError):
                validar("texto.pdf", conteudo)

    def test_rejeita_pdf_criptografado(self):
        with self.assertRaisesMessage(ValidationError, "senha"):
            validar("texto.pdf", pdf_teste(lambda escritor: escritor.encrypt("segredo")))

    def test_rejeita_javascript_e_arquivo_embutido(self):
        for configurar in (adicionar_javascript, lambda e: e.add_attachment("teste.txt", b"teste")):
            with self.subTest(configurar=configurar), self.assertRaisesMessage(ValidationError, "conteúdo ativo"):
                validar("texto.pdf", pdf_teste(configurar))

    def test_rejeita_acao_em_anotacao_e_objeto_indireto(self):
        def configurar(escritor):
            acao = DictionaryObject(
                {NameObject("/S"): NameObject("/Launch"), NameObject("/F"): TextStringObject("teste")}
            )
            anotacao = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Link"),
                    NameObject("/A"): escritor._add_object(acao),
                }
            )
            escritor.pages[0][NameObject("/Annots")] = ArrayObject([escritor._add_object(anotacao)])

        with self.assertRaisesMessage(ValidationError, "conteúdo ativo"):
            validar("texto.pdf", pdf_teste(configurar))

    def test_rejeita_nome_de_acao_com_escape_pdf(self):
        class NomeComEscape(NameObject):
            def write_to_stream(self, stream, encryption_key=None):
                stream.write(b"/Java#53cript")

        def configurar(escritor):
            escritor._root_object[NameObject("/OpenAction")] = DictionaryObject(
                {
                    NameObject("/S"): NomeComEscape("/JavaScript"),
                }
            )

        with self.assertRaisesMessage(ValidationError, "conteúdo ativo"):
            validar("texto.pdf", pdf_teste(configurar))

    def test_limita_quantidade_de_objetos(self):
        with patch("comunicacao.validacao_documentos.MAX_OBJETOS_PDF", 1):
            with self.assertRaisesMessage(ValidationError, "objetos"):
                validar("texto.pdf", PDF_OK)

    def test_link_normal_permitido_protocolo_ativo_bloqueado(self):
        for destino, permitido in (
            ("https://example.com/aula", True),
            ("javascript:teste", False),
            ("file:///teste", False),
        ):

            def configurar(escritor, destino=destino):
                escritor._root_object[NameObject("/OpenAction")] = DictionaryObject(
                    {
                        NameObject("/S"): NameObject("/URI"),
                        NameObject("/URI"): TextStringObject(destino),
                    }
                )

            with self.subTest(destino=destino):
                if permitido:
                    validar("texto.pdf", pdf_teste(configurar))
                else:
                    with self.assertRaises(ValidationError):
                        validar("texto.pdf", pdf_teste(configurar))

    def test_texto_de_comando_em_pdf_nao_e_acao_executavel(self):
        conteudo = pdf_teste(lambda e: e.add_metadata({"/Subject": "Exemplo didático: shutdown -a"}))
        validar("material.pdf", conteudo)


class OfficeSeguroTest(SimpleTestCase):
    def test_aceita_formatos_sem_conteudo_ativo(self):
        for extensao, principal in (
            ("docx", "word/document.xml"),
            ("xlsx", "xl/workbook.xml"),
            ("pptx", "ppt/presentation.xml"),
        ):
            with self.subTest(extensao=extensao):
                dados = validar("aula." + extensao, office_teste(principal))
                with zipfile.ZipFile(io.BytesIO(dados.conteudo_seguro)) as pacote:
                    self.assertIn(principal, pacote.namelist())

    def test_rejeita_xml_invalido_e_entidades(self):
        for xml in (b"<document", b'<!DOCTYPE x [<!ENTITY t "teste">]><document>&t;</document>'):
            with self.subTest(xml=xml), self.assertRaises(ValidationError):
                validar("aula.docx", office_teste(substituir={"word/document.xml": xml}))

    def test_rejeita_programa_extra_caminho_invalido_e_embutidos(self):
        for nome in (
            "programa.exe",
            "word/programa.exe",
            "word/extra.txt",
            "word/embeddings/objeto.bin",
            "../fora.xml",
        ):
            with self.subTest(nome=nome), self.assertRaises(ValidationError):
                validar("aula.docx", office_teste(extras=[nome]))

    def test_rejeita_partes_duplicadas(self):
        saida = io.BytesIO(office_teste())
        with zipfile.ZipFile(saida, "a") as pacote:
            pacote.writestr("WORD/document.xml", b"<teste/>")
        with self.assertRaisesMessage(ValidationError, "duplicadas"):
            validar("aula.docx", saida.getvalue())

    def test_rejeita_tipo_principal_incompativel(self):
        conteudo = office_teste("xl/workbook.xml", substituir={"word/document.xml": b"<document/>"})
        with self.assertRaises(ValidationError):
            validar("aula.docx", conteudo)

    def test_rejeita_tamanho_descompactado_e_numero_de_partes(self):
        for limite in ("MAX_OFFICE_ABERTO", "MAX_PARTES_OFFICE"):
            with self.subTest(limite=limite), patch("comunicacao.validacao_documentos." + limite, 1):
                with self.assertRaisesMessage(ValidationError, "grande demais"):
                    validar("aula.docx", office_teste())

    def test_links_normais_permitidos_recursos_externos_bloqueados(self):
        for tipo, destino, permitido in (
            ("hyperlink", "https://example.com/aula", True),
            ("hyperlink", "javascript:teste", False),
            ("image", "https://example.com/foto.png", False),
            ("attachedTemplate", "https://example.com/modelo", False),
        ):
            rels = (
                f'<Relationships xmlns="{NS_RELS}"><Relationship Id="rId2" '
                f'Type="{NS_REL_DOC}{tipo}" Target="{destino}" TargetMode="External"/></Relationships>'
            ).encode()
            conteudo = office_teste(substituir={"word/_rels/document.xml.rels": rels})
            with self.subTest(tipo=tipo, destino=destino):
                if permitido:
                    validar("aula.docx", conteudo)
                else:
                    with self.assertRaises(ValidationError):
                        validar("aula.docx", conteudo)

    def test_rejeita_relacionamento_interno_inexistente(self):
        rels = (
            f'<Relationships xmlns="{NS_RELS}"><Relationship Id="rId2" '
            f'Type="{NS_REL_DOC}image" Target="media/ausente.png"/></Relationships>'
        ).encode()
        with self.assertRaisesMessage(ValidationError, "inexistente"):
            validar("aula.docx", office_teste(substituir={"word/_rels/document.xml.rels": rels}))

    def test_imagem_embutida_tambem_e_reconstruida(self):
        marcador = b"CONTEUDO-EXTRA"
        conteudo = office_teste(substituir={"word/media/image1.png": PNG_OK + marcador})
        dados = validar("aula.docx", conteudo)
        with zipfile.ZipFile(io.BytesIO(dados.conteudo_seguro)) as pacote:
            self.assertNotIn(marcador, pacote.read("word/media/image1.png"))

    def test_rejeita_imagem_embutida_falsa(self):
        with self.assertRaises(ValidationError):
            validar("aula.docx", office_teste(substituir={"word/media/image1.png": b"falsa"}))

    def test_rejeita_dde_em_campo_word(self):
        xml = (
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b"<w:instrText>DD</w:instrText><w:instrText>EAUTO teste</w:instrText></w:document>"
        )
        with self.assertRaises(ValidationError):
            validar("aula.docx", office_teste(substituir={"word/document.xml": xml}))

    def test_formula_comum_permitida_conexoes_e_comandos_bloqueados(self):
        for formula, permitido in (
            ("SUM(A1:A3)", True),
            ('WEBSERVICE("https://example.com")', False),
            ("cmd|teste!A1", False),
            ('HYPERLINK("file:///teste")', False),
        ):
            xml = (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f"<sheetData><row><c><f>{formula}</f></c></row></sheetData></worksheet>"
            ).encode()
            conteudo = office_teste("xl/workbook.xml", substituir={"xl/worksheets/sheet1.xml": xml})
            with self.subTest(formula=formula):
                if permitido:
                    validar("aula.xlsx", conteudo)
                else:
                    with self.assertRaises(ValidationError):
                        validar("aula.xlsx", conteudo)

    def test_rejeita_tipos_de_partes_enganosos(self):
        conteudo = office_teste(substituir={"word/media/image1.png": PNG_OK})
        entrada, saida = io.BytesIO(conteudo), io.BytesIO()
        with zipfile.ZipFile(entrada) as antigo, zipfile.ZipFile(saida, "w") as novo:
            for item in antigo.infolist():
                dados = antigo.read(item)
                if item.filename == "[Content_Types].xml":
                    dados = dados.replace(b"image/png", b"application/octet-stream")
                novo.writestr(item.filename, dados)
        with self.assertRaisesMessage(ValidationError, "tipo declarado"):
            validar("aula.docx", saida.getvalue())
