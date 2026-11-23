# RF33 — E-mails automáticos de acompanhamento

O RF33 da monografia exige dois eventos: alerta ao docente sobre alunos em situação
de atenção e aviso ao discente sobre feedback publicado. O RF32 continua separado:
recuperação de senha e mensagem de pendência escrita pelo professor.

## Feedback

Salvar uma avaliação oficial (nota e/ou feedback) cria um aviso para o autor da
submissão. O sinal de `AvaliacaoOficial` cobre a tela de correção e o Admin.
O aviso só é enviado depois da confirmação da transação. Uma operação desfeita
não envia e-mail. O parecer da IA não é avaliação oficial e não dispara esse aviso.

Salvar novamente sem mudar nota nem feedback não repete o e-mail. Uma revisão real
gera outro aviso e substitui versões antigas ainda pendentes. Se a atividade ou
trilha estiver em rascunho, o aviso aguarda a publicação e a próxima execução do
processador. Não há envio retroativo de avaliações anteriores à implantação.

## Atenção

A verificação reutiliza os indicadores e o limite percentual do painel. Ela
considera frequência, entregas e progresso calculáveis; valores iguais ao limite
não geram atenção. Nota e parecer de IA não são usados para diagnosticar alunos.

Cada matrícula ativa gera um aviso ao docente ao entrar em atenção. Enquanto a
situação persistir, novas verificações não repetem o aviso. Se a verificação
observar recuperação e depois uma nova queda, começa outro episódio e há novo
aviso. Trocar o docente também permite avisar o novo responsável. Contas e turmas
inativas não entram na verificação.

Na primeira execução, situações de atenção já existentes são consideradas novas.
O monitor observa o estado em cada execução, não todas as mudanças entre execuções.
Não há disparo por acesso GET ao painel.

## Persistência, falhas e privacidade

`EmailAcademico` guarda referências, status e tentativas; não copia notas, respostas
ou o texto do feedback. Os e-mails contêm uma orientação e, se `SIMAP_PUBLIC_URL`
estiver configurada, um link para a tela protegida. A sessão e as permissões continuam
sendo exigidas. Nome, RGM, nota e texto da avaliação não são incluídos no corpo.

Uma falha do provedor é registrada e o envio fica pendente, sem perder a avaliação.
O processador tenta novamente. Sem e-mail cadastrado, aguarda a correção do cadastro.
Antes de enviar ou reenviar, confere conta, vínculo, visibilidade e validade do aviso.
Se o aluno saiu da turma ou o alerta não se aplica mais, cancela o envio.

A reserva no banco impede que dois processadores enviem normalmente o mesmo aviso
ao mesmo tempo. Uma reserva abandonada pode ser retomada após dez minutos. Como
não há transação distribuída com o Mailgun, uma interrupção entre a aceitação pelo
provedor e o registro no banco pode causar repetição na recuperação; não se promete
entrega exatamente uma vez nem chegada garantida à caixa de entrada.

O status enviado significa aceito pelo backend. Com o backend console, significa
somente impresso no terminal; com Mailgun, aceito pela API, não confirmação de leitura.

## Execução

```powershell
.\venv\Scripts\python.exe manage.py migrate
# Uma verificação, útil para teste ou agendador:
.\venv\Scripts\python.exe manage.py notificar_acompanhamento
# Acompanhamento contínuo, em outro terminal (Ctrl+C para parar):
.\venv\Scripts\python.exe manage.py notificar_acompanhamento --intervalo 60
```

Sem esse processo ou agendamento, a verificação de atenção e as novas tentativas
não são automáticas. O feedback tenta o envio no próprio evento de publicação.
O parâmetro `--limite` limita o lote de avisos processados (padrão: 200).
Use um worker supervisionado ou um agendador em produção. Credenciais e configuração
do backend permanecem no ambiente. No sandbox Mailgun, autorize os destinatários.

## Agendamento no GitHub Actions

O workflow `.github/workflows/rf33.yml` verifica o RF33 nos minutos 17 e 47 de cada
hora (UTC). Ele roda somente na `main` do repositorio original, nunca em PRs ou
forks. Tambem permite executar manualmente em Actions, pelo botao Run workflow.
O arquivo precisa estar integrado na main para aparecer e ser agendado.

