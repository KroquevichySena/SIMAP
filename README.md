# SIMAP — Sistema de Monitoramento da Aprendizagem em Programação

Plataforma web para disciplinas introdutórias de programação. Centraliza a gestão de turmas, o registro de presença, as trilhas de aprendizagem com atividades teóricas e práticas, a análise das entregas com apoio de IA, a comunicação entre docente e discente e os painéis de desempenho de cada perfil.

Projeto Final de Curso — Engenharia de Software, Universidade de Mogi das Cruzes (UMC).

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Funcionalidades](#2-funcionalidades)
3. [Arquitetura e tecnologias](#3-arquitetura-e-tecnologias)
4. [Instruções de execução](#4-instruções-de-execução)
5. [Roteiro de verificação](#5-roteiro-de-verificação)
6. [Regras de negócio](#6-regras-de-negócio)
7. [Testes e qualidade](#7-testes-e-qualidade)
8. [Segurança e LGPD](#8-segurança-e-lgpd)
9. [Problemas comuns](#9-problemas-comuns)
10. [Documentação complementar](#10-documentação-complementar)
11. [Estrutura do projeto](#11-estrutura-do-projeto)

---

## 1. Visão geral

Em turmas iniciais de programação, o docente tem dificuldade de identificar a tempo quais alunos precisam de atenção, e as ferramentas comuns (planilhas e sistemas acadêmicos genéricos) não acompanham a aprendizagem em programação. O SIMAP reúne esse acompanhamento num só lugar.

O sistema tem três perfis:

| Perfil | Quem é | O que faz |
|---|---|---|
| **Coordenação** | Conta administrativa (superusuário sem perfil discente) | Cadastra docentes e discentes e consulta a auditoria |
| **Docente** | Professor da disciplina | Cria turmas, matrículas, trilhas e atividades; faz a chamada; corrige as entregas; acompanha o painel da turma |
| **Discente** | Aluno matriculado | Realiza as atividades, confirma presença, pede ajuda à IA e acompanha a própria evolução |

---

## 2. Funcionalidades

| Módulo | O que o sistema faz |
|---|---|
| **Acesso** | Login, cadastro de usuários pela Coordenação com senha temporária, troca obrigatória da senha no primeiro acesso, aceite versionado dos termos de uso, recuperação de senha por e-mail |
| **Turmas** | Criação de turmas, matrículas, alteração da situação da matrícula, limite de atenção da turma |
| **Trilhas e atividades** | Trilhas e atividades em rascunho ou publicadas, ordem de exibição, material de apoio, vídeos do YouTube, prazos e conclusão das atividades |
| **Editor de código** | Execução de Python no navegador do aluno (Pyodide), casos de teste do professor, rascunho salvo automaticamente |
| **Entregas** | Envio de respostas e anexos, análise consultiva pelo Google Gemini (resumo e pontos de atenção), nota e devolutiva publicadas só após a validação do docente |
| **Ajuda da IA ao aluno** | Dicas em níveis, explicação de conceitos, busca de material e leitura de erros do código, sem entregar a solução |
| **Chamada** | Chamada por QR code projetado, com código que expira, renovação, confirmação pelo celular, presenças em análise e lista de faltas |
| **Comunicação** | Avisos e comentários na turma, mensagens, anexos validados, notificações internas e e-mails automáticos de atenção e feedback (RF33) |
| **Painéis** | Painel do docente com indicadores da turma e destaque dos alunos em atenção; painel do discente com a própria frequência, entregas e progresso |
| **Auditoria** | Registro das ações relevantes, com filtros e exportação em CSV, e limpeza pelo prazo de retenção |

---

## 3. Arquitetura e tecnologias

O SIMAP é uma **aplicação web monolítica e modular**, no padrão **MVT (Model-View-Template)** do Django:

- **Model:** os dados e as regras simples de cada objeto (`models.py`).
- **View:** recebe a requisição, confere a permissão e chama a regra (`views.py`).
- **Template:** o HTML, renderizado no servidor (`templates/`).
- **Camada de serviços:** as regras de negócio maiores ficam em `servicos.py`, separadas das views, o que facilita os testes.

Cada domínio é um app do Django (veja a [estrutura do projeto](#11-estrutura-do-projeto)). Todos rodam no mesmo processo e no mesmo banco, e se comunicam por chamadas diretas, sem API intermediária.

| Camada | Tecnologia |
|---|---|
| Linguagem e framework | Python 3.12, Django 5.2 LTS |
| Banco de dados | PostgreSQL 16 (SQLite aceito para avaliação local) |
| Interface | Django Templates, HTML5, CSS3, JavaScript, Bootstrap 5.3, Chart.js |
| Execução de código do aluno | Pyodide (Python no navegador, nunca no servidor) |
| Integrações | Google Gemini (análise das entregas e ajuda ao aluno), Mailgun (e-mails) |
| Arquivos estáticos | WhiteNoise |
| Qualidade | Testes do Django, Ruff (linter), GitHub Actions (CI) |

---

## 4. Instruções de execução

Passo a passo para instalar, configurar e rodar o SIMAP numa máquina Windows. Os comandos são para o PowerShell.

### 4.1 Pré-requisitos

| Ferramenta | Versão | Observação |
|---|---|---|
| Python | **3.12** | `winget install Python.Python.3.12` (feche e abra o terminal depois) |
| Git | recente | para clonar o repositório |
| PostgreSQL | 16 (opcional) | sem ele, o sistema roda com SQLite |

### 4.2 Instalação

```bash
git clone https://github.com/KroquevichySena/SIMAP.git
cd SIMAP
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

O prefixo `(venv)` deve aparecer no início da linha do terminal.

### 4.3 Configuração do `.env`

Toda a configuração vem de variáveis de ambiente, e nenhuma credencial fica no código. Crie o `.env` a partir do modelo:

```bash
copy .env.example .env
```

Gere uma `SECRET_KEY` e cole no `.env`:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

| Variável | Obrigatória | Para que serve | Valor local |
|---|---|---|---|
| `SECRET_KEY` | sim | assinatura de sessões e cookies | a chave gerada acima |
| `DEBUG` | sim | modo de desenvolvimento | `True` (produção: `False`) |
| `ALLOWED_HOSTS` | sim | domínios aceitos | `127.0.0.1,localhost` |
| `CSRF_TRUSTED_ORIGINS` | sim | origens aceitas nos formulários | `http://127.0.0.1:8000,http://localhost:8000` |
| `DATABASE_URL` | sim | conexão com o banco | `sqlite:///db.sqlite3` ou `postgres://USUARIO:SENHA@localhost:5432/simap` |
| `SECURE_SSL_REDIRECT` | não | força HTTPS | `False` (produção: `True`) |
| `GEMINI_API_KEY` | não | análise das entregas e ajuda ao aluno | chave do [Google AI Studio](https://aistudio.google.com/) |
| `TUTORIA_MODELO` | não | modelo do Gemini na ajuda ao aluno | padrão `gemini-3.1-flash-lite` |
| `TUTORIA_BUSCA_NA_WEB` | não | busca de material na web | padrão `True` |
| `EMAIL_BACKEND` | não | envio de e-mails | console (os e-mails aparecem no terminal) |
| `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_API_URL` | não | envio real de e-mails | vazios no ambiente local |
| `DEFAULT_FROM_EMAIL` | não | remetente dos e-mails | `nao-responda@simap.local` |
| `AUDITORIA_RETENCAO_DIAS` | não | dias de guarda da auditoria | `180` |
| `AUDITORIA_PROXIES_CONFIAVEIS` | não | proxies na frente do Django | `0` |
| `CONN_MAX_AGE`, `DJANGO_LOG_LEVEL`, `SIMAP_PYODIDE_URL` | não | ajustes finos | já têm valor padrão |

Sem `GEMINI_API_KEY`, as funções de IA ficam indisponíveis e o restante do sistema funciona normalmente. Sem Mailgun, os e-mails (recuperação de senha, notificações) são impressos no terminal do `runserver`.

> **Segurança:** o `.env` está no `.gitignore` e nunca deve ir para o repositório. Use apenas dados fictícios.

### 4.4 Banco de dados e primeiro usuário

```bash
python manage.py migrate
python manage.py createsuperuser
```

A conta criada pelo `createsuperuser` é a **Coordenação**. Não atribua a ela o perfil DISCENTE. No primeiro login, ela aceita os termos de uso e passa a ver o menu **Usuários**, onde cadastra docentes e discentes.

**Dados de demonstração (opcional).** O comando abaixo cria um docente, alunos, uma turma e trilhas com atividades de exemplo. Ele se recusa a rodar em produção:

```bash
python manage.py popular_dados
python manage.py popular_dados --limpar   # apaga e recria os dados de exemplo
```

### 4.5 Rodar

```bash
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`. Cada perfil entra na sua área: a Coordenação em **Usuários**, o docente no **painel do docente** e o discente no **painel do discente**.

### 4.6 Comandos de manutenção

| Comando | O que faz |
|---|---|
| `python manage.py notificar_prazos` | Notifica os alunos sobre atividades com prazo próximo ainda não entregues (`--horas` define a janela, padrão 24) |
| `python manage.py limpar_auditoria` | Remove registros de auditoria mais antigos que o prazo de retenção (`--simular` só mostra a quantidade; `--dias` muda o prazo) |

---

## 5. Roteiro de verificação

Siga na ordem, porque cada etapa usa os dados da anterior. Para usar dois perfis ao mesmo tempo, abra uma janela anônima para o segundo.

| # | Perfil | O que fazer | Resultado esperado |
|---|---|---|---|
| 1 | Coordenação | **Usuários → Novo usuário**: cadastrar 1 docente e 2 discentes (com RGM) | Contas criadas com senha temporária |
| 2 | Docente | Entrar com a senha temporária | Pede a troca da senha e depois o aceite dos termos |
| 3 | Docente | **Turmas → Nova turma** e matricular os 2 discentes | Turma ativa com 2 matrículas |
| 4 | Docente | **Trilhas** e **Atividades**: criar uma trilha publicada com uma atividade prática (código inicial e casos de teste) | Atividade visível para os alunos da turma |
| 5 | Discente | **Minhas trilhas**: abrir a atividade, rodar o código no editor, testar os casos e entregar | Entrega registrada |
| 6 | Discente | Na atividade, usar **Preciso de ajuda** | Dica de nível 1; os níveis seguintes liberam em ordem |
| 7 | Docente | **Atividades → Corrigir**: pedir a análise da IA, revisar e publicar a nota | Com chave do Gemini: resumo e pontos de atenção. Sem chave: aviso de IA indisponível |
| 8 | Docente | **Chamadas → Abrir chamada** com QR de 15 s e **Abrir projeção** | Projeção com QR, código e contador |
| 9 | Discente | Abrir `http://127.0.0.1:8000/chamada/p/<código>/` (ou digitar o código em **Confirmar presença**) e confirmar | "Presença registrada"; o contador e a lista do docente atualizam |
| 10 | Docente | Esperar o QR expirar, **Renovar QR** e depois **Finalizar chamada** | Código novo na renovação; lista de faltas ao finalizar |
| 11 | Docente e discente | **Comunicação**: publicar um aviso, comentar e anexar um arquivo | Aviso, comentário e notificação no sino |
| 12 | Docente | **Painel**: ver os indicadores e ajustar o limite de atenção da turma | Alunos abaixo do limite destacados |
| 13 | Discente | **Painel**: ver a própria evolução | Frequência, entregas e progresso apenas do próprio aluno |
| 14 | Coordenação | **Auditoria**: filtrar e exportar em CSV | Registros de login, aceite dos termos e ações |
| 15 | Qualquer | **Esqueci minha senha** na tela de login | Link de recuperação no terminal (ou por e-mail, com Mailgun) |

> A leitura do QR pelo **celular** e a conferência de localização exigem o sistema publicado com HTTPS. Em `127.0.0.1`, o celular não alcança o computador e o navegador bloqueia o GPS.

---

## 6. Regras de negócio

### 6.1 Cadastro e primeiro acesso

- A Coordenação cadastra docentes e discentes em `/contas/usuarios/`. O cadastro exige nome, sobrenome, usuário, e-mail, perfil e senha temporária; o RGM é obrigatório para discentes. As contas criadas não recebem privilégios administrativos.
- A Coordenação informa as credenciais por um canal privado. No primeiro acesso, a pessoa troca a senha temporária por uma pessoal, e a temporária deixa de funcionar. A recuperação de senha por e-mail também permite definir a senha pessoal.
- Depois da troca, a pessoa lê e aceita os termos de uso em `/contas/primeiro-acesso/`. O aceite registra usuário, versão, data, hora e IP, e gera registro na auditoria. Uma nova versão dos termos exige novo aceite.
- Até a troca da senha e o aceite, o sistema bloqueia todas as páginas, inclusive URLs diretas e envios de formulário, também em sessões já abertas.
- O docente é responsável pelas matrículas das próprias turmas.

### 6.2 Limite de atenção da turma

- O docente define o **limite de atenção (%)** ao criar a turma (padrão 60%) e pode alterá-lo em **Turmas → Configurar turma**. O valor vai de 0 a 100, com uma casa decimal, e só o docente responsável pode alterá-lo.
- O painel destaca os indicadores abaixo do limite; um valor igual ao limite não gera alerta. O limite não altera notas e não é um diagnóstico automático.

### 6.3 Chamada por QR code

- O docente abre a chamada escolhendo a turma, o tempo do QR (15, 30, 45 ou 60 s) e o limite de presenças (automático, igual aos alunos com matrícula ativa, ou personalizado).
- Quando o tempo acaba, a chamada fecha e só reabre se o docente renovar, o que gera um código novo. Ao finalizar, o sistema mostra as faltas.
- O aluno tem **3 minutos** entre ler o QR e confirmar. A leitura feita antes do login não se perde.
- **Presença recusada** (não é gravada): tempo de confirmação esgotado, chamada finalizada, matrícula inativa, presença repetida ou limite atingido.
- **Presença em análise** (é gravada e o docente aceita ou recusa): mesmo celular de outro aluno, localização negada, imprecisa ou fora do raio da instituição.
- O sistema guarda só a **distância** até a instituição, nunca as coordenadas do aluno. A instituição e as suas coordenadas são cadastradas pela Coordenação no `/admin`.
- Os painéis contam apenas as presenças **confirmadas**.

### 6.4 Entregas e IA

- A análise do Gemini é **consultiva**: o resumo e os pontos de atenção só chegam ao aluno depois da validação do docente, que define a nota.
- A ajuda da IA ao aluno nunca entrega a solução. Ela tem limite de pedidos por dia e intervalo entre pedidos, e o docente pode desligá-la por atividade (por exemplo, em provas) e escolher até qual nível de dica liberar.
- Falhas de comunicação com o Gemini ou o Mailgun são registradas em log e não interrompem o restante do sistema.

### 6.5 Arquivos enviados

Materiais, entregas e anexos da Comunicação passam pela mesma validação no servidor: até 5 arquivos por envio e 10 MB por arquivo.

- **Imagens** (PNG, JPEG, GIF, WebP) são reconstruídas sem metadados, com limites de pixels e de quadros.
- **PDFs** são lidos em modo estrito; arquivos corrompidos, protegidos por senha, com JavaScript, ações perigosas ou anexos internos são recusados.
- **DOCX, XLSX e PPTX** têm o conteúdo inspecionado; macros, ActiveX, arquivos embutidos e conexões externas são recusados.
- Os arquivos são salvos com nome aleatório, com tamanho e SHA-256 registrados, e só são baixados por quem tem permissão.

Essa validação é uma defesa em camadas e não substitui um antivírus. Referências: [OWASP — File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [Pillow](https://pillow.readthedocs.io/en/stable/reference/Image.html), [pypdf](https://pypdf.readthedocs.io/en/stable/user/robustness.html) e [defusedxml](https://pypi.org/project/defusedxml/).

---

## 7. Testes e qualidade

**E-mails automáticos (RF33):** depois de atualizar, execute `python manage.py migrate`.
O aluno é avisado após salvar a avaliação oficial; revisões que alteram a nota ou o
feedback também geram aviso. Para acompanhar alunos em atenção e reprocessar envios
pendentes, mantenha em outro terminal:

```bash
python manage.py notificar_acompanhamento --intervalo 60
```

Esse processo precisa continuar em execução. Em produção, use um worker supervisionado
ou agende `python manage.py notificar_acompanhamento` periodicamente, sem `--intervalo`.
Abrir o painel não dispara e-mails. O envio usa `EMAIL_BACKEND`; no modo console, a
mensagem aparece no terminal e não chega a uma caixa postal. Para links nos avisos,
configure `SIMAP_PUBLIC_URL` com o endereço do sistema.
Veja [regras e verificação do RF33](docs/RF33_NOTIFICACOES.md).

Os testes usam um banco SQLite em memória, criado do zero e descartado no fim. Não precisam de `.env` nem de PostgreSQL:

```bash
python manage.py test --settings=SIMAP.settings_test                       # todos
python manage.py test --settings=SIMAP.settings_test --tipo unitarios      # só regras, sem banco
python manage.py test --settings=SIMAP.settings_test --tipo integracao     # views, formulários e fluxos
```

O resultado esperado é `OK`, sem falhas.

**Linter (Ruff):** as regras estão em `ruff.toml`.

```bash
pip install -r requirements-dev.txt
ruff check .
```

**Integração contínua:** a cada Pull Request para a `main`, o GitHub Actions (`.github/workflows/ci.yml`) roda em paralelo os testes unitários, os testes de integração (incluindo a checagem de migrations pendentes) e o linter.

---

## 8. Segurança e LGPD

- **Senhas:** hash PBKDF2 com salt; mínimo de 10 caracteres, validadas contra senhas comuns, numéricas e parecidas com os dados do usuário.
- **Sessão:** expira após 8 horas de inatividade e ao fechar o navegador; logout apenas por POST.
- **Proteções do Django:** CSRF em todos os formulários, consultas parametrizadas pelo ORM (contra SQL Injection) e escape automático nos templates (contra XSS).
- **Autorização:** cada tela confere o perfil, e as consultas são sempre filtradas pelo usuário dono dos dados, para que ninguém acesse turmas, entregas ou chamadas de outra pessoa.
- **Credenciais:** chaves de API e senhas ficam em variáveis de ambiente, fora do repositório.
- **Produção:** com `DEBUG=False`, o sistema exige HTTPS, cookies seguros e HSTS.
- **LGPD:** o sistema trata dados de identificação institucional e de desempenho acadêmico, sem dados sensíveis. Aplica o princípio da minimização (a chamada não guarda a localização do aluno; a auditoria não copia o texto das mensagens). O aluno vê apenas os próprios dados, e o docente, apenas os das suas turmas. Os termos de uso e a política de privacidade ficam acessíveis no sistema.

---

## 9. Problemas comuns

| Erro | Causa | Solução |
|---|---|---|
| `ImproperlyConfigured: Set the SECRET_KEY environment variable` | falta o `.env` | [passo 4.3](#43-configuração-do-env) |
| `ModuleNotFoundError` (ex.: `defusedxml`, `google.genai`) | dependências desatualizadas depois de um `git pull` | `pip install -r requirements.txt` |
| `could not connect to server` | PostgreSQL desligado ou `DATABASE_URL` errada | ligar o serviço ou usar `sqlite:///db.sqlite3` |
| `IntegrityError` ao rodar `migrate` num banco antigo | dados de versões anteriores do sistema | criar um banco novo e rodar `migrate` nele |
| `Bad Request (400)` | endereço fora do `ALLOWED_HOSTS` | incluir o endereço no `.env` |
| Tabela ou coluna inexistente | migrations não aplicadas depois de atualizar | `python manage.py migrate` |

---

## 10. Documentação complementar

| Documento | Conteúdo |
|---|---|
| [docs/INTEGRACAO_API.md](docs/INTEGRACAO_API.md) | Integrações com o Google Gemini e o Mailgun: fluxo, autenticação, tratamento de falhas e dados enviados |
| [docs/AJUDA_IA_ALUNO.md](docs/AJUDA_IA_ALUNO.md) | Ajuda da IA ao aluno: níveis de dica, limites e configuração pelo docente |
| [docs/EDITOR_DE_CODIGO.md](docs/EDITOR_DE_CODIGO.md) | Editor de código das atividades práticas e execução segura no navegador |
| [docs/TRILHAS_MATERIAIS.md](docs/TRILHAS_MATERIAIS.md) | Materiais de apoio, vídeos, entregas com arquivo e notificações |
| [docs/COMUNICACAO.md](docs/COMUNICACAO.md) | Comunicação entre docente e discente, segurança dos anexos e privacidade |
| [SIMAP_BPMN_Diagram.bpmn](SIMAP_BPMN_Diagram.bpmn) | Diagrama BPMN dos processos do sistema |

---

## 11. Estrutura do projeto

Arquivos locais como `.env`, banco SQLite, ambiente virtual e a pasta de arquivos enviados (`media/`) não fazem parte do repositório.

```text
SIMAP/
├── SIMAP/                  # Configuração do projeto
│   ├── settings.py         # Configurações, lidas das variáveis de ambiente
│   ├── settings_test.py    # Configurações dos testes (banco em memória)
│   ├── test_runner.py      # Separação entre testes unitários e de integração
│   ├── urls.py             # Rotas principais
│   └── asgi.py / wsgi.py   # Pontos de entrada do servidor
│
├── usuarios/               # Contas, perfis, primeiro acesso, termos de uso, e-mail (Mailgun)
├── turmas/                 # Turmas, matrículas, instituição, limite de atenção
├── core/                   # Trilhas, atividades, materiais, vídeos, home por perfil
│   └── management/         # Comandos popular_dados e notificar_prazos
├── entregas/               # Submissões, editor de código, análise pelo Gemini
├── tutoria/                # Ajuda da IA ao aluno
├── chamada/                # Chamada por QR code e registro de presença
├── comunicacao/            # Avisos, comentários, mensagens, anexos e notificações
├── painel/                 # Painéis de desempenho do docente e do discente
├── auditoria/              # Registro de ações, exportação CSV e retenção
│   └── management/         # Comando limpar_auditoria
│
├── templates/              # Telas (HTML) organizadas por app, mais o layout base
├── static/                 # CSS e JavaScript (editor, gráficos, tutoria)
├── docs/                   # Documentação complementar
│
├── .github/workflows/      # Integração contínua (testes e linter)
├── .env.example            # Modelo das variáveis de ambiente (sem valores reais)
├── requirements.txt        # Dependências do sistema
├── requirements-dev.txt    # Ferramentas de desenvolvimento (Ruff)
├── ruff.toml               # Regras do linter
├── SIMAP_BPMN_Diagram.bpmn # Diagrama BPMN
├── manage.py               # Utilitário de linha de comando do Django
└── LICENSE
```

Cada app segue a organização padrão do Django: `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, `migrations/` e os arquivos de teste (`tests.py` e `test_*.py`). Os apps com regras maiores têm também `servicos.py`.
