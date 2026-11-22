"""Gera credenciais descartaveis de testes locais, sem imprime-las."""
import secrets
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
destino = raiz / ".env.docker.local"
if destino.exists():
    raise SystemExit("Ambiente local ja existe; arquivo preservado.")
senha = secrets.token_hex(24)
chave = secrets.token_hex(48)
destino.write_text(
    f"SIMAP_TEST_DB_PASSWORD={senha}\n"
    f"SIMAP_TEST_SECRET={chave}\n"
    f"SIMAP_TEST_DATABASE_URL=postgresql://simap_test:{senha}@db:5432/simap_docker_test\n",
    encoding="utf-8",
)
print("Ambiente descartavel gerado; valores nao exibidos. Nao compartilhe o arquivo.")
