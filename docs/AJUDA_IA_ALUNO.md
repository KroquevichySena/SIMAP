# Ajuda da IA para o aluno

Além de ajudar o professor na correção, o Gemini agora ajuda o aluno a
estudar, sem resolver o exercício por ele.

## Como o aluno usa

- **Atividade prática:** o painel **🙋 Preciso de ajuda** fica embaixo do editor de código.
- **Atividade teórica:** o link **🙋 Preciso de ajuda** aparece em *Minhas trilhas* e abre uma página com o enunciado e o painel.

O aluno **não escreve o pedido**: ele só escolhe uma ação.

| Botão | O que a IA faz |
|---|---|
| 💡 Me dá uma dica | Dicas em níveis. **Nível 1:** perguntas que fazem pensar. **Nível 2:** aponta o conceito ou recurso da linguagem. **Nível 3:** estrutura da solução em pseudocódigo, em português. Cada nível só libera depois do anterior, e a IA recebe as dicas já dadas para não repetir. |
| 📖 Explica o conceito | Explica o assunto com um exemplo de **outro contexto**, diferente do exercício. |
| 🔎 Busca material | Busca na web (Google, pelo próprio Gemini) de 3 a 5 materiais, com os links das fontes. |
| 🐞 Olha meu código | Só nas práticas. Envia o código do editor e o erro da última execução; a IA explica o erro e onde olhar, sem reescrever o código. |

As respostas ficam guardadas e aparecem de novo quando o aluno reabre a atividade.

## Para o professor

No formulário da atividade:

- **Ajuda da IA para o aluno** (ligada por padrão). Desligue em provas e avaliações.
- **Até qual nível de dica:** 1, 2 ou 3.

Na **tela de correção**, cada entrega mostra quantas ajudas o aluno usou, até qual nível
de dica chegou e quantas respostas foram barradas (passe o mouse no selo para ver os tipos).
Os pedidos também ficam registrados na **auditoria** (sem o código nem o texto das respostas).

## Proteções contra "forçar" a resposta

1. **Sem prompt livre.** O pedido é montado pelo SIMAP a partir do botão escolhido.
2. **Regras nas instruções de sistema.** O enunciado, o código, o erro e as dicas anteriores vão marcados (`<codigo_do_aluno>` etc.) como material de trabalho, que a IA não deve obedecer. Um texto que tente fechar essas marcações é neutralizado.
3. **Comentários apagados.** Os comentários do código (onde costuma vir "ignore as regras") são removidos antes de ir para a IA, mantendo os números de linha.
4. **Conferência da resposta.** Se a resposta tiver mais de 3 linhas de código, é barrada. Nas dicas, explicações e análises, uma segunda consulta à IA responde "isto entrega a solução? SIM/NÃO". Respostas barradas são trocadas por uma orientação genérica.
5. **Limites:** 10 pedidos por dia em cada atividade, até 2 dicas por nível e 15 segundos entre pedidos. Falhas da IA não gastam o limite.
6. **Texto seguro na tela.** A resposta da IA é escapada (nada de HTML ou scripts) e só links `https://` viram clicáveis. As sugestões de busca do Google, que precisam ser exibidas quando a busca é usada, ficam num quadro isolado, sem scripts.

Nenhuma proteção de IA é perfeita, por isso o professor vê quanto de ajuda cada aluno usou.

## Configuração

| Variável | Padrão | Para quê |
|---|---|---|
| `GEMINI_API_KEY` | (já existia) | Chave do Gemini |
| `TUTORIA_MODELO` | `gemini-3.1-flash-lite` | Modelo usado na ajuda ao aluno |

Limites em `SIMAP/settings.py`: `TUTORIA_PEDIDOS_POR_DIA`, `TUTORIA_DICAS_POR_NIVEL`, `TUTORIA_INTERVALO_SEGUNDOS`.

A ajuda usa a biblioteca nova do Google, **google-genai** (a antiga, `google-generativeai`,
foi descontinuada e não tem a busca na web). A análise da correção continua na biblioteca
antiga por enquanto; vale migrar depois.

## Código

| Arquivo | O que faz |
|---|---|
| `tutoria/servicos.py` | Regras, montagem do pedido, limites e conferência da resposta |
| `tutoria/gemini.py` | Conversa com o Gemini (google-genai), incluindo a busca na web |
| `tutoria/views.py` | Página de ajuda das teóricas e o pedido feito pelo painel |
| `tutoria/templates/tutoria/_painel.html` | O painel "Preciso de ajuda" |
| `static/js/tutoria.js` | Botões do painel; pega o código e o último erro do editor |

## Testes

`tutoria/tests.py` (28 testes, com o Gemini simulado): dicas em níveis e limite do professor,
dicas anteriores enviadas, comentários removidos, marcações neutralizadas, regras só nas
instruções de sistema, resposta com código barrada (com e sem cercas de Markdown),
verificador, pseudocódigo aceito, HTML escapado, busca com fontes e sugestões isoladas,
limites diário e de intervalo, falha da IA sem gastar limite, ajuda desligada, acesso (404,
CSRF, professor), painel com histórico, página das teóricas, resumo na correção e a leitura da
resposta da biblioteca do Gemini.
