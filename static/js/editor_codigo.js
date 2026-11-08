// Editor de código das atividades práticas.
//
// - O editor é o CodeMirror 5. Se ele não carregar, a caixa de texto comum
//   continua funcionando e a entrega não depende dele.
// - O Python roda no navegador (Pyodide), dentro de um iframe isolado
//   (python_sandbox.js). Nada do código do aluno roda no servidor.
// - "Parar", o tempo limite e o limite de saída derrubam o iframe inteiro,
//   que é recriado na próxima execução.
(function () {
  "use strict";

  const TEMPO_LIMITE_MS = 10000;
  const LIMITE_SAIDA = 20000;

  function absoluta(url) {
    return new URL(url, window.location.href).href;
  }

  function origemDe(url) {
    return new URL(url).origin;
  }

  function normalizar(texto) {
    // Compara saídas ignorando espaços no fim das linhas e linhas vazias no fim.
    return String(texto || "")
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map(function (linha) { return linha.replace(/\s+$/, ""); })
      .join("\n")
      .replace(/\n+$/, "");
  }

  function linhasDeEntrada(texto) {
    const valor = String(texto || "").replace(/\r\n?/g, "\n");
    if (valor === "") return [];
    const linhas = valor.split("\n");
    if (linhas[linhas.length - 1] === "") linhas.pop();
    return linhas;
  }

  function lerCookie(nome) {
    const partes = document.cookie ? document.cookie.split(";") : [];
    for (const parte of partes) {
      const [chave, ...resto] = parte.trim().split("=");
      if (chave === nome) return decodeURIComponent(resto.join("="));
    }
    return "";
  }

  // ---------------------------------------------------------------------
  // Execução isolada: um iframe sandbox por editor, criado só quando preciso.
  // ---------------------------------------------------------------------
  function criarExecutor(config, aoMudarEstado) {
    let iframe = null;
    let pronto = null;          // Promise resolvida quando o Python carregou
    let ouvinte = null;
    let atual = null;           // execução em andamento
    let contador = 0;

    function destruir() {
      if (ouvinte) window.removeEventListener("message", ouvinte);
      if (iframe) iframe.remove();
      iframe = null; pronto = null; ouvinte = null;
    }

    function montarSrcdoc() {
      const origemSimap = window.location.origin;
      const origemPyodide = origemDe(config.urlPyodide);
      const politica = [
        "default-src 'none'",
        "script-src " + origemSimap + " " + origemPyodide + " blob: 'unsafe-eval' 'wasm-unsafe-eval'",
        "worker-src blob:",
        "connect-src " + origemPyodide,
      ].join("; ");
      return '<!DOCTYPE html><html><head><meta charset="utf-8">' +
        '<meta http-equiv="Content-Security-Policy" content="' + politica + '">' +
        '<script src="' + config.urlSandbox + '"><\/script></head><body></body></html>';
    }

    function iniciar() {
      if (pronto) return pronto;
      pronto = new Promise(function (resolver, rejeitar) {
        aoMudarEstado("carregando");
        iframe = document.createElement("iframe");
        iframe.setAttribute("sandbox", "allow-scripts");
        iframe.setAttribute("title", "Execução do Python");
        iframe.setAttribute("aria-hidden", "true");
        iframe.style.display = "none";

        ouvinte = function (evento) {
          if (!iframe || evento.source !== iframe.contentWindow) return;
          const msg = evento.data || {};
          if (msg.origem !== "simap-python") return;
          if (msg.tipo === "sandbox-pronto") {
            iframe.contentWindow.postMessage(
              { tipo: "iniciar", urlWorker: config.urlWorker, urlPyodide: config.urlPyodide }, "*"
            );
          } else if (msg.tipo === "pronto") {
            aoMudarEstado("pronto", msg.versao);
            resolver();
          } else if (msg.tipo === "falha") {
            if (atual) {
              atual.terminar({ erro: "O Python parou: " + msg.texto, interrompido: true });
            } else {
              aoMudarEstado("falha", msg.texto);
              destruir();
              rejeitar(new Error(msg.texto));
            }
          } else if (atual && (msg.tipo === "saida" || msg.tipo === "fim") && (msg.tipo === "saida" || msg.id === atual.id)) {
            atual.receber(msg);
          }
        };
        window.addEventListener("message", ouvinte);
        iframe.srcdoc = montarSrcdoc();
        document.body.appendChild(iframe);
      });
      return pronto;
    }

    // Executa e devolve { saida, erro, tempo, interrompido }.
    function executar(codigo, entradas, aoReceberSaida) {
      return iniciar().then(function () {
        return new Promise(function (resolver) {
          const id = ++contador;
          let saida = "";
          let relogio = null;
          atual = {
            id: id,
            receber: function (msg) {
              if (msg.tipo === "saida") {
                (msg.partes || []).forEach(function (parte) {
                  saida += parte.texto;
                  aoReceberSaida(parte.texto, parte.fluxo);
                });
                if (saida.length > LIMITE_SAIDA + 2000) {
                  atual.terminar({ erro: "A saída ficou grande demais e a execução foi interrompida.", interrompido: true });
                }
              } else {
                atual.terminar({ erro: msg.erro || "", tempo: msg.tempo });
              }
            },
            terminar: function (resultado) {
              clearTimeout(relogio);
              atual = null;
              if (resultado.interrompido) destruir();
              resolver(Object.assign({ saida: saida }, resultado));
            },
          };
          relogio = setTimeout(function () {
            if (atual && atual.id === id) {
              atual.terminar({
                erro: "Tempo esgotado (" + TEMPO_LIMITE_MS / 1000 + " s). Será que há um laço que não termina?",
                interrompido: true,
              });
            }
          }, TEMPO_LIMITE_MS);
          iframe.contentWindow.postMessage({ tipo: "executar", id: id, codigo: codigo, entradas: entradas }, "*");
        });
      });
    }

    function parar() {
      if (atual) atual.terminar({ erro: "Execução interrompida por você.", interrompido: true });
      else destruir();
    }

    return { executar: executar, parar: parar, ocupado: function () { return !!atual; } };
  }

  // ---------------------------------------------------------------------
  // Um editor na página.
  // ---------------------------------------------------------------------
  function montarEditor(raiz) {
    const fonte = raiz.querySelector(".editor-fonte");
    const entrada = raiz.querySelector(".editor-entrada");
    const saida = raiz.querySelector(".editor-saida");
    const status = raiz.querySelector(".editor-status");
    const botaoExecutar = raiz.querySelector(".editor-executar");
    const botaoParar = raiz.querySelector(".editor-parar");
    const botaoTestar = raiz.querySelector(".editor-testar");
    const painelCasos = raiz.querySelector(".editor-resultado-casos");
    const somenteLeitura = raiz.dataset.somenteLeitura === "1";
    const elementoCasos = document.getElementById(raiz.dataset.casos);
    const casos = elementoCasos ? JSON.parse(elementoCasos.textContent) : [];

    let editor = null;
    if (window.CodeMirror) {
      editor = window.CodeMirror.fromTextArea(fonte, {
        mode: "python",
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        matchBrackets: true,
        autoCloseBrackets: !somenteLeitura,
        readOnly: somenteLeitura,
        viewportMargin: Infinity,
        extraKeys: {
          Tab: function (cm) {
            if (cm.somethingSelected()) cm.indentSelection("add");
            else cm.replaceSelection("    ", "end");
          },
          "Shift-Tab": function (cm) { cm.indentSelection("subtract"); },
          "Ctrl-Enter": function () { botaoExecutar.click(); },
          "Cmd-Enter": function () { botaoExecutar.click(); },
        },
      });
      raiz.classList.add("com-codemirror");
      // O texto vai para a caixa escondida só na hora de entregar; a checagem
      // de "campo vazio" passa a ser feita aqui no JavaScript.
      fonte.required = false;
    }

    function codigoAtual() {
      return editor ? editor.getValue() : fonte.value;
    }

    function escreverStatus(texto, classe) {
      status.textContent = texto;
      status.className = "editor-status small " + (classe || "text-muted");
    }

    function acrescentarSaida(texto, fluxo) {
      const ultimo = saida.lastElementChild;
      const classe = fluxo === "err" ? "text-danger" : "";
      if (ultimo && ultimo.className === classe) {
        ultimo.textContent += texto;
      } else {
        const trecho = document.createElement("span");
        trecho.className = classe;
        trecho.textContent = texto;
        saida.appendChild(trecho);
      }
      saida.scrollTop = saida.scrollHeight;
    }

    function ocupado(sim) {
      botaoExecutar.disabled = sim;
      if (botaoTestar) botaoTestar.disabled = sim;
      botaoParar.disabled = !sim;
    }

    const executor = criarExecutor(
      { urlPyodide: absoluta(raiz.dataset.pyodideUrl), urlWorker: absoluta(raiz.dataset.workerUrl), urlSandbox: absoluta(raiz.dataset.sandboxUrl) },
      function (estado, detalhe) {
        if (estado === "carregando") escreverStatus("Carregando o Python… (na primeira vez pode levar alguns segundos)");
        else if (estado === "pronto") escreverStatus("Python " + (detalhe || "") + " pronto");
        else if (estado === "falha") escreverStatus("Não foi possível carregar o Python: " + detalhe, "text-danger");
      }
    );

    function mostrarErro(texto) {
      if (texto) acrescentarSaida((saida.textContent && !saida.textContent.endsWith("\n") ? "\n" : "") + texto, "err");
    }

    botaoExecutar.addEventListener("click", function () {
      if (executor.ocupado()) return;
      saida.textContent = "";
      if (painelCasos) painelCasos.hidden = true;
      ocupado(true);
      executor.executar(codigoAtual(), linhasDeEntrada(entrada.value), acrescentarSaida)
        .then(function (r) {
          mostrarErro(r.erro);
          if (r.erro) escreverStatus(r.interrompido ? "Execução interrompida" : "Terminou com erro", "text-danger");
          else escreverStatus("✔ Executou em " + (r.tempo / 1000).toFixed(2).replace(".", ",") + " s", "text-success");
          raiz.dispatchEvent(new CustomEvent("editor:executou", { detail: { codigo: codigoAtual(), erro: r.erro || "", saida: r.saida } }));
        })
        .catch(function () { /* o status já mostra a falha ao carregar */ })
        .finally(function () { ocupado(false); });
    });

    botaoParar.addEventListener("click", function () { executor.parar(); });

    if (botaoTestar) {
      botaoTestar.addEventListener("click", async function () {
        if (executor.ocupado()) return;
        ocupado(true);
        saida.textContent = "";
        painelCasos.hidden = false;
        painelCasos.textContent = "";
        const lista = document.createElement("ol");
        lista.className = "small mb-1 ps-3";
        painelCasos.appendChild(lista);
        let acertos = 0;
        try {
          for (let i = 0; i < casos.length; i++) {
            const caso = casos[i];
            escreverStatus("Testando caso " + (i + 1) + " de " + casos.length + "…");
            const r = await executor.executar(codigoAtual(), linhasDeEntrada(caso.entrada), function () {});
            const obtida = normalizar(r.saida);
            const ok = !r.erro && obtida === normalizar(caso.saida);
            if (ok) acertos++;
            const item = document.createElement("li");
            item.className = ok ? "text-success" : "text-danger";
            const titulo = document.createElement("span");
            titulo.textContent = ok ? "✔ passou" : (r.erro ? "✘ erro na execução" : "✘ saída diferente da esperada");
            item.appendChild(titulo);
            if (!ok) {
              const detalhes = document.createElement("details");
              detalhes.className = "text-body";
              const resumo = document.createElement("summary");
              resumo.textContent = "ver detalhes";
              detalhes.appendChild(resumo);
              [["Entrada", caso.entrada || "(vazia)"], ["Esperado", caso.saida], ["Seu programa", r.erro ? (r.saida + r.erro) : r.saida]]
                .forEach(function (par) {
                  const rotulo = document.createElement("div");
                  rotulo.className = "fw-semibold mt-1";
                  rotulo.textContent = par[0];
                  const bloco = document.createElement("pre");
                  bloco.className = "bg-light border rounded p-1 mb-0";
                  bloco.textContent = par[1];
                  detalhes.appendChild(rotulo);
                  detalhes.appendChild(bloco);
                });
              item.appendChild(detalhes);
            }
            lista.appendChild(item);
            if (r.interrompido && r.erro.indexOf("por você") !== -1) break;
          }
          const resumo = acertos + " de " + casos.length + " caso(s) passaram";
          escreverStatus(resumo, acertos === casos.length ? "text-success" : "text-danger");
        } catch (e) {
          /* falha ao carregar o Python: o status já explica */
        } finally {
          ocupado(false);
        }
      });
    }

    // Rascunho salvo sozinho (só na tela do aluno, antes da entrega).
    const urlRascunho = raiz.dataset.urlRascunho;
    if (urlRascunho && !somenteLeitura) {
      let espera = null;
      let ultimoSalvo = codigoAtual();
      const salvar = function () {
        const codigo = codigoAtual();
        if (codigo === ultimoSalvo) return;
        const corpo = new URLSearchParams({ codigo: codigo });
        fetch(urlRascunho, {
          method: "POST",
          headers: { "X-CSRFToken": lerCookie("csrftoken") || (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "" },
          body: corpo,
          credentials: "same-origin",
        })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (res) {
            if (res.ok) { ultimoSalvo = codigo; escreverStatus("Rascunho salvo às " + res.d.salvo_em); }
            else escreverStatus(res.d.erro || "Não foi possível salvar o rascunho", "text-danger");
          })
          .catch(function () { escreverStatus("Sem conexão: o rascunho não foi salvo", "text-danger"); });
      };
      const agendar = function () { clearTimeout(espera); espera = setTimeout(salvar, 2000); };
      if (editor) editor.on("change", agendar); else fonte.addEventListener("input", agendar);
      window.addEventListener("beforeunload", salvar);
    }

    // O formulário de entrega precisa do texto atualizado do editor.
    const formulario = raiz.closest("form");
    if (formulario && editor) {
      formulario.addEventListener("submit", function (evento) {
        editor.save();
        if (!fonte.value.trim()) {
          evento.preventDefault();
          escreverStatus("Escreva o código antes de entregar.", "text-danger");
        }
      });
    }

    raiz.editorSimap = { codigo: codigoAtual, editor: editor };
  }

  document.querySelectorAll("[data-editor-codigo]").forEach(montarEditor);

  // Editor dentro de algo que estava escondido (o acordeão da correção) precisa
  // se redesenhar quando aparece.
  document.addEventListener("shown.bs.collapse", function (evento) {
    evento.target.querySelectorAll("[data-editor-codigo]").forEach(function (raiz) {
      if (raiz.editorSimap && raiz.editorSimap.editor) raiz.editorSimap.editor.refresh();
    });
  });
})();
