# SIMAP - Sistema de Monitoramento da Aprendizagem em Programação

**Data do Setup Inicial:** 22 de Agosto de 2026

---

## 🚀 Como baixar e rodar o projeto localmente (Time)

Para garantir que não teremos conflitos de versão e mantermos o alinhamento com a arquitetura definida no PFC, sigam rigorosamente estes passos no terminal (PowerShell):

0. **Verifique a versão do Python:**
   O projeto exige o **Python 3.12**. Se você não tiver essa versão instalada, rode o comando abaixo no PowerShell para baixar automaticamente (pode ser necessário digitar 'Y' para aceitar os termos):
   ```bash
   winget install Python.Python.3.12
   ```
   *(Importante: Feche e abra o terminal novamente após a instalação para o Windows reconhecer o comando).*

1. **Clone o repositório para a sua máquina e entre na pasta:**
   ```bash
   git clone [https://github.com/KroquevichySena/SIMAP.git](https://github.com/KroquevichySena/SIMAP.git)
   cd SIMAP
   ```

2. **Crie o ambiente virtual forçando o Python 3.12:**
   ```bash
   py -3.12 -m venv venv
   ```

3. **Ative o ambiente virtual:**
   ```bash
   .\venv\Scripts\activate
   ```
   *(O prefixo `(venv)` deve aparecer no início da linha do seu terminal).*

4. **Instale as dependências cravadas do projeto (Django 5.2):**
   ```bash
   pip install -r requirements.txt
   ```

5. **Sincronize o banco de dados e ligue o servidor:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```
   *Acesse `http://127.0.0.1:8000/` no navegador para confirmar que está rodando.*

## Cadastro e primeiro acesso

A coordenação utiliza uma conta administrativa ativa (superusuário, sem perfil
discente). Após o login e o aceite dos termos, pode acessar **Usuários** no menu
para cadastrar docentes e discentes em `/contas/usuarios/`.

O cadastro exige nome, sobrenome, usuário de acesso, e-mail, perfil e senha
temporária; o RGM é obrigatório para discentes. As contas criadas nessa tela não
recebem privilégios administrativos. A coordenação informa as credenciais à
pessoa por um canal privado. No primeiro acesso, a pessoa precisa substituí-la
por uma senha diferente; a senha temporária deixa de funcionar. A redefinição
pelo e-mail cadastrado também permite definir essa senha pessoal. Senhas
definidas pela coordenação no Admin também exigem a troca por uma senha pessoal.
O professor continua responsável pelas matrículas nas próprias turmas.

O login pede apenas usuário e senha. Quem tem troca pendente é encaminhado para
`/contas/trocar-senha-temporaria/`, antes dos termos e das funcionalidades.
O bloqueio também vale para sessões existentes, URLs diretas e operações POST.
Depois da troca, quem ainda não aceitou a versão vigente é
encaminhado a `/contas/primeiro-acesso/`, onde lê os termos e confirma o próprio
aceite. Até isso acontecer, o sistema bloqueia também URLs diretas e operações.
O aceite registra usuário, versão, data/hora e IP e gera registro na auditoria.
Uma nova versão dos termos exige novo aceite, inclusive em sessões existentes.

Para criar a primeira conta de coordenação, use `python manage.py createsuperuser`.
Não atribua perfil DISCENTE à conta administrativa. Após atualizar, execute
`python manage.py migrate`: a migração `usuarios.0003` marca os docentes e
discentes já cadastrados para uma troca de senha única. Ela preserva as contas
da coordenação e os aceites existentes. A senha temporária não possui prazo
automático de expiração; a restrição é de acesso até sua substituição.

## Limite de atenção da turma

O docente define o **Limite de atenção (%)** ao criar a turma (padrão: 60%) e
pode alterá-lo em **Turmas → Configurar turma**. A tela de alunos e o painel
também têm links para essa configuração. O servidor só permite a alteração
pelo docente responsável, aceita de 0 a 100 com uma casa decimal e mantém o
valor anterior se o envio for inválido.

O painel usa o limite para sinalizar indicadores calculáveis abaixo do percentual;
um valor igual ao limite não gera alerta. A configuração não modifica notas e
não é um diagnóstico automático de dificuldade. O campo já existia no modelo
da turma, portanto essa parte não exige migração adicional.

## Validação dos arquivos enviados

Materiais de trilhas/atividades, entregas e Comunicação compartilham a mesma
validação no servidor: até 5 arquivos por envio e 10 MB por arquivo. Depois de
atualizar o código, instale as dependências com `pip install -r requirements.txt`.
Não há novas migrações para esta alteração.

- Imagens PNG, JPEG, GIF e WebP são decodificadas e reconstruídas com Pillow,
  sem metadados e sem conteúdo acrescentado ao final. Limites: 20 milhões de
  pixels por quadro, 100 quadros e 40 milhões de pixels acumulados por animação.
- PDFs são lidos com pypdf em modo estrito. Arquivos corrompidos, protegidos
  por senha, com JavaScript, ações perigosas ou anexos internos são recusados.
  Links HTTP/HTTPS e mailto e destinos internos normais continuam permitidos.
  Há limites de páginas, objetos e complexidade; não há renderização do PDF.
- DOCX, XLSX e PPTX têm o pacote, XML e relacionamentos inspecionados. Macros,
  ActiveX, arquivos embutidos, campos DDE, fórmulas de conexão externa e recursos
  externos automáticos são recusados. Links clicáveis comuns são permitidos.
  Imagens internas também são reconstruídas. Formatos internos não suportados,
  como imagens vetoriais e fontes embutidas, são recusados; nesse caso, exporte
  o material como PDF. O ZIP interno tem limites de 2000 partes e 100 MB abertos.
