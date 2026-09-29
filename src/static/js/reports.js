/* Desenha os gráficos dos /reports.
 *
 * Cada bloco escreve <canvas data-grafico="d-<slug>"> e, ao lado, um
 * <script type="application/json" id="d-<slug>"> com a especificação montada em
 * src/reports/comum.py:grafico():
 *   {tipo: barras|barras-h|barras-linha|rosca|cascata, rotulos: [...],
 *    series: [{nome, valores, tom|tons, tipo?: "linha", eixo?: "pct"}],
 *    formato: moeda|int|pct, empilhado?: bool, gradiente?: bool,
 *    passos?: ["total"|"neg"|"pos", ...]}   <- só na cascata
 * Sem JS o canvas some e a tabela do bloco continua de pé.
 */
(function () {
  "use strict";

  if (typeof Chart === "undefined") return;

  var css = getComputedStyle(document.documentElement);
  function cor(nome, reserva) {
    return (css.getPropertyValue(nome) || "").trim() || reserva;
  }

  var TONS = {
    blue: cor("--vivid-blue", "#1463f3"),
    teal: cor("--vivid-teal", "#00c2a8"),
    violet: cor("--vivid-violet", "#7b3fe4"),
    coral: cor("--vivid-coral", "#f2545b"),
    amber: cor("--vivid-amber", "#f5a524"),
    magenta: cor("--vivid-magenta", "#d63384"),
    cyan: cor("--vivid-cyan", "#00b4d8"),
    green: cor("--vivid-green", "#1db954"),
    navy: cor("--navy-600", "#2f4e6f"),
    neutral: cor("--grey-400", "#95a0af"),
    success: cor("--vivid-teal", "#00c2a8"),
    info: cor("--vivid-blue", "#1463f3"),
    warning: cor("--vivid-amber", "#f5a524"),
    danger: cor("--vivid-coral", "#f2545b"),
  };
  var SEQUENCIA = ["blue", "teal", "violet", "amber", "coral", "cyan", "magenta", "green"];
  var EIXO = cor("--grey-500", "#6b7787");
  var GRADE = cor("--grey-100", "#eceff3");

  Chart.defaults.font.family = cor("--font-ui", "system-ui, sans-serif");
  Chart.defaults.font.size = 11;
  Chart.defaults.color = EIXO;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation.duration = 340;

  var BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  var INT = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  var DEC = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

  function curta(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return "R$ " + DEC.format(v / 1e9) + " bi";
    if (a >= 1e6) return "R$ " + DEC.format(v / 1e6) + " mi";
    if (a >= 1e3) return "R$ " + INT.format(v / 1e3) + " mil";
    return BRL.format(v);
  }

  function formatador(formato, cheio) {
    if (formato === "pct") return function (v) { return DEC.format(v) + "%"; };
    if (formato === "int") return function (v) { return INT.format(v); };
    return cheio ? function (v) { return BRL.format(v); } : curta;
  }

  function tom(nome, i) {
    return TONS[nome] || TONS[SEQUENCIA[i % SEQUENCIA.length]];
  }

  function alfa(hex, a) {
    var h = hex.replace("#", "");
    if (h.length === 3) h = h.split("").map(function (c) { return c + c; }).join("");
    var n = parseInt(h, 16);
    return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
  }

  // Degradê ao longo da barra; recalculado quando o chartArea muda
  function degrade(base, horizontal) {
    return function (ctx) {
      var area = ctx.chart.chartArea;
      if (!area) return base;
      var g = horizontal
        ? ctx.chart.ctx.createLinearGradient(area.left, 0, area.right, 0)
        : ctx.chart.ctx.createLinearGradient(0, area.bottom, 0, area.top);
      g.addColorStop(0, alfa(base, 0.55));
      g.addColorStop(1, base);
      return g;
    };
  }

  function legenda(spec) {
    return spec.series.length > 1 || spec.tipo === "rosca";
  }

  function tooltip(spec) {
    var fmt = formatador(spec.formato, true);
    return {
      backgroundColor: cor("--navy-900", "#101b28"),
      padding: 12,
      cornerRadius: 10,
      titleFont: { weight: "700" },
      callbacks: {
        label: function (ctx) {
          var s = spec.series[ctx.datasetIndex] || {};
          var bruto = ctx.raw;
          var texto = s.eixo === "pct" ? DEC.format(bruto) + "%" : fmt(bruto);
          if (spec.tipo === "rosca") {
            var soma = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
            if (soma) texto += "  (" + DEC.format((bruto / soma) * 100) + "%)";
            return " " + ctx.label + ": " + texto;
          }
          return " " + (s.nome || "") + ": " + texto;
        },
      },
    };
  }

  function barras(spec, horizontal) {
    var fmt = formatador(spec.formato, false);
    var empilhado = !!spec.empilhado;
    var datasets = spec.series.map(function (s, i) {
      var base = tom(s.tom, i);
      if (s.tipo === "linha") {
        return {
          type: "line",
          label: s.nome,
          data: s.valores,
          borderColor: base,
          backgroundColor: base,
          borderWidth: 3,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: "#fff",
          pointBorderWidth: 2,
          tension: 0.35,
          yAxisID: "pct",
          order: 0,
        };
      }
      return {
        label: s.nome,
        data: s.valores,
        backgroundColor: spec.gradiente ? degrade(base, horizontal) : base,
        hoverBackgroundColor: base,
        borderRadius: empilhado ? 4 : 8,
        borderSkipped: false,
        maxBarThickness: horizontal ? 22 : 44,
        order: 1,
      };
    });

    var valor = {
      stacked: empilhado,
      beginAtZero: true,
      grid: { color: GRADE, drawTicks: false },
      border: { display: false },
      ticks: { callback: function (v) { return fmt(v); }, padding: 8 },
    };
    var categoria = {
      stacked: empilhado,
      grid: { display: false },
      border: { color: cor("--grey-300", "#c3cbd6"), width: 2 },
      ticks: {
        padding: 6,
        autoSkip: false,
        callback: function (v) {
          var r = this.getLabelForValue(v) || "";
          var lim = horizontal ? 26 : 16;
          return r.length > lim ? r.slice(0, lim - 1) + "…" : r;
        },
      },
    };

    var scales = horizontal ? { x: valor, y: categoria } : { x: categoria, y: valor };
    if (spec.series.some(function (s) { return s.eixo === "pct"; })) {
      scales.pct = {
        position: "right",
        beginAtZero: true,
        grid: { display: false },
        border: { display: false },
        ticks: { callback: function (v) { return DEC.format(v) + "%"; } },
      };
    }

    return {
      type: "bar",
      data: { labels: spec.rotulos, datasets: datasets },
      options: {
        indexAxis: horizontal ? "y" : "x",
        interaction: { mode: "index", intersect: false },
        scales: scales,
        plugins: {
          legend: {
            display: legenda(spec),
            position: "top",
            align: "start",
            labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 8, padding: 16 },
          },
          tooltip: tooltip(spec),
        },
      },
    };
  }

  function rosca(spec) {
    var s = spec.series[0];
    var cores = s.valores.map(function (_, i) { return tom((s.tons || [])[i], i); });
    return {
      type: "doughnut",
      data: {
        labels: spec.rotulos,
        datasets: [{ data: s.valores, backgroundColor: cores, borderColor: "#fff", borderWidth: 3, hoverOffset: 8 }],
      },
      options: {
        cutout: "66%",
        plugins: {
          legend: {
            position: "right",
            labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 8, padding: 10 },
          },
          tooltip: tooltip(spec),
        },
      },
    };
  }

  // Cascata: "total" é barra cheia desde o zero; "neg"/"pos" flutua a partir do
  // acumulado anterior. O tooltip mostra o tamanho do passo, não o intervalo.
  function cascata(spec) {
    var s = spec.series[0];
    var passos = spec.passos || [];
    var fmt = formatador(spec.formato, true);
    var acumulado = 0;
    var dados = [], cores = [];
    s.valores.forEach(function (v, i) {
      var passo = passos[i] || "total";
      if (passo === "total") {
        dados.push([0, v]); acumulado = v; cores.push(TONS.blue);
      } else if (passo === "neg" || passo === "saida") {
        // "saida" desce do acumulado como a perda, mas é dinheiro que entrou: verde
        dados.push([acumulado - v, acumulado]); acumulado -= v;
        cores.push(passo === "saida" ? TONS.teal : TONS.coral);
      } else {
        dados.push([acumulado, acumulado + v]); acumulado += v; cores.push(TONS.teal);
      }
    });
    return {
      type: "bar",
      data: { labels: spec.rotulos, datasets: [{ data: dados, backgroundColor: cores, borderRadius: 6,
                                                 borderSkipped: false, maxBarThickness: 64 }] },
      options: {
        scales: {
          x: { grid: { display: false }, border: { color: cor("--grey-300", "#c3cbd6"), width: 2 } },
          y: { beginAtZero: true, grid: { color: GRADE, drawTicks: false }, border: { display: false },
               ticks: { callback: function (v) { return curta(v); }, padding: 8 } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: cor("--navy-900", "#101b28"), padding: 12, cornerRadius: 10,
            callbacks: {
              label: function (ctx) {
                var par = ctx.raw;
                var valor = par[1] - par[0];
                var sinal = (passos[ctx.dataIndex] === "neg" || passos[ctx.dataIndex] === "saida") ? "− " : "";
                return " " + sinal + fmt(valor);
              },
            },
          },
        },
      },
    };
  }

  function desenhar(canvas) {
    var fonte = document.getElementById(canvas.dataset.grafico);
    if (!fonte) return;
    var spec;
    try { spec = JSON.parse(fonte.textContent); } catch (e) { return; }
    if (!spec || !spec.series || !spec.series.length) return;

    var config;
    if (spec.tipo === "rosca") config = rosca(spec);
    else if (spec.tipo === "cascata") config = cascata(spec);
    else config = barras(spec, spec.tipo === "barras-h");
    // Rosca estreita: legenda embaixo
    if (spec.tipo === "rosca" && canvas.parentElement.clientWidth < 460) {
      config.options.plugins.legend.position = "bottom";
    }
    new Chart(canvas, config);
  }

  document.querySelectorAll("canvas[data-grafico]").forEach(desenhar);
})();
