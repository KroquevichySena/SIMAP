# Docker do SIMAP

Base: entrega1611 (5f5791957dffc40f89d1d40c501266cb5bca18f7).
Preparado inicialmente em copia local e integrado apos autorizacao informada pela equipe em 21/11.
O servico do Render roda por esta imagem (ver Publicacao no Render).

## Arquivos

Dockerfile instala Python 3.12 e dependencias, copia o codigo e executa com usuario sem privilegios.
requirements.docker.txt acrescenta Gunicorn sem modificar requirements.txt.
.dockerignore exclui credenciais, bancos locais, anexos, historico Git e ambientes virtuais.
docker/entrypoint.sh coleta arquivos estaticos ao iniciar e executa Gunicorn.
compose.yaml cria uma aplicacao e um PostgreSQL 16 exclusivamente locais, com volumes de teste.
O volume dados_teste_pg16 usa o caminho /var/lib/postgresql/data esperado pela imagem 16.
Volumes de PostgreSQL 18 nao sao reutilizados nem migrados automaticamente. O banco 16 usa um volume separado.
docker/preparar_ambiente_local.py gera as credenciais descartaveis sem exibi-las.

## Teste local

Na copia, com Docker Desktop ativo, execute:

    python docker/preparar_ambiente_local.py
    docker compose --env-file .env.docker.local -p simap-docker-proposta build
    docker compose --env-file .env.docker.local -p simap-docker-proposta up -d

Acesse http://127.0.0.1:18080/contas/login/.
O DEBUG do compose e True para teste HTTP local; isso NAO e configuracao de producao.
As contas precisam ser criadas apenas nesse banco ficticio:

    docker compose --env-file .env.docker.local -p simap-docker-proposta exec web python manage.py createsuperuser

Nao compartilhe credenciais. Nao utilize dados reais.
Para executar os testes SQLite dentro da imagem:

    docker compose --env-file .env.docker.local -p simap-docker-proposta run --rm --no-deps web python manage.py test --settings=SIMAP.settings_test --verbosity 0 --noinput

Para parar, preservando os volumes de teste:

    docker compose --env-file .env.docker.local -p simap-docker-proposta down

Nao execute compose config nem docker inspect sem filtrar campos: podem exibir variaveis.
O arquivo local de credenciais nunca deve ser versionado nem colocado na imagem.

## Inicializacao

A porta usa PORT (padrao 8000). Gunicorn usa um worker, duas threads e timeout de 120 segundos por padrao.
O comando web executa collectstatic com as variaveis de runtime; nenhuma credencial e necessaria no build.
RUN_MIGRATIONS=1 executa migrations antes do servidor. O compose local usa isso para um banco vazio.
Em producao, planejar migrations uma vez por publicacao, antes de multiplicar instancias. O padrao e nao migrar.
Comandos alternativos passam direto pelo entrypoint, sem migrar nem coletar arquivos.

## Publicacao no Render

O simap.onrender.com roda por esta imagem, no mesmo servico de antes, com o
runtime trocado para Docker. O servico fica em Virginia (EUA), a mesma regiao do banco Neon.
As variaveis SECRET_KEY, DATABASE_URL, DEBUG=False, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS,
SECURE_SSL_REDIRECT=True, SIMAP_PUBLIC_URL e as credenciais de integracoes ficam somente no
Environment do Render. Nao copiar .env nem passar segredos por ARG no Dockerfile.

RUN_MIGRATIONS=1 esta configurada: o conteiner executa as migrations antes de iniciar o
Gunicorn, em cada publicacao e a cada vez que o servico acorda. Sem migrations pendentes,
isso so acrescenta alguns segundos. Se uma migration falhar, a publicacao nao sobe e o
Render mantem a versao anterior. Isso e seguro enquanto houver uma unica instancia; com
mais de uma, rodar as migrations uma vez antes da publicacao e desligar a variavel.
WEB_CONCURRENCY nao esta configurada, entao vale o padrao de um worker.

O RF33 nao roda como worker no Render: o agendamento e feito pelo GitHub Actions
(ver docs/RF33_NOTIFICACOES.md).
A imagem base Python 3.12 esta fixada pelo digest testado; revisar atualizacoes de seguranca antes de uso prolongado.

## Limites

Docker nao resolve hibernacao, latencia Render/Neon ou perda de anexos no Render gratuito.
O volume anexos_teste persiste somente no Docker local; nao cria disco persistente no Render.
Esta branch inclui a correcao do bloqueio da chamada no PostgreSQL e a reutilizacao de dados do painel docente.
Os testes de bloqueio devem ser executados com SIMAP.settings_test_postgres; SQLite nao valida esse comportamento.
O banco local nao e o Neon; nao migramos dados da demonstracao publicada.
Revisar a politica de backups do Neon; o plano gratuito nao substitui uma copia de seguranca propria.
