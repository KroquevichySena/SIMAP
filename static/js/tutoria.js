// Painel "Preciso de ajuda": o aluno só aperta botões; o pedido é montado no
// servidor. No "Olha meu código", vão junto o código do editor e o último erro.
(function () {
  "use strict";
  if (window.__painelAjudaPronto) return;
  window.__painelAjudaPronto = true;

  function lerCookie(nome) {
    const item = (document.cookie || "").split(";").map(function (p) { return p.trim(); })
      .find(function (p) { return p.indexOf(nome + "=") === 0; });
    return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : "";
  }

  // Guarda o resultado da última execução do editor (se houver editor na página).
  let ultimaExecucao = { erro: "" };
  document.addEventListener("editor:executou", function (e) { ultimaExecucao = e.detail || { erro: "" }; }, true);

  function codigoDoEditor() {
    const raiz = document.querySelector("[data-editor-codigo]");
    if (raiz && raiz.editorSimap) return raiz.editorSimap.codigo();
    const fonte = document.querySelector(".editor-fonte");
    return fonte ? fonte.value : "";
  }

  document.querySelectorAll("[data-painel-ajuda]").forEach(function (painel) {
    const status = painel.querySelector(".ajuda-status");
    const historico = painel.querySelector(".ajuda-historico");
    const restantes = painel.querySelector(".ajuda-restantes");
    const botoes = painel.querySelectorAll("button[data-tipo]");
    const botaoDica = painel.querySelector("button[data-tipo=DICA]");
    let proximoNivel = painel.dataset.proximoNivel ? parseInt(painel.dataset.proximoNivel, 10) : null;
    let restantesHoje = parseInt(painel.dataset.restantes || "0", 10);

    function atualizar(estado) {
      if (estado) {
        proximoNivel = estado.proximo_nivel;
        restantesHoje = estado.restantes_hoje;
      }
      restantes.textContent = restantesHoje + " ajuda(s) restante(s) hoje";
      botaoDica.querySelector(".ajuda-nivel").textContent = proximoNivel ? "(nível " + proximoNivel + ")" : "(acabaram)";
      botoes.forEach(function (b) { b.disabled = restantesHoje <= 0; });
      if (!proximoNivel) botaoDica.disabled = true;
    }

    function escrever(texto, classe) {
      status.textContent = texto;
      status.className = "small ajuda-status mb-2 " + (classe || "text-muted");
    }

    botoes.forEach(function (botao) {
      botao.addEventListener("click", function () {
        const tipo = botao.dataset.tipo;
        const dados = new URLSearchParams({ tipo: tipo });
        if (tipo === "DICA") dados.set("nivel", String(proximoNivel || 0));
        if (tipo === "DICA" || tipo === "CODIGO") dados.set("codigo", codigoDoEditor());
        if (tipo === "CODIGO") dados.set("erro", ultimaExecucao.erro || "");

        botoes.forEach(function (b) { b.disabled = true; });
        escrever(tipo === "MATERIAL" ? "Procurando materiais na web…" : "Pensando…");
        fetch(painel.dataset.url, {
          method: "POST",
          headers: { "X-CSRFToken": lerCookie("csrftoken") || (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "" },
          body: dados,
          credentials: "same-origin",
        })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (res) {
            if (res.ok) {
              // HTML montado pelo servidor, com o texto já escapado.
              historico.insertAdjacentHTML("afterbegin", res.d.html);
              escrever(res.d.status === "ERRO" ? "A IA não respondeu agora. Tente de novo em instantes." : "");
            } else {
              escrever(res.d.erro || "Não foi possível pedir ajuda agora.", "text-danger");
            }
            atualizar(res.d.estado);
          })
          .catch(function () { escrever("Sem conexão com o SIMAP.", "text-danger"); atualizar(); });
      });
    });

    atualizar();
  });
})();
