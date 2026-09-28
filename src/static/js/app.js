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
