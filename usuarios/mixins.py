from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class CoordenacaoRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    permission_denied_message = "Apenas a coordenação pode cadastrar e consultar usuários."

    def test_func(self):
        return self.request.user.is_coordenacao
