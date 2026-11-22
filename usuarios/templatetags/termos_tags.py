"""{% versao_termos_vigente %}: o número da versão vigente, para a página saber qual foi aceita."""
from django import template

from usuarios.termos import numero_vigente

register = template.Library()
register.simple_tag(numero_vigente, name="versao_termos_vigente")