- Arquivos reconstruídos recebem tamanho e SHA-256 do conteúdo realmente salvo.
  Downloads continuam sujeitos à permissão de acesso, com nomes aleatórios no
  disco e cabeçalhos que restringem interpretação de conteúdo pelo navegador.

Isso é defesa em camadas, não uma garantia de ausência de malware nem um
antivírus. Arquivos antigos não são reprocessados automaticamente. Na implantação,
configure também limites de requisição, armazenamento e tráfego no servidor;
o diretório `media` não deve ser publicado diretamente.

Referências: [OWASP — File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html),
[Pillow — Image](https://pillow.readthedocs.io/en/stable/reference/Image.html),
[pypdf — leitura estrita](https://pypdf.readthedocs.io/en/stable/user/robustness.html)
e [defusedxml](https://pypi.org/project/defusedxml/).

## 🤖 Como Configurar a IA (Google Gemini)

Para que as funcionalidades de inteligência artificial do projeto funcionem perfeitamente na sua máquina local, é obrigatório configurar a chave de acesso da API:

1. Acesse o [Google AI Studio](https://aistudio.google.com/) e gere a sua API Key gratuita.
2. Na raiz do projeto, localize o arquivo chamado `.env.example`.   
3. Faça uma cópia deste arquivo e renomeie a cópia para `.env` (apenas `.env`, sem nome antes do ponto).
4. Abra o novo arquivo `.env` e adicione a sua chave colando o código gerado, ficando neste formato:
   ```env
   GEMINI_API_KEY=sua_chave_gerada_aqui
   ```

A documentação técnica das integrações com o Google Gemini e com o Mailgun (fluxo, endpoints, autenticação, tratamento de falhas, dados enviados e testes) está em [docs/INTEGRACAO_API.md](docs/INTEGRACAO_API.md).

---

## 🛠️ O que foi feito no Setup Inicial

A infraestrutura básica do projeto foi configurada com sucesso, englobando:
* Inicialização do projeto base utilizando **Python 3.12** e **Django 5.2 LTS**.
* Criação das configurações globais do sistema na raiz (`SIMAP`), com variáveis de ambiente (`wsgi`, `asgi` e `settings`) ajustadas para evitar erros de rotas.
* Criação do módulo principal da aplicação (`core`), já registrado no sistema e pronto para receber as regras de negócio, tabelas e visualizações.
* Realização da primeira migração nativa, gerando o arquivo `db.sqlite3` para testes locais de desenvolvimento.
* Configuração do `.gitignore` para bloquear o envio da pasta `venv`, arquivos de compilação de cache (`__pycache__`) e o banco de dados local.
* Exportação de todas as bibliotecas no arquivo `requirements.txt`.

---

## 📁 Árvore de Pastas do Projeto

Abaixo está a estrutura de diretórios atualizada do sistema:

```text
📁 SIMAP/
├── ✋ chamada/               # App de validação de presença
│   ├── 📂 migrations/        
│   ├── 🐍 __init__.py        
│   ├── 🛠️ admin.py           
│   ├── ⚙️ apps.py            
│   ├── 📝 forms.py           
│   ├── 📊 models.py          
│   ├── 🧪 tests.py           
│   ├── 🔗 urls.py            
│   └── 👁️ views.py           
│
├── 🧠 core/                  # App principal com lógicas centrais e mixins
│   ├── 📂 management/        
│   ├── 📂 migrations/        
│   ├── 🐍 __init__.py        
│   ├── 🛠️ admin.py           
│   ├── ⚙️ apps.py            
│   ├── 📝 forms.py           
│   ├── 🧩 mixins.py          
│   ├── 📊 models.py          
│   ├── 🧪 tests.py           
│   ├── 🔗 urls.py            
│   └── 👁️ views.py           
│
├── ⚙️ SIMAP/                 # Configurações globais do projeto
│   ├── 🐍 __init__.py        
│   ├── 🚀 asgi.py            
│   ├── 🛠️ settings.py        
│   ├── 🔗 urls.py            
│   └── 🚀 wsgi.py            
│
├── 🎨 templates/             # Diretório global de interfaces HTML
│   ├── 📂 chamada/           
│   ├── 📂 core/              
│   ├── 📂 partials/          
│   ├── 📂 teste/             
│   └── 🌐 base.html          
│
├── 🏫 turmas/                # App de gestão de turmas com templates isolados
│   ├── 📂 migrations/        
│   ├── 📂 templates/         
│   ├── 🐍 __init__.py        
│   ├── 🛠️ admin.py           
│   ├── ⚙️ apps.py            
│   ├── 📝 forms.py           
│   ├── 📊 models.py          
│   ├── 🧪 tests.py           
│   ├── 🔗 urls.py            
│   └── 👁️ views.py           
│
├── 👥 usuarios/              # App de gestão de perfis
│   ├── 📂 migrations/        
│   ├── 🐍 __init__.py        
│   ├── 🛠️ admin.py           
│   ├── ⚙️ apps.py            
│   ├── 📊 models.py          
│   ├── 🧪 tests.py           
│   └── 👁️ views.py           
│
├── 🔒 .env.example           # Exemplo de configuração de ambiente
├── 🚫 .gitignore             # Arquivo de exclusão do Git
├── ⚖️ LICENSE                # Licença do projeto
├── 🎮 manage.py              # Gestor principal do Django
├── 📖 README.md              # Documentação central
└── 📦 requirements.txt       # Dependências do projeto
```
