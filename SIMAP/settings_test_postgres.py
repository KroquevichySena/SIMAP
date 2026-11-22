"""PostgreSQL exclusivo de testes; nao reutiliza a configuracao do banco publicado."""
import os

from .settings_test import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("SIMAP_TEST_POSTGRES_DB", "postgres"),
        "USER": os.environ.get("SIMAP_TEST_POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("SIMAP_TEST_POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("SIMAP_TEST_POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("SIMAP_TEST_POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        "TEST": {"NAME": "test_simap_regressao"},
    }
}
