from django.contrib.auth.models import UserManager


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("perfil", "COORDENACAO")
        if extra_fields["perfil"] != "COORDENACAO":
            raise ValueError("Uma conta superusuária deve possuir o perfil Coordenação.")
        return super().create_superuser(username, email=email, password=password, **extra_fields)
