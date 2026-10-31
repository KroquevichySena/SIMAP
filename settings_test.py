"""
Configuração usada só pelos testes de integração.

A ideia é a mesma do application-test.properties com H2 da aula: um banco
em memória, criado do zero a cada execução e jogado fora no final. Assim os
testes nunca encostam no PostgreSQL de desenvolvimento e rodam em qualquer
máquina, sem precisar de .env nem de banco instalado.

Uso:
    python manage.py test --settings=SIMAP.settings_test
"""
import os

# Valores fixos para os testes. Se o .env existir, ele não sobrescreve estes,
# porque o django-environ não troca variável que já está definida.
os.environ.setdefault("SECRET_KEY", "chave-apenas-para-testes-de-integracao")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("CSRF_TRUSTED_ORIGINS", "http://localhost,http://127.0.0.1")
os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")

from .settings import *  # noqa: E402,F401,F403

# Banco de teste em memória (equivalente ao H2 da aula). O Django cria as
# tabelas pelas migrations no início e descarta tudo no fim.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Nada de enviar e-mail de verdade nem chamar o Gemini durante os testes.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
GEMINI_API_KEY = ""
MAILGUN_API_KEY = ""

# Arquivos estáticos sem o manifest do WhiteNoise, que exigiria rodar o
# collectstatic antes dos testes.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Menos barulho no terminal durante os testes.
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "ERROR"  # noqa: F405

# Hash de senha rápido só nos testes (prática recomendada pela documentação do
# Django). Em produção continua o PBKDF2 definido no settings.py.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# O WhiteNoise avisa que a pasta do collectstatic não existe; nos testes isso
# é esperado, então o aviso só polui a saída.
import warnings  # noqa: E402

warnings.filterwarnings("ignore", message="No directory at")
