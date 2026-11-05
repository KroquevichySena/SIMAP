# Comunicação entre professor e alunos

O SIMAP tem um espaço de comunicação no formato de comentários, e não um chat em tempo real: alguém publica e os outros respondem. É mais simples de usar e de manter, e o professor consegue acompanhar tudo o que acontece na turma.

## O que dá para fazer

| Recurso | Onde fica | Quem vê |
|---|---|---|
| **Mural da turma** | Comunicação → turma | Professor e alunos com matrícula ativa |
| **Comentários da atividade** | Botão "Comentários" na atividade | Toda a turma (o aluno só vê se a atividade estiver publicada) |
| **Mensagem privada** | No mural, campo "Para" | Só o autor e o destinatário |
| **Respostas** | Dentro de cada publicação | Quem pode ver a publicação |
| **Notificações** | Sino na barra de navegação | Cada pessoa vê só as suas |

Regras de quem fala com quem:

- O professor manda mensagem privada para qualquer aluno da turma.
- O aluno manda mensagem privada só para o professor. Conversa privada entre alunos fica de fora de propósito, porque o professor não teria como moderar algo que não enxerga.
- Quem é de fora da turma recebe 404, como se a turma não existisse.
- Apaga uma publicação ou resposta quem escreveu ou o professor da turma.

Quem é notificado:

| Ação | Notificados |
|---|---|
| Professor publica no mural ou comenta numa atividade | Todos os alunos ativos da turma |
| Aluno publica no mural ou comenta numa atividade | O professor |
| Mensagem privada | O destinatário |
| Resposta | O autor da publicação, quem já respondeu e o professor (ou, numa privada, a outra pessoa) |

## Segurança dos anexos

A regra é **"só entra o que a gente conhece"**: existe uma lista curta de tipos permitidos, e todo o resto é recusado, inclusive o que ninguém lembrou de proibir.

| Categoria | Extensões |
|---|---|
| Documentos | .pdf, .docx, .xlsx, .pptx |
| Imagens | .png, .jpg, .jpeg, .gif, .webp |
| Texto | .txt, .md, .csv |
| Código-fonte | .py, .java, .c, .cpp, .h, .cs, .js, .ts, .html, .css, .sql, .json |

Limites: até **5 arquivos** por mensagem e **10 MB** por arquivo, configuráveis no `settings.py`.

Cada arquivo passa por estas conferências (`comunicacao/seguranca.py`):

1. **Extensão final.** `trabalho.pdf.bat` termina em `.bat` e é recusado. Executáveis, scripts e instaladores (`.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.msi`, `.lnk`, `.scr`…), arquivos compactados (`.zip`, `.rar`) e SVG nunca entram.
2. **Nome.** Caminhos (`../../`) e caracteres invisíveis são removidos. Isso inclui o caractere que inverte o texto, usado para disfarçar `fdp.exe` como `exe.pdf`.
3. **Conteúdo real.** Os primeiros bytes precisam bater com o tipo declarado. Um `.exe` renomeado para `.pdf` começa com `MZ`, e não com `%PDF`, então é recusado. Qualquer arquivo com assinatura de executável do Windows, Linux ou macOS é bloqueado, seja qual for o nome.
4. **Conteúdo ativo.**
   - São recusados PDFs com JavaScript, com arquivos embutidos ou com comandos para abrir programas.
   - São recusados documentos do Office com macro (`vbaProject.bin`), com ActiveX ou com objetos embutidos.
   - "Bombas zip" (documentos que explodem de tamanho ao abrir) também são barradas.
   - Arquivos de texto e de código não podem ter conteúdo binário.

Depois de aprovado:

- **Armazenamento.** O arquivo é salvo com um **nome aleatório** (UUID), numa pasta que o servidor **não** entrega direto. O nome original fica só no banco, para aparecer na tela, junto com o hash SHA-256.
- **Download.** Todo download passa por uma view que confere se a pessoa pode ver a mensagem. A resposta:
  - usa o tipo de conteúdo da nossa lista, e não o que o navegador de quem enviou informou;
  - força o download (só imagens abrem na tela);
  - traz `X-Content-Type-Options: nosniff` e uma `Content-Security-Policy` com `sandbox`, que bloqueia scripts.
- **Código-fonte** é baixado com `.txt` no fim (`exercicio.py.txt`). Um clique duplo abre um editor de texto, em vez de executar o programa no computador do professor.
- **Exclusão.** Quando a mensagem é apagada, o arquivo também sai do disco.

## Segurança dos links

O texto nunca é tratado como HTML: tudo é escapado e só depois os endereços aprovados viram links. Um link só fica clicável se:

- começar com `http://` ou `https://` (`javascript:`, `data:` e `file:` ficam como texto comum);
- não tiver usuário embutido, o truque de `https://www.umc.br@site-falso.com`;
- for um endereço válido para o validador do Django.

O link abre em outra aba com `rel="noopener noreferrer nofollow"`. O domínio aparece ao lado, entre parênteses, para ninguém clicar sem saber para onde vai.

## Privacidade (LGPD)

- **Auditoria.** A auditoria registra quem publicou, respondeu, enviou ou apagou cada mensagem e anexo, e quando. O **texto** das mensagens não é copiado para lá e aparece como `[conteúdo não registrado]` (atributo `AUDITORIA_CAMPOS_OCULTOS` dos models).
- **Termos de Uso.** Os Termos de Uso devem citar o tratamento das mensagens e dos anexos (dados enviados pelo próprio usuário, com a finalidade de comunicação acadêmica).

## Pontos de atenção para produção

- **Armazenamento dos anexos.** O disco do Render é apagado a cada novo deploy. Para os anexos sobreviverem, `MEDIA_ROOT` precisa apontar para um disco persistente do Render ou para um armazenamento de objetos (como S3), usando `django-storages`.
- **Antivírus.** A validação por tipo e conteúdo barra os ataques comuns, mas não substitui um antivírus. Se o sistema crescer, dá para passar cada anexo pelo ClamAV antes de salvar.
- **Limite de envios.** Ainda não existe limite de quantas mensagens alguém envia por minuto. Isso pode ser feito depois com `django-ratelimit`.
