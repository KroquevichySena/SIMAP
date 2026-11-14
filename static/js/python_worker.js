// Roda o Python do aluno (Pyodide) fora da página principal.
//
// Este worker nasce dentro de um iframe isolado (python_sandbox.js), que não
// tem acesso aos cookies do SIMAP e só pode baixar arquivos do endereço do
// Pyodide. Mesmo que o código do aluno tente usar a rede ou o JavaScript da
// página, não chega a lugar nenhum.

let pyodide = null;

// Prepara a função que executa o código do aluno. Cada execução começa do
// zero (variáveis não passam de uma execução para outra), o input() lê da
// caixa "Entrada" sem repetir o valor na saída, e o erro mostra só as linhas do
// código do aluno, sem as linhas internas do Pyodide.
const PREPARO = `
import builtins, sys, traceback

LIMITE_SAIDA = 20000


class _SaidaLimitada:
    def __init__(self, original):
        self.original = original
        self.total = 0

    def write(self, texto):
        self.total += len(texto)
        if self.total > LIMITE_SAIDA:
            raise RuntimeError(
                "a saída passou de %d caracteres e a execução foi interrompida "
                "(será que há um laço que não termina?)" % LIMITE_SAIDA
            )
        return self.original.write(texto)

    def flush(self):
        return self.original.flush()

    def __getattr__(self, nome):
        return getattr(self.original, nome)


_saida_original = sys.stdout


def __simap_executar(codigo, entradas):
    fila = list(entradas)

    def entrada(mensagem=""):
        sys.stdout.write(str(mensagem))
        if not fila:
            raise EOFError(
                "o programa pediu mais entradas do que as linhas da caixa Entrada"
            )
        return fila.pop(0)

    builtins.input = entrada
    sys.stdout = _SaidaLimitada(_saida_original)
    escopo = {"__name__": "__main__", "__builtins__": builtins}
    try:
        exec(compile(codigo, "seu_codigo.py", "exec"), escopo)
        return ""
    except SystemExit:
        return ""
    except BaseException:
        tipo, valor, tb = sys.exc_info()
        quadros = [q for q in traceback.extract_tb(tb) if q.filename == "seu_codigo.py"]
        linhas = traceback.format_list(quadros) + traceback.format_exception_only(tipo, valor)
        cabecalho = "Traceback (most recent call last):\\n" if quadros else ""
        return cabecalho + "".join(linhas)
    finally:
        try:
            sys.stdout.flush()
        finally:
            sys.stdout = _saida_original
            sys.stderr.flush()
`;

function enviar(mensagem) {
  self.postMessage(mensagem);
}

// A saída é juntada em pedaços antes de ir para a página. Mandar uma mensagem
// por linha travaria a tela num programa que imprime milhares de linhas.
let pendentes = [];
let tamanhoPendente = 0;
let ultimoEnvio = 0;

function despejar() {
  if (!pendentes.length) return;
  enviar({ tipo: "saida", partes: pendentes });
  pendentes = [];
  tamanhoPendente = 0;
  ultimoEnvio = performance.now();
}

function guardarSaida(fluxo, texto) {
  const ultima = pendentes[pendentes.length - 1];
  if (ultima && ultima.fluxo === fluxo) ultima.texto += texto;
  else pendentes.push({ fluxo: fluxo, texto: texto });
  tamanhoPendente += texto.length;
  if (tamanhoPendente >= 4096 || performance.now() - ultimoEnvio > 100) despejar();
}

async function iniciar(urlPyodide) {
  importScripts(urlPyodide + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: urlPyodide });
  // "write" recebe os bytes assim que o Python descarrega a saída (sem esperar
  // o fim da linha), e isatty faz o print() descarregar a cada linha.
  const decodOut = new TextDecoder();
  const decodErr = new TextDecoder();
  pyodide.setStdout({ write: (bytes) => { guardarSaida("out", decodOut.decode(bytes, { stream: true })); return bytes.length; }, isatty: true });
  pyodide.setStderr({ write: (bytes) => { guardarSaida("err", decodErr.decode(bytes, { stream: true })); return bytes.length; }, isatty: true });
  pyodide.setStdin({ error: true });
  pyodide.runPython(PREPARO);
  enviar({ tipo: "pronto", versao: pyodide.runPython("import sys; sys.version.split()[0]") });
}

function executar(id, codigo, entradas) {
  const inicio = performance.now();
  ultimoEnvio = inicio;
  const funcao = pyodide.globals.get("__simap_executar");
  const lista = pyodide.toPy(entradas);
  let erro = "";
  try {
    erro = funcao(codigo, lista);
  } catch (falha) {
    erro = String(falha && falha.message ? falha.message : falha);
  } finally {
    lista.destroy();
    funcao.destroy();
    despejar();
  }
  enviar({ tipo: "fim", id: id, erro: erro, tempo: Math.round(performance.now() - inicio) });
}

self.onmessage = async (evento) => {
  const msg = evento.data || {};
  try {
    if (msg.tipo === "iniciar") {
      await iniciar(String(msg.urlPyodide));
    } else if (msg.tipo === "executar" && pyodide) {
      executar(msg.id, String(msg.codigo), (msg.entradas || []).map(String));
    }
  } catch (falha) {
    enviar({ tipo: "falha", texto: String(falha && falha.message ? falha.message : falha) });
  }
};
