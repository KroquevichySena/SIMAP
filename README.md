# SIMAP — Sistema de Monitoramento da Aprendizagem em Programação

Plataforma web para disciplinas introdutórias de programação. Centraliza a gestão de turmas, o registro de presença, as trilhas de aprendizagem com atividades teóricas e práticas, a análise das entregas com apoio de IA, a comunicação entre docente e discente e os painéis de desempenho de cada perfil.

Projeto Final de Curso — Engenharia de Software, Universidade de Mogi das Cruzes (UMC).

---

## Acompanhamento do PFC (entrega de 23/11/2026)

### Etapa de 09/11

| Exigência | Situação |
|---|---|
| Diagrama de classes e BPMN | Entregues na monografia; em atualização para refletir o sistema atual |
| Integração ou consumo de API | Cumprido: Google Gemini (correção e ajuda ao aluno) e Mailgun (e-mail) |
| Formulários com validação | Cumprido |
| Pelo menos 75% dos casos de uso, com front-end e back-end integrados | Cumprido |
| Documentação das regras de negócio | Cumprido na pasta `docs/`; ampliada neste README em 14/11 (seção 6) |
| Validação pelo orientador | Não houve apontamentos nem validação registrada na entrega de 09/11 |

### Desenvolvido desde 09/11

| PR | Entrega |
|---|---|
| #21, #22 | Identidade visual do SIMAP aplicada a todas as telas |
| #23 | Cadastro de usuários pela Coordenação e primeiro acesso |
| #24 | Validação de segurança dos arquivos enviados |
| #25, #26 | Chamada por QR code com ciclo, renovação, identificação de aparelho e localização |
| #27 | Painel como página inicial de docentes e discentes |
| #28 | Integração contínua no GitHub Actions (testes e Ruff a cada PR) |
| #20, #29, #30 | Ajuda da IA ao aluno durante as atividades |
| #31 | Senha temporária com troca obrigatória e limite de atenção por turma |
| #32 | README com instruções de execução e roteiro de verificação |
| #33 | Termos de uso 1.3 (LGPD), com novo aceite de todos os usuários |
| #34 | Páginas de erro 403, 404 e 500 |
| #35 | Variáveis do Gunicorn documentadas no `.env.example` |
| #36 | Relatório de acompanhamento da entrega de 16/11 neste README |
| #37 | Cobertura dos testes unitários medida no CI, com mínimo de 50% |
| #38, #39 | Perfil próprio da Coordenação, e-mails automáticos de acompanhamento (RF33), dados de demonstração e ajustes nas notificações |
| #40 | Ajustes finais nos nomes fictícios e na ajuda da senha |

Na entrega de 16/11: verificação ponta a ponta dos três perfis em 15/11 (35 fluxos e 58 telas, sem erros).

### Desenvolvido após 16/11, com autorização do orientador

| PR | Entrega |
|---|---|
| #41 | Manual do usuário com as telas dos três perfis ([docs/MANUAL_DO_USUARIO.md](docs/MANUAL_DO_USUARIO.md)) |
| #42 | Cadastro de instituições pela Coordenação e vínculo com as turmas |
| #43 | Correção da chamada no PostgreSQL, otimização do painel do docente e implantação em contêiner (Docker e Gunicorn) |
| #44 | Testes unitários dos serviços principais |
| #45 | Login por link de outro perfil leva ao painel, sem aviso de erro |
| #46 | E-mail e RGM mascarados nas listagens administrativas |
| #47 | Versões dos termos de uso publicadas pela Coordenação, com reaceite imediato |
| #48 | Manual do usuário atualizado com instituições, versões dos termos e máscara de dados |
| #49, #50 | Agendamento dos e-mails do RF33 pelo GitHub Actions |

Situação atual: 608 testes automatizados passando (11 deles só rodam no PostgreSQL) e análise estática sem alertas. O sistema está publicado no Render, com o banco no Neon (PostgreSQL 16).

### Pendências

