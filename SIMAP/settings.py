"""
Configurações do SIMAP, o Sistema de Monitoramento da Aprendizagem em Programação.

Rodamos com Django 5.2 LTS, Python 3.12 e PostgreSQL 16. Tudo que é segredo
ou muda de uma máquina para outra (senhas, chaves, endereço do banco) vem do
arquivo .env, e não daqui.
"""

from pathlib import Path

import environ

# A pasta raiz do projeto, usada como ponto de partida para os outros caminhos.
BASE_DIR = Path(__file__).resolve().parent.parent

# As credenciais ficam no .env, que não vai para o GitHub. Aqui dizemos ao
# django-environ o tipo de cada variável e o valor padrão, caso ela não exista.
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    SECURE_SSL_REDIRECT=(bool, False),
)

# Carrega o .env da raiz do projeto, se ele existir.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Em produção o site roda num domínio do Render, e o Django precisa saber que
# pode confiar nele para a proteção contra CSRF funcionar.
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# Os apps do Django que o projeto usa, e os nossos.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "auditoria",  # antes dos outros apps do SIMAP, para já ouvir tudo desde o início
    "usuarios",
    "turmas",
    "core",
    "chamada",
    "entregas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # A auditoria vem depois da autenticação porque precisa saber quem é o usuário
    "auditoria.middleware.AuditoriaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "SIMAP.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "SIMAP.wsgi.application"

# O banco é o PostgreSQL 16. O endereço vem inteiro do .env, neste formato:
# postgres://usuario:senha@host:5432/nome_banco
DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}

# Em vez de abrir uma conexão nova a cada requisição, reaproveitamos por até
# 60 segundos, conferindo antes se ela ainda está funcionando.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Login, senhas e sessão.
AUTH_USER_MODEL = "usuarios.Usuario"

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "login"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        # O padrão do Django é 8 caracteres; aqui exigimos 10.
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# As senhas nunca são guardadas como texto. O PBKDF2 gera um hash com um salt
# diferente para cada usuário, então duas senhas iguais ficam diferentes no banco.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# Quem fica 8 horas sem usar o sistema precisa entrar de novo.
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True  # cada clique renova o prazo

# Versão vigente dos Termos de Uso e Política de Privacidade.
# Fonte única: alimenta o texto exibido em usuarios/termos_de_uso.html e a
# checagem de reaceite em usuarios/forms.py (LoginComTermosForm).
TERMOS_DE_USO_VERSAO = "1.2"

# Idioma e fuso horário.
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True  # datas vão para o banco com fuso (timestamptz no PostgreSQL)

# Arquivos estáticos (CSS, JS, imagens). Em produção quem entrega é o WhiteNoise.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"   # para onde o collectstatic copia tudo
STATICFILES_DIRS = [BASE_DIR / "static"] # onde ficam os arquivos que a gente edita

# No Django 5 essa configuração mudou de nome para STORAGES. Em produção os
# arquivos são comprimidos e ganham um código no nome, para o navegador não
# ficar preso a uma versão antiga em cache.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# Tipo do ID dos modelos que não definem um próprio: 'serial', de 4 bytes.
# Atenção: os apps core, turmas, usuarios e chamada definem BigAutoField no
# apps.py deles, e isso vale mais do que esta linha, então lá o ID é de 8 bytes.
# A tabela de auditoria usa 8 bytes de propósito, porque só cresce.
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Chaves das APIs externas: o Gemini, que analisa as respostas, e o Mailgun, dos e-mails.
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_API_URL = env(
    "GEMINI_API_URL", default="https://generativelanguage.googleapis.com"
)

MAILGUN_API_KEY = env("MAILGUN_API_KEY", default="")
MAILGUN_DOMAIN = env("MAILGUN_DOMAIN", default="")
MAILGUN_API_URL = env("MAILGUN_API_URL", default="https://api.mailgun.net")

# E-mail. Sem nada no .env, as mensagens só aparecem no terminal; em produção
# o .env aponta para o backend do Mailgun.
# O "or" cobre o caso de EMAIL_BACKEND= vazio no .env, que o django-environ
# devolve como texto vazio em vez de usar o padrão, e quebrava o envio.
EMAIL_BACKEND = (
    env("EMAIL_BACKEND", default="")
    or "django.core.mail.backends.console.EmailBackend"
)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="nao-responda@simap.local")

# Faz as mensagens do Django (sucesso, erro...) usarem as cores do Bootstrap.
# O Bootstrap chama o vermelho de 'danger', e não de 'error'.
from django.contrib.messages import constants as messages  # noqa: E402

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

# Cabeçalhos de segurança que valem sempre, até em desenvolvimento.
X_FRAME_OPTIONS = "DENY"                 # ninguém pode abrir o SIMAP dentro de um iframe
SECURE_CONTENT_TYPE_NOSNIFF = True       # o navegador não tenta adivinhar o tipo do arquivo
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # False: necessário para envio via JS/AJAX
    SECURE_HSTS_SECONDS = 31536000        # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # O Render recebe o HTTPS e repassa para o Django por dentro. Sem esta linha,
    # o Django acharia que a conexão não é segura.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Logs no terminal. A ficha pede que uma falha nas APIs externas fique registrada
# aqui sem derrubar o sistema.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        # Um log só para as integrações externas (Gemini e Mailgun).
        "simap.integracoes": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Auditoria
# Por quantos dias guardamos os registros. Depois disso, o comando
# limpar_auditoria apaga os antigos, como a LGPD pede. Em produção ele deve
# rodar uma vez por dia.
AUDITORIA_RETENCAO_DIAS = env.int("AUDITORIA_RETENCAO_DIAS", default=180)

# Quantos proxies existem entre o usuário e o Django. No Render existe 1,
# então o IP real vem do cabeçalho X-Forwarded-For. Na sua máquina é 0,
# porque ali esse cabeçalho pode ser inventado por qualquer um.
AUDITORIA_PROXIES_CONFIAVEIS = env.int("AUDITORIA_PROXIES_CONFIAVEIS", default=0)

LOGGING["loggers"]["simap.auditoria"] = {
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}
