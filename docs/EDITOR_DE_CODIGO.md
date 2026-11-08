# Editor de código das atividades práticas

Atividades do tipo **Prática (código)** agora abrem num editor parecido com o
Google Colab: o aluno escreve o código, executa, vê a saída e roda os casos de
teste antes de entregar.

## Para o aluno

Em **Minhas trilhas**, a atividade prática mostra o botão **💻 Abrir editor de código**.

- **Editor:** cores, números de linha, indentação automática, Tab e Shift+Tab, fechamento de parênteses. `Ctrl+Enter` executa.
- **▶ Executar:** roda o código e mostra a saída. Erros aparecem com a linha do código do aluno (sem as linhas internas do Python).
- **Entrada:** cada linha da caixa é a resposta de um `input()`. O valor lido aparece na saída, como num terminal. Se o programa pedir mais entradas do que existem, aparece um aviso claro.
- **■ Parar:** interrompe a execução. Também há tempo limite de 10 s e limite de 20.000 caracteres de saída, então um laço infinito não trava a página.
- **🧪 Testar casos:** roda cada caso de teste do professor e mostra ✔ ou ✘, com o esperado e o obtido nos casos que falharam.
- **Rascunho:** é salvo sozinho a cada pausa na digitação e volta quando o aluno reabre a atividade.
- **Entregar resposta:** envia o código (e anexos, se houver) como a entrega normal. Depois disso o código fica só para leitura, mas ainda pode ser executado.

## Para o professor

No formulário da atividade, ao escolher o tipo **Prática (código)**, aparecem:

- **Código inicial:** o que já vem escrito no editor do aluno (por exemplo, o esqueleto de uma função).
- **Casos de teste:** entrada e saída esperada, até 10. A comparação ignora espaços no fim das linhas e linhas vazias no fim. Espaços no começo da linha são mantidos.

Na **tela de correção**, o código do aluno aparece no mesmo editor, só para leitura, com os botões de executar e testar casos.

> Os casos de teste são um retorno para o aluno. O resultado é calculado no navegador, então não vale como nota automática: a nota continua sendo do professor.

## Como funciona e por que é seguro

- O Python roda **no navegador**, com o [Pyodide](https://pyodide.org) (Python compilado para WebAssembly). Nada do código do aluno roda no servidor do SIMAP.
- A execução acontece num **iframe isolado** (`sandbox="allow-scripts"`), sem acesso aos cookies do SIMAP nem à página, e com uma política de segurança (CSP) que só deixa baixar o Pyodide. Um código como `js.XMLHttpRequest` tentando ler páginas do SIMAP é bloqueado. Isso importa principalmente na correção, quando o professor executa o código de um aluno no navegador dele.
- Dentro do iframe, o Python roda num **Web Worker**. "Parar", o tempo limite e o limite de saída derrubam o iframe inteiro, que é recriado na próxima execução.
- O editor é o **CodeMirror 5**, carregado da jsDelivr com versão fixa e checagem de integridade (`integrity`). Se ele não carregar, a caixa de texto comum continua funcionando.

### Arquivos

| Arquivo | O que faz |
|---|---|
| `static/js/editor_codigo.js` | Editor, botões, casos de teste, rascunho e o iframe isolado |
| `static/js/python_sandbox.js` | Roda dentro do iframe e cria o worker |
| `static/js/python_worker.js` | Carrega o Pyodide e executa o código |
| `templates/entregas/_editor_codigo.html` | O componente do editor (usado pelo aluno e na correção) |
| `templates/entregas/discente/resolver.html` | A tela do aluno |

### Configuração

`SIMAP_PYODIDE_URL` (padrão `https://cdn.jsdelivr.net/npm/pyodide@0.29.5/`): endereço do Pyodide.
Dá para hospedar uma cópia própria; o servidor precisa enviar `Access-Control-Allow-Origin: *`.

A primeira execução baixa cerca de 11 MB (fica em cache no navegador depois). Funciona a
biblioteca padrão do Python; pacotes como `numpy` não estão incluídos, e `tkinter`/`turtle`
não funcionam no navegador.

## Testes

`entregas/test_editor.py` (18 testes): acesso à tela, botão só nas práticas, 404 para quem não
é da turma, rascunho (salvar, reabrir, limite, CSRF), entrega apagando o rascunho e travando a
edição, cadastro e remoção de casos de teste, espaços preservados, código com `</script>`
sem quebrar a página e o editor na correção.

A execução no navegador foi verificada com o Chromium e o Pyodide 0.29.5: saída e entrada,
casos de teste, traceback, bloqueio de rede pela CSP, tempo limite, limite de saída, botão
Parar, rascunho e execução pelo professor na correção.
