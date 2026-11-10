// Ponte entre a página do SIMAP e o worker do Python.
//
// Este script roda dentro de um iframe com sandbox="allow-scripts", ou seja,
// numa origem "anônima": sem cookies, sem acesso à página de fora e com uma
// política (CSP) que só deixa baixar o Pyodide. A página manda as ordens por
// postMessage e recebe de volta a saída do programa.
(function () {
  let worker = null;

  function paraPagina(mensagem) {
    window.parent.postMessage(Object.assign({ origem: "simap-python" }, mensagem), "*");
  }

  window.addEventListener("message", function (evento) {
    if (evento.source !== window.parent) return;
    const msg = evento.data || {};

    if (msg.tipo === "iniciar" && !worker) {
      // O worker precisa nascer de um blob para herdar esta mesma origem
      // isolada (e a mesma CSP); o código dele vem do SIMAP via importScripts.
      const fonte = "importScripts(" + JSON.stringify(String(msg.urlWorker)) + ");";
      const url = URL.createObjectURL(new Blob([fonte], { type: "text/javascript" }));
      worker = new Worker(url);
      worker.onmessage = function (e) { paraPagina(e.data); };
      worker.onerror = function (e) {
        e.preventDefault();
        paraPagina({ tipo: "falha", texto: e.message || "o Python parou de responder" });
      };
      worker.postMessage({ tipo: "iniciar", urlPyodide: String(msg.urlPyodide) });
    } else if (msg.tipo === "executar" && worker) {
      worker.postMessage({ tipo: "executar", id: msg.id, codigo: msg.codigo, entradas: msg.entradas });
    }
  });

  paraPagina({ tipo: "sandbox-pronto" });
})();
