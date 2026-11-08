# Melhorias nas trilhas: materiais, entregas com arquivo e avisos

Estas melhorias reaproveitam a validação de arquivos e de links do módulo de
comunicação (ver `docs/COMUNICACAO.md`). Nada de regra nova de segurança: o
material do professor e o arquivo da entrega passam pela mesmíssima checagem
dos anexos do mural.

## Material de apoio na trilha e na atividade

- Nos formulários de trilha e de atividade há o campo **Material de apoio**: até 5 arquivos por vez, de até 10 MB cada (PDF, Office, imagens, texto e código-fonte).
- `.bat`, `.exe`, compactados, documentos com macro e executáveis disfarçados são recusados. Se um arquivo for recusado, **nada** é salvo e o formulário volta com o motivo.
- Na edição aparece a lista **Remover material já enviado**. Só dá para remover material daquela própria trilha ou atividade.
- O download (`/materiais/<id>/`) é liberado para o professor da turma e para alunos com matrícula ativa, desde que a trilha (e a atividade, se for o caso) esteja publicada. Para qualquer outra pessoa a resposta é 404.

## Entrega com arquivo

- O aluno pode anexar arquivos junto com a resposta (por exemplo, o `.py` do exercício).
- Se algum arquivo for barrado, a entrega inteira não é registrada e o aluno vê o motivo. A resposta e os arquivos são gravados juntos, numa transação.
- A análise do Gemini continua usando **só o texto** da resposta. Os arquivos não são enviados para a IA.
- O arquivo só pode ser baixado pelo próprio aluno e pelo professor da turma (`/entregas/anexos/<id>/`). Na tela de correção o professor vê a lista de arquivos de cada entrega.

## Links clicáveis

A descrição da trilha e o enunciado da atividade agora mostram os links como
clicáveis, tanto para o aluno quanto na tela de correção, com o mesmo filtro
`texto_com_links` da comunicação (`javascript:`, `data:` e links com usuário
embutido continuam como texto comum).

## Notificações no sino

| Quando | Quem recebe |
|---|---|
| Uma trilha passa a ficar publicada (criada já publicada, ou marcada depois) | Alunos ativos da turma |
| Uma atividade passa a ficar visível (publicada, numa trilha publicada) | Alunos ativos da turma |
| O prazo de uma atividade está chegando e o aluno ainda não entregou | Esse aluno |

Editar algo que já estava publicado não gera aviso de novo. A notificação leva
direto para a trilha ou atividade na tela **Minhas Trilhas**.

### Lembrete de prazo

```bash
python manage.py notificar_prazos            # prazos das próximas 24 horas
python manage.py notificar_prazos --horas 48
```

O comando pode rodar de hora em hora (cron do servidor ou Cron Job do Render).
Cada aluno recebe um único lembrete por atividade, por mais vezes que o
comando rode.

## Testes

- `core/test_materiais.py`: envio e remoção de material, `.bat` recusado, permissão de download, avisos de publicação sem duplicar, lembrete de prazo e links na tela do aluno.
- `entregas/test_anexos.py`: entrega com e sem arquivo, `.bat` e `.exe` disfarçado barrando a entrega, permissão de download e arquivo visível na correção.
