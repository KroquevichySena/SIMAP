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

## 🤖 Como Configurar a IA (Google Gemini)

Para que as funcionalidades de inteligência artificial do projeto funcionem perfeitamente na sua máquina local, é obrigatório configurar a chave de acesso da API:

1. Acesse o [Google AI Studio](https://aistudio.google.com/) e gere a sua API Key gratuita.
2. Na raiz do projeto, localize o arquivo chamado `.env.example`.   
3. Faça uma cópia deste arquivo e renomeie a cópia para `.env` (apenas `.env`, sem nome antes do ponto).
4. Abra o novo arquivo `.env` e adicione a sua chave colando o código gerado, ficando neste formato:
   ```env
   GEMINI_API_KEY=sua_chave_gerada_aqui

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