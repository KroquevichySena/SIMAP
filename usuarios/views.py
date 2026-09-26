from django.conf import settings
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

from .forms import LoginComTermosForm
from .models import AceiteTermos


class LoginComTermosView(auth_views.LoginView):
    form_class = LoginComTermosForm

    def form_valid(self, form):
        response = super().form_valid(form)
        AceiteTermos.objects.get_or_create(
            usuario=form.get_user(),
            versao=settings.TERMOS_DE_USO_VERSAO,
        )
        return response


class TermosDeUsoView(TemplateView):
    template_name = 'usuarios/termos_de_uso.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_layout'] = (
            'base.html' if self.request.user.is_authenticated else 'base_publico.html'
        )
        context['versao_atual'] = settings.TERMOS_DE_USO_VERSAO
        return context
