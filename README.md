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
SIMAP/
├── core/                  # App principal (Regras de negócio, views e models)
│   ├── migrations/        # Histórico de alterações do banco de dados
│   ├── __init__.py
│   ├── admin.py           # Configurações do painel administrativo
│   ├── apps.py            # Configuração do próprio app
│   ├── models.py          # Tabelas do banco de dados (Docente, Discente, Turma, etc.)
│   ├── tests.py           # Testes unitários (cobertura mínima de 50%)
│   └── views.py           # Funções que controlam o que aparece na tela
├── SIMAP/                 # Configurações globais do projeto
│   ├── __pycache__/
│   ├── __init__.py
│   ├── asgi.py            # Entry-point para servidores assíncronos
│   ├── settings.py        # Configurações centrais (Apps, banco, fuso horário)
│   ├── urls.py            # Roteamento global de URLs
│   └── wsgi.py            # Entry-point para servidores WSGI (Gunicorn)
├── venv/                  # Ambiente virtual (Ignorado no Git)
├── .gitignore             # Regras de exclusão do repositório
├── db.sqlite3             # Banco de dados local de desenvolvimento (Ignorado)
├── LICENSE                # Arquivo de licença 
├── manage.py              # Gerenciador de comandos do Django
├── README.md              # Este arquivo de documentação
└── requirements.txt       # Lista oficial de dependências e bibliotecas
```