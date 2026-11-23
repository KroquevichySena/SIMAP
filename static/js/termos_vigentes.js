// Se a coordenação publicar uma nova versão dos termos enquanto a pessoa está
// usando o SIMAP, a página é bloqueada na hora e só libera depois do aceite.
//
// A consulta vai sem cookies (credentials: "omit"): não renova a sessão, então
// o logout por inatividade continua valendo, e não entra na auditoria.
(function () {
  "use strict";
  var corpo = document.body;
  var aceita = corpo.dataset.termosVersao;
  var endereco = corpo.dataset.termosVigente;
  var aceite = corpo.dataset.termosAceite;
  var intervalo = Number(corpo.dataset.termosIntervalo || 15000);
  if (!aceita || !endereco || !aceite) return;
  var bloqueada = false;

  function bloquear(versao) {
    if (bloqueada) return;
    bloqueada = true;
    var layout = document.querySelector(".simap-layout");
    if (layout) {
      layout.inert = true;
      layout.setAttribute("aria-hidden", "true");
    }
    var destino = aceite + "?next=" + encodeURIComponent(location.pathname + location.search);
    var aviso = document.createElement("div");
    aviso.className = "simap-termos-bloqueio";
    aviso.setAttribute("role", "alertdialog");
    aviso.setAttribute("aria-modal", "true");
    aviso.setAttribute("aria-labelledby", "termos-bloqueio-titulo");
    aviso.setAttribute("aria-describedby", "termos-bloqueio-texto");
    var cartao = document.createElement("div");
    cartao.className = "simap-termos-bloqueio-cartao";
    var titulo = document.createElement("h2");
    titulo.id = "termos-bloqueio-titulo";
    titulo.textContent = "Os termos de uso foram atualizados";
    var texto = document.createElement("p");
    texto.id = "termos-bloqueio-texto";
    texto.textContent = "A coordenação publicou a versão " + versao + " dos Termos de Uso e da Política de Privacidade. " +
      "Para continuar usando o SIMAP, leia e aceite a nova versão. Depois do aceite, você volta para esta página.";
    var botao = document.createElement("a");
    botao.className = "simap-botao simap-botao-primario";
    botao.href = destino;
    botao.textContent = "Ler e aceitar os termos";
    cartao.append(titulo, texto, botao);
    aviso.append(cartao);
    corpo.append(aviso);
    botao.focus();
  }

  function conferir() {
    if (bloqueada) return;
    fetch(endereco, { credentials: "omit", cache: "no-store", headers: { Accept: "application/json" } })
      .then(function (resposta) { return resposta.ok ? resposta.json() : null; })
      .then(function (dados) {
        if (dados && dados.versao && dados.versao !== aceita) bloquear(dados.versao);
      })
      .catch(function () { /* sem conexão: tenta de novo na próxima rodada */ });
  }

  setInterval(conferir, intervalo);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") conferir();
  });
})();
