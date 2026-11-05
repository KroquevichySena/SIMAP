"""Quando um anexo sai do banco, o arquivo também sai do disco."""
from .arquivos import conectar_limpeza_do_disco
from .models import Anexo

conectar_limpeza_do_disco(Anexo)