O runner acessa diretamente o mesmo PostgreSQL Neon do site e envia pelo Mailgun.
Nao depende do Render estar acordado nem do computador da equipe. Nao executa
migrations, nao limpa auditoria e nao muda configuracoes do Render.

Antes de ativar, abra Settings > Secrets and variables > Actions > New repository
secret no GitHub e cadastre os valores diretamente, sem colar em chats ou commits:

| Secret | Valor |
| --- | --- |
| `RF33_SECRET_KEY` | Valor de SECRET_KEY configurado no ambiente do SIMAP |
| `RF33_DATABASE_URL` | Conexao do banco Neon PostgreSQL 16 atualmente usado pelo Render, com SSL |
| `RF33_MAILGUN_API_KEY` | Chave de envio do mesmo dominio Mailgun do site |
| `RF33_MAILGUN_DOMAIN` | Dominio de envio, sem protocolo |
| `RF33_DEFAULT_FROM_EMAIL` | Mesmo remetente de DEFAULT_FROM_EMAIL no Render |
| `RF33_MAILGUN_API_URL` | Base da API, sem barra final: https://api.mailgun.net (US) ou https://api.eu.mailgun.net (EU) |

Os cinco primeiros sao obrigatorios. MAILGUN_API_URL usa US quando omitido;
dominios EU exigem configurar o sexto Secret. A chave do Gemini nao e necessaria.
Secrets do Render nao sao compartilhados automaticamente com o GitHub.
Somente mantenedores autorizados devem alterar o workflow e o codigo da main:
este job possui acesso ao banco real. Evite agendadores duplicados.

O runner usa Python 3.12 padrao em ubuntu-latest. Em repositorios publicos,
os runners padrao do GitHub Actions sao gratuitos; limites do Neon e Mailgun
continuam aplicaveis. Nao selecionar runners maiores pagos.

O agendamento pode atrasar e, em repositorios publicos sem atividade por 60 dias,
pode ser desativado pelo GitHub. Nao e um mecanismo de notificacao imediata.
Documentacao: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

Depois do merge e da configuracao dos Secrets:

1. Prepare uma turma ficticia com aluno em atencao e e-mail do docente autorizado.
2. Abra Actions > RF33 - alertas por e-mail > Run workflow, selecionando main.
3. Confira o resumo com contagens e o e-mail recebido pelo docente.
4. Repita: enquanto o mesmo episodio persistir, nao deve haver novo alerta.
5. Confira depois uma execucao com evento schedule: o teste manual, sozinho,
   nao comprova que o agendamento automatico aconteceu.

O workflow nao sobrepoe execucoes. As credenciais ficam apenas na etapa de envio,
e os logs publicos mostram contagens, sem tracebacks de banco ou provedores.
A opcao `--falhar-em-erro` marca a execucao como falha quando o provedor falha;
os avisos permanecem pendentes para nova tentativa. Pendencias sem e-mail ou
aguardando publicacao aparecem no resumo e exigem verificar cadastro/visibilidade.
Uma execucao verde nao comprova chegada na caixa de entrada: conferir o resumo
e os eventos do Mailgun. Uma falha pode ocorrer depois de alguns envios terem
sido realizados; nao significa rollback de e-mails.

## Verificação com dados fictícios

1. Cadastre professor e aluno com e-mails de teste, matricule e publique uma atividade.
2. Faça a entrega como aluno. Como professor, salve a nota e o feedback.
3. Confira o aviso no console; salvar os mesmos valores não deve repeti-lo.
4. Altere o feedback: deve haver novo aviso, sem nota nem feedback no corpo do e-mail.
5. Tenha uma atividade vencida após a matrícula sem conclusão ou uma chamada encerrada
   sem presença. Rode o processador e confira o aviso ao professor.
6. Rode novamente: o alerta persistente não deve gerar outro e-mail.
7. Resolva todos os indicadores abaixo do limite e rode a verificação. Depois provoque
   nova situação de atenção e confira outro aviso.

Os testes em `comunicacao/test_emails_academicos.py` usam banco isolado, backend em
memória e mocks. Não enviam mensagens reais. Testam também permissões, rollback,
alterações, reservas, reenvios e cancelamento de avisos obsoletos.
