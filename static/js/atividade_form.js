// Formulário de atividade: mostra os campos de código só nas atividades práticas
// e deixa o professor acrescentar casos de teste sem recarregar a página.
(function () {
  const tipo = document.getElementById("id_tipo");
  const codigoInicial = document.getElementById("id_codigo_inicial");
  const secaoCasos = document.getElementById("secao-casos");
  const blocoCodigo = codigoInicial ? codigoInicial.closest("p") : null;

  function atualizar() {
    const pratica = tipo && tipo.value === "PRATICA";
    if (blocoCodigo) blocoCodigo.hidden = !pratica;
    if (secaoCasos) secaoCasos.hidden = !pratica;
  }
  if (tipo) {
    tipo.addEventListener("change", atualizar);
    atualizar();
  }

  const botao = document.getElementById("adicionar-caso");
  const modelo = document.getElementById("modelo-caso");
  const lista = document.getElementById("lista-casos");
  const total = document.getElementById("id_casos-TOTAL_FORMS");
  const maximo = document.getElementById("id_casos-MAX_NUM_FORMS");
  if (!botao || !modelo || !lista || !total) return;

  botao.addEventListener("click", function () {
    const indice = parseInt(total.value, 10);
    if (maximo && indice >= parseInt(maximo.value, 10)) {
      botao.disabled = true;
      botao.textContent = "Limite de casos atingido";
      return;
    }
    const html = modelo.innerHTML.replace(/__prefix__/g, String(indice));
    lista.insertAdjacentHTML("beforeend", html);
    total.value = String(indice + 1);
  });
})();