| Item | Prazo | Situação |
|---|---|---|
| Testes unitários com cobertura mínima de 50% (coverage.py) | 23/11 | Concluído: cobertura medida no CI a cada PR (#37), com testes unitários adicionais dos serviços principais (#44) |
| Manual do sistema (apêndice da monografia) | 23/11 | Concluído (#41) e atualizado com as telas das entregas #42 a #47 (#48) |
| Implantação em contêiner (Docker, Gunicorn, Render) | 23/11 | Concluído: Docker e Gunicorn (#43) e sistema publicado no Render |
| Migração da correção por IA para o pacote `google-genai` | 23/11 | Pendente: a ajuda ao aluno já usa `google-genai`; a análise das entregas (`entregas/ia_services.py`) ainda usa o pacote anterior |
| Agendamento automático do RF33 (GitHub Actions) | 23/11 | Em verificação: as execuções manuais funcionam e enviam os e-mails, mas o disparo automático pelo cron ainda não ocorreu |

Verificado no ambiente publicado em 23/11: ajuda da IA (Gemini) e e-mails pelo Mailgun sandbox (recuperação de senha, feedback e alerta de atenção). Ainda não verificada: a chamada por QR no celular com localização.

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
| **Coordenação** | Perfil próprio `COORDENACAO`, separado de docente e discente | Cadastra docentes, discentes e instituições, publica as versões dos termos de uso e consulta a auditoria |
| **Docente** | Professor da disciplina | Cria turmas, matrículas, trilhas e atividades; faz a chamada; corrige as entregas; acompanha o painel da turma |
| **Discente** | Aluno matriculado | Realiza as atividades, confirma presença, pede ajuda à IA e acompanha a própria evolução |

---

## 2. Funcionalidades

| Módulo | O que o sistema faz |
|---|---|
| **Acesso** | Login, cadastro de usuários pela Coordenação com senha temporária, troca obrigatória da senha no primeiro acesso, versões dos termos de uso publicadas pela Coordenação com aceite obrigatório, recuperação de senha por e-mail |
| **Turmas** | Criação de turmas, matrículas, alteração da situação da matrícula, limite de atenção da turma, instituição da turma cadastrada pela Coordenação |
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

A conta criada pelo `createsuperuser` recebe o perfil **Coordenação** automaticamente.
Ela não acessa as funções de docente ou discente. No primeiro login, aceita os termos
de uso e passa a ver os menus **Usuários**, onde cadastra docentes e discentes,
**Instituições** e **Termos de uso**.
Esse formulário não cria outras contas de coordenação nem permite elevar privilégios.

Na listagem de Usuários, o e-mail e o RGM aparecem mascarados (por exemplo,
`an***@umc.br` e `***2733`); a busca aceita o dado completo, e a tela de confirmação
de cada ação mostra o dado inteiro para conferência. A coordenação pode **desativar**, **reativar** ou solicitar
a **exclusão** de uma conta acadêmica, sempre com confirmação e POST protegido por
CSRF. Desativar bloqueia o login e as sessões na próxima requisição, preservando
senha, vínculos e histórico. Reativar não altera a situação das matrículas.
A exclusão definitiva pela tela do SIMAP só é permitida para contas que nunca
entraram e não possuem vínculos ou registros que seriam removidos (incluindo
aceites dos termos). Contas com histórico devem ser desativadas. Registros de
auditoria são preservados. Contas da coordenação e contas com flags administrativas
não podem ser removidas nem desativadas por essa tela.

O Admin exibe os três perfis. Para entrar nele, a conta precisa do perfil Coordenação
e também das permissões técnicas do Django (`is_staff` e permissões, ou superusuário).
Somente escolher um perfil não concede automaticamente privilégios de superusuário.
Uma conta com perfil docente ou discente não acessa o Admin, mesmo com flags indevidas.

Ao atualizar, execute `python manage.py migrate`. A migração `usuarios.0004` converte
as contas superusuárias antigas que não sejam discentes para o perfil Coordenação.
Senhas, aceites e vínculos são preservados. Se uma dessas contas era responsável por
turmas, transfira-as para um docente em **Admin → Turmas → Docente**. Enquanto isso,
os dados continuam preservados no Admin, mas a coordenação não atua como professor.

**Dados de demonstração (opcional).** O comando abaixo cria coordenação, docente,
alunos, uma turma e trilhas com atividades fictícias. Os usuários têm prefixo `demo.`,
RGMs `DEMO-` e e-mails reservados `@example.test`. Ele se recusa a rodar em produção:

```bash
python manage.py popular_dados
python manage.py popular_dados --limpar   # recria somente a turma DEMO; preserva contas e senhas
```

A senha temporária exclusiva do cenário está na constante `SENHA_PADRAO` do comando
(somente desenvolvimento); ela não é impressa no resumo. Troque-a no primeiro
acesso. Contas existentes mantêm suas senhas ao repetir o comando. Use um banco
separado para a apresentação e nunca inclua senhas, QR codes, tokens ou dados
pessoais reais nas evidências. A limpeza é recusada se a turma DEMO contiver dados
de outras contas. Dados antigos criados por versões anteriores não são apagados.

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
| `python manage.py notificar_acompanhamento` | Envia os e-mails automáticos de acompanhamento (RF33) e reprocessa os pendentes (`--intervalo 60` mantém o processo rodando) |

**E-mails automáticos (RF33):** depois de atualizar, execute `python manage.py migrate`.
O aluno é avisado após salvar a avaliação oficial; revisões que alteram a nota ou o
feedback também geram aviso. Para acompanhar alunos em atenção e reprocessar envios
pendentes, mantenha em outro terminal:

```bash
python manage.py notificar_acompanhamento --intervalo 60
```

Esse processo precisa continuar em execução. Em produção, o comando é agendado pelo
GitHub Actions (workflow **RF33 - alertas por e-mail**, nos minutos 17 e 47 de cada hora,
em UTC), que acessa o mesmo banco do site e envia pelo Mailgun. O workflow também pode ser
executado manualmente em **Actions → RF33 - alertas por e-mail → Run workflow**.
Abrir o painel não dispara e-mails. O envio usa `EMAIL_BACKEND`; no modo console, a
mensagem aparece no terminal e não chega a uma caixa postal. Para links nos avisos,
configure `SIMAP_PUBLIC_URL` com o endereço do sistema.
Veja [regras e verificação do RF33](docs/RF33_NOTIFICACOES.md).

### 4.7 Publicação

O sistema está publicado em <https://simap.onrender.com>. A aplicação roda no **Render**,
pela imagem do `Dockerfile` (Gunicorn), e o banco fica no **Neon** (PostgreSQL 16), os dois
na mesma região (Virginia, EUA). A proximidade importa: cada página faz várias consultas,
e a distância entre aplicação e banco multiplica o tempo de resposta.

- Configure as variáveis de produção no painel do Render, nunca no repositório: `SECRET_KEY`,
  `DATABASE_URL` (com `?sslmode=require`), `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
  `SECURE_SSL_REDIRECT=True`, `SIMAP_PUBLIC_URL` e as chaves das integrações.
- **As migrations rodam em cada publicação**: com `RUN_MIGRATIONS=1` no Render, o contêiner executa
  `python manage.py migrate` antes de iniciar o Gunicorn. Se uma migration falhar, a publicação não
  sobe e o Render mantém a versão anterior no ar. Isso é seguro enquanto houver uma única instância;
  com mais de uma, as migrations devem rodar uma vez só, antes da publicação. Veja [docs/DOCKER.md](docs/DOCKER.md).
- O Gunicorn usa os padrões da imagem: um worker, duas threads e tempo limite de 120 segundos
  (`WEB_CONCURRENCY`, `GUNICORN_THREADS` e `GUNICORN_TIMEOUT` mudam esses valores).
- Os e-mails usam o Mailgun em modo **sandbox**: só destinatários autorizados no Mailgun recebem.
  Recuperação de senha, feedback e alerta de atenção foram validados nessas caixas.
- No plano gratuito, o serviço hiberna após 15 minutos sem acesso (o primeiro acesso seguinte
  leva cerca de um minuto) e os arquivos enviados não são preservados entre publicações.

---

## 5. Roteiro de verificação

Siga na ordem, porque cada etapa usa os dados da anterior. Para usar dois perfis ao mesmo tempo, abra uma janela anônima para o segundo.

| # | Perfil | O que fazer | Resultado esperado |
|---|---|---|---|
| 1 | Coordenação | **Usuários → Cadastrar usuário**: cadastrar 1 docente e 2 discentes (com RGM) | Contas criadas com senha temporária |
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
| 12 | Docente | **Painel**: ver os indicadores; em **Turmas → Configurar turma**, ajustar o limite de atenção | Alunos abaixo do limite destacados |
| 13 | Discente | **Painel**: ver a própria evolução | Frequência, entregas e progresso apenas do próprio aluno |
| 14 | Coordenação | **Auditoria**: filtrar e exportar em CSV | Registros de login, aceite dos termos e ações |
| 15 | Qualquer | **Esqueci minha senha** na tela de login | Link de recuperação no terminal (ou por e-mail, com Mailgun) |
| 16 | Coordenação | **Instituições**: cadastrar a instituição com as coordenadas e vincular a turma | Turma ligada à instituição usada na conferência de localização da chamada |
| 17 | Coordenação | **Termos de uso → Nova versão**: pré-visualizar e publicar a versão seguinte | Quem estiver com o sistema aberto é bloqueado em alguns segundos e precisa aceitar a nova versão para continuar |

> A leitura do QR pelo **celular** e a conferência de localização exigem o sistema publicado com HTTPS. Em `127.0.0.1`, o celular não alcança o computador e o navegador bloqueia o GPS.

---

## 6. Regras de negócio

### 6.1 Cadastro e primeiro acesso

- A Coordenação cadastra docentes e discentes em `/contas/usuarios/`. O cadastro exige nome, sobrenome, usuário, e-mail, perfil e senha temporária; o RGM é obrigatório para discentes. As contas criadas não recebem privilégios administrativos.
- A Coordenação informa as credenciais por um canal privado. No primeiro acesso, a pessoa troca a senha temporária por uma pessoal, e a temporária deixa de funcionar. A recuperação de senha por e-mail também permite definir a senha pessoal.
- Depois da troca, a pessoa lê e aceita os termos de uso em `/contas/primeiro-acesso/`. O aceite registra usuário, versão, data, hora e IP, e gera registro na auditoria. Uma nova versão dos termos exige novo aceite.
- A Coordenação publica as versões dos termos em **Termos de uso**, com pré-visualização e confirmação. A versão vigente é sempre a última publicada; uma versão publicada não pode ser alterada nem apagada, e o histórico mostra quantas contas aceitaram cada uma. A versão 1.3 foi cadastrada por migração com o mesmo texto que estava no sistema.
- Ao ser publicada uma nova versão, as páginas abertas consultam a versão vigente a cada 15 segundos e bloqueiam a tela até o novo aceite, mostrando o que mudou. Essa consulta não renova a sessão nem gera registro na auditoria; o servidor continua recusando qualquer requisição sem o aceite.
- Se a pessoa entra por um link de tela de outro perfil (por exemplo, um docente pelo link de confirmação de presença), o login a leva para o próprio painel.
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
- O sistema guarda só a **distância** até a instituição, nunca as coordenadas do aluno. A Coordenação cadastra a instituição e as suas coordenadas em **Instituições** e a vincula às turmas.
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

Os testes usam um banco SQLite em memória, criado do zero e descartado no fim. Não precisam de `.env` nem de PostgreSQL:

```bash
python manage.py test --settings=SIMAP.settings_test                       # todos
python manage.py test --settings=SIMAP.settings_test --tipo unitarios      # só regras, sem banco
python manage.py test --settings=SIMAP.settings_test --tipo integracao     # views, formulários e fluxos
```

O resultado esperado é `OK`, sem falhas.

**Testes no PostgreSQL:** alguns comportamentos, como o bloqueio de concorrência da chamada, só podem ser verificados num PostgreSQL real; esses testes são pulados no SQLite. Com um PostgreSQL 16 local (ou só para testes), rode:

```bash
python manage.py test --settings=SIMAP.settings_test_postgres
```

A conexão usa `127.0.0.1:5432` e o usuário `postgres`; para mudar, defina `SIMAP_TEST_POSTGRES_HOST`, `SIMAP_TEST_POSTGRES_PORT`, `SIMAP_TEST_POSTGRES_USER` e `SIMAP_TEST_POSTGRES_PASSWORD`. O banco de testes é criado e apagado a cada execução e nunca é o banco publicado.

**Linter (Ruff):** as regras estão em `ruff.toml`.

```bash
pip install -r requirements-dev.txt
ruff check .
```

**Cobertura de testes:** as regras estão em `.coveragerc`. O mínimo exigido é 50% nos testes unitários.

```bash
pip install -r requirements-dev.txt
coverage run manage.py test --settings=SIMAP.settings_test --tipo unitarios
coverage report
```

**Integração contínua:** a cada Pull Request para a `main`, o GitHub Actions (`.github/workflows/ci.yml`) roda em paralelo os testes unitários com a medição de cobertura, os testes de integração (incluindo a checagem de migrations pendentes), o linter, a regressão da chamada, do login e do painel num PostgreSQL 16 e a construção da imagem Docker. O PR falha se a cobertura dos testes unitários ficar abaixo de 50%.

---

## 8. Segurança e LGPD

- **Senhas:** hash PBKDF2 com salt; mínimo de 10 caracteres, validadas contra senhas comuns, numéricas e parecidas com os dados do usuário.
- **Sessão:** expira após 8 horas de inatividade e ao fechar o navegador; logout apenas por POST.
- **Proteções do Django:** CSRF em todos os formulários, consultas parametrizadas pelo ORM (contra SQL Injection) e escape automático nos templates (contra XSS).
- **Autorização:** cada tela confere o perfil, e as consultas são sempre filtradas pelo usuário dono dos dados, para que ninguém acesse turmas, entregas ou chamadas de outra pessoa.
- **Credenciais:** chaves de API e senhas ficam em variáveis de ambiente, fora do repositório.
- **Produção:** com `DEBUG=False`, o sistema exige HTTPS, cookies seguros e HSTS.
- **LGPD:** o sistema trata dados de identificação institucional e de desempenho acadêmico, sem dados sensíveis. Aplica o princípio da minimização (a chamada não guarda a localização do aluno; a auditoria não copia o texto das mensagens). O aluno vê apenas os próprios dados, e o docente, apenas os das suas turmas. Nas listagens administrativas, o e-mail e o RGM aparecem mascarados. Os termos de uso e a política de privacidade ficam acessíveis no sistema; cada versão publicada é guardada com o texto integral, e cada aceite registra a versão, a data, a hora e o IP, o que permite comprovar o que cada pessoa aceitou.

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
| [docs/MANUAL_DO_USUARIO.md](docs/MANUAL_DO_USUARIO.md) | Manual do usuário, com as telas dos três perfis |
| [docs/DOCKER.md](docs/DOCKER.md) | Imagem Docker, Gunicorn e variáveis de execução |
| [docs/RF33_NOTIFICACOES.md](docs/RF33_NOTIFICACOES.md) | Regras e verificação dos e-mails automáticos de acompanhamento |
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
│   ├── settings_test_postgres.py  # Testes num PostgreSQL real
│   ├── test_runner.py      # Separação entre testes unitários e de integração
│   ├── urls.py             # Rotas principais
│   └── asgi.py / wsgi.py   # Pontos de entrada do servidor
│
├── usuarios/               # Contas, perfis, primeiro acesso, versões dos termos de uso, e-mail (Mailgun)
├── turmas/                 # Turmas, matrículas, instituição, limite de atenção
├── core/                   # Trilhas, atividades, materiais, vídeos, home por perfil
│   └── management/         # Comandos popular_dados e notificar_prazos
├── entregas/               # Submissões, editor de código, análise pelo Gemini
├── tutoria/                # Ajuda da IA ao aluno
├── chamada/                # Chamada por QR code e registro de presença
├── comunicacao/            # Avisos, comentários, mensagens, anexos e notificações
│   └── management/         # Comando notificar_acompanhamento (RF33)
├── painel/                 # Painéis de desempenho do docente e do discente
├── auditoria/              # Registro de ações, exportação CSV e retenção
│   └── management/         # Comando limpar_auditoria
│
├── templates/              # Telas (HTML) organizadas por app, mais o layout base
├── static/                 # CSS e JavaScript (editor, gráficos, tutoria)
├── docs/                   # Documentação complementar e manual do usuário
├── docker/                 # Script de início do contêiner
│
├── .github/workflows/      # Integração contínua (testes e linter)
├── .env.example            # Modelo das variáveis de ambiente (sem valores reais)
├── requirements.txt        # Dependências do sistema
├── requirements-dev.txt    # Ferramentas de desenvolvimento (Ruff e coverage)
├── requirements.docker.txt # Dependências da imagem Docker (inclui o Gunicorn)
├── Dockerfile, compose.yaml # Imagem do sistema e ambiente local em contêiner
├── .coveragerc             # Regras da medição de cobertura
├── ruff.toml               # Regras do linter
├── SIMAP_BPMN_Diagram.bpmn # Diagrama BPMN
├── manage.py               # Utilitário de linha de comando do Django
└── LICENSE
```

Cada app segue a organização padrão do Django: `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, `migrations/` e os arquivos de teste (`tests.py` e `test_*.py`). Os apps com regras maiores têm também `servicos.py`.
