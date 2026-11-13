from django.contrib import admin
from .models import Instituicao
from .models import Turma
from .models import Matricula

admin.site.register(Instituicao)
admin.site.register(Turma)
admin.site.register(Matricula)
    

