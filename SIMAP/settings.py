"""
Django settings para o projeto SIMAP.
Sistema de Monitoramento da Aprendizagem em Programação.
Django 5.2 LTS | Python 3.12 | PostgreSQL 16
"""

from pathlib import Path

import environ

# ==============================================================================
# CAMINHOS BASE
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# VARIÁVEIS DE AMBIENTE (django-environ)
# Segurança: credenciais ficam no .env, fora do controle de versão.
# ==============================================================================
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    SECURE_SSL_REDIRECT=(bool, False),
)

# Lê o arquivo .env (se existir) da raiz do projeto
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Necessário para o Render/produção (proteção CSRF em domínio externo)
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# ==============================================================================
# APLICAÇÕES
# ==============================================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "usuarios",
    "turmas",
    "core",
    "chamada",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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

# ==============================================================================
# BANCO DE DADOS — PostgreSQL 16
# Formato do DATABASE_URL: postgres://usuario:senha@host:5432/nome_banco
# ==============================================================================
DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}

# Reaproveita conexões (reduz latência) e valida se estão vivas
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# ==============================================================================
# AUTENTICAÇÃO E AUTORIZAÇÃO
# ==============================================================================
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
        # Mínimo elevado de 8 (padrão) para 10 caracteres
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Algoritmo de hash: PBKDF2 (padrão do Django, com salt automático)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# Sessão expira em 8 horas de inatividade
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True  # Renova a sessão a cada interação

# ==============================================================================
# INTERNACIONALIZAÇÃO
# ==============================================================================
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True  # DateTimeField -> 'timestamptz' no PostgreSQL

# ==============================================================================
# ARQUIVOS ESTÁTICOS (WhiteNoise)
# ==============================================================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"   # destino do collectstatic
STATICFILES_DIRS = [BASE_DIR / "static"] # seus arquivos de desenvolvimento

# Django 5.x usa STORAGES (STATICFILES_STORAGE foi removido na 5.1)
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

# ==============================================================================
# CHAVE PRIMÁRIA PADRÃO
# Otimização do PFC: 'serial' (4 bytes) em vez de 'bigserial' (8 bytes).
# Tabelas de crescimento contínuo (ex.: RegistroAuditoria) sobrescrevem
# localmente com models.BigAutoField(primary_key=True).
# ==============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# ==============================================================================
# APIS EXTERNAS
# ==============================================================================
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_API_URL = env(
    "GEMINI_API_URL", default="https://generativelanguage.googleapis.com"
)

MAILGUN_API_KEY = env("MAILGUN_API_KEY", default="")
MAILGUN_DOMAIN = env("MAILGUN_DOMAIN", default="")
MAILGUN_API_URL = env("MAILGUN_API_URL", default="https://api.mailgun.net")

# ==============================================================================
# E-MAIL
# ==============================================================================
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="nao-responda@simap.local")

# ==============================================================================
# MENSAGENS (compatibilidade com classes do Bootstrap 5.3)
# ==============================================================================
from django.contrib.messages import constants as messages  # noqa: E402

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

# ==============================================================================
# SEGURANÇA
# ==============================================================================
X_FRAME_OPTIONS = "DENY"                 # Anti-clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True       # Anti-MIME sniffing
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
    # O Render entrega HTTPS via proxy reverso; sem isto o Django não detecta
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==============================================================================
# LOGGING
# Requisito da Ficha: falhas de API registradas em log sem interromper o sistema.
# ==============================================================================
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
        # Logger dedicado às integrações externas (Gemini/Mailgun)
        "simap.integracoes": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}