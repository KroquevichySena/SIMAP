"""Filtros {{ conta.email|email_mascarado }} e {{ conta.rgm|rgm_mascarado }} para os templates."""
from django import template

from usuarios.mascaras import mascarar_email, mascarar_rgm

register = template.Library()
register.filter("email_mascarado", mascarar_email)
register.filter("rgm_mascarado", mascarar_rgm)
