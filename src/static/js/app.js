// Inicializa ícones Lucide em toda a página.
(function () {
  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }
})();

// Menu lateral: fixo nas resoluções altas (só CSS), off-canvas nas baixas.
(function () {
  var botao = document.getElementById("btn-menu");
  var fundo = document.getElementById("menu-fundo");
  if (!botao) return;

  function abrir(estado) {
    document.body.classList.toggle("menu-aberto", estado);
    botao.setAttribute("aria-expanded", estado ? "true" : "false");
  }

  botao.addEventListener("click", function () {
    abrir(!document.body.classList.contains("menu-aberto"));
  });

  if (fundo) fundo.addEventListener("click", function () { abrir(false); });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") abrir(false);
  });

  document.querySelectorAll(".app-sidenav__item").forEach(function (link) {
    link.addEventListener("click", function () { abrir(false); });
  });
})();

// Menu da conta (avatar na topbar).
(function () {
  var botao = document.getElementById("btn-conta");
  if (!botao) return;
  var conta = botao.parentNode;

  function abrir(estado) {
    conta.classList.toggle("aberta", estado);
    botao.setAttribute("aria-expanded", estado ? "true" : "false");
  }

  botao.addEventListener("click", function (e) {
    e.stopPropagation();
    abrir(!conta.classList.contains("aberta"));
  });

  document.addEventListener("click", function (e) {
    if (!conta.contains(e.target)) abrir(false);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") abrir(false);
  });
})();

// Dado sensível sob demanda: nome do paciente (data-paciente) ou texto livre que
// pode citá-lo (data-revelar="<url>"). A página traz só a máscara; o clique busca
// o valor (a rota confere permissão e registra quem viu); outro clique mascara.
(function () {
  document.addEventListener("click", function (e) {
    var botao = e.target.closest("[data-paciente],[data-revelar]");
    if (!botao) return;
    e.preventDefault();
    e.stopPropagation();
    var mascara = botao.dataset.mascara || "*****";
    if (botao.dataset.revelado) {
      botao.textContent = mascara;
      delete botao.dataset.revelado;
      botao.title = "Clique para ver";
      return;
    }
    var url = botao.dataset.revelar || "/pacientes/nome?codigo=" + encodeURIComponent(botao.dataset.paciente);
    botao.disabled = true;
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { botao.title = res.j.erro || "Não foi possível ver"; return; }
        botao.textContent = res.j.nome || res.j.texto || "(não encontrado)";
        botao.dataset.revelado = "1";
        botao.title = "Clique para ocultar";
      })
      .catch(function () { botao.title = "Não foi possível ver"; })
      .then(function () { botao.disabled = false; });
  });
})();
