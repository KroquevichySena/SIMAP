from django.contrib import admin

from .models import Instituicao, Matricula, Turma

admin.site.register(Instituicao)
admin.site.register(Turma)
admin.site.register(Matricula)


