// Mapa semantico: as tabelas posicionadas por significado, na GPU.
//
// O layout NAO vem do servidor. O Postgres manda quem e vizinho de quem
// (src/mapa.py) e a forca do cosmos.gl decide onde cada ponto para. Blocos de
// assunto emergem dai -- ninguem os desenhou.
//
// Escolha de encoding, e por que: sao 16 assuntos, muito acima do que uma escala
// categorica aguenta distinguir (o teto seguro sao 3 cores). Entao quem separa os
// temas e a POSICAO (setPointClusters) e quem os identifica e o NOME escrito
// sobre o bloco. A cor inteira sobra para as arestas, que carregam as outras duas
// perguntas da pagina: FK sem parentesco, e duplicata.
import { Graph } from 'https://esm.sh/@cosmograph/cosmos@3.4.1?bundle';

const alvo = document.getElementById('mapa');
if (alvo) iniciar();

// Tokens do ds_opalus resolvidos aqui porque o cosmos desenha em WebGL: o canvas
// nao le var(--...). Validados contra a superficie branca (ΔE de CVD e de visao
// normal acima do piso, os tres pares).
const COR = {
  ponto: '#2f4e6f',       // navy-600
  sim: '#c3cbd6',         // grey-300  -- o tecido de fundo
  ambos: '#009597',       // teal-500  -- FK que o significado confirma
  fk: '#c98a12',          // amber-500 -- FK SEM parentesco
  gemea: '#c0392f',       // red-500   -- o mesmo conceito duas vezes
};

// Aresta de parentesco e a maioria (777 de 926) e serve de fundo; as outras tres
// sao o achado e precisam saltar. Opacidade e espessura andam juntas com a cor.
const PESO = { sim: 0.35, ambos: 1.4, fk: 1.6, gemea: 2.2 };

function iniciar() {
  const estado = document.getElementById('mapa-estado');
  const aviso = (texto) => { if (estado) estado.textContent = texto; };

  // O recorte esta na URL da pagina; o JSON tem de ver o mesmo. `q` e o termo da
  // busca semantica: com ele o mapa desenha so as tabelas que a busca trouxe.
  const atual = new URLSearchParams(location.search);
  const parametros = new URLSearchParams();
  ['q', 'topk', 'excluir', 'provedor'].forEach((chave) => {
    const valor = atual.get(chave);
    if (valor) parametros.set(chave, valor);
  });
  const url = '/oracle/mapa.json' + (parametros.toString() ? '?' + parametros : '');

  // Sem termo nao busca nada. Sao duas razoes: a chamada de embedding e paga, e o
  // mapa do schema inteiro e um kNN all-pairs sobre as 1.649 tabelas vetorizadas
  // -- medido em 72 segundos, contra 11 do mapa de 50 tabelas da busca.
  if (!atual.get('q')) {
    return aviso('Busque acima para desenhar o mapa das tabelas que casarem.');
  }

  fetch(url)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((dados) => {
      if (!dados.nodes.length) {
        return aviso(dados.meta && dados.meta.termo
          ? 'A busca nao trouxe nenhuma tabela vetorizada.'
          : 'Nenhuma tabela vetorizada neste recorte.');
      }
      montar(dados);
      tabelaGemeas(dados.gemeas);
      tabelaTemas(dados.temas);
    })
    .catch((e) => aviso('Não conseguimos carregar o mapa (' + e + ').'));
}

function montar(dados) {
  const estado = document.getElementById('mapa-estado');
  const dica = document.getElementById('mapa-dica');
  const camadaTemas = document.getElementById('mapa-temas');

  // As arestas do cosmos referenciam INDICE, nao nome -- e o indice e a posicao
  // no array de nos, que o servidor ja devolve em ordem estavel.
  const indice = new Map(dados.nodes.map((no, i) => [no.nome, i]));

  const posicoes = new Float32Array(dados.nodes.length * 2);
  const tamanhos = new Float32Array(dados.nodes.length);
  // Semear em circulo, e nao no centro: pontos empilhados no mesmo pixel dao
  // repulsao infinita e o grafo explode no primeiro tick.
  dados.nodes.forEach((no, i) => {
    const angulo = (i / dados.nodes.length) * Math.PI * 2;
    posicoes[i * 2] = 2048 + Math.cos(angulo) * 900;
    posicoes[i * 2 + 1] = 2048 + Math.sin(angulo) * 900;
    // sqrt e nao linear: dependentes vai de 0 a dezenas, e escala linear faria o
    // hub virar um disco que engole os vizinhos.
    tamanhos[i] = 3 + Math.sqrt(no.dependentes) * 2.2;
  });

  const arestas = new Float32Array(dados.edges.length * 2);
  const cores = new Float32Array(dados.edges.length * 4);
  const larguras = new Float32Array(dados.edges.length);
  dados.edges.forEach((aresta, i) => {
    arestas[i * 2] = indice.get(aresta.origem);
    arestas[i * 2 + 1] = indice.get(aresta.destino);
    const [r, g, b] = rgb(COR[aresta.tipo]);
    cores[i * 4] = r;
    cores[i * 4 + 1] = g;
    cores[i * 4 + 2] = b;
    cores[i * 4 + 3] = aresta.tipo === 'sim' ? 0.5 : 0.9;
    larguras[i] = PESO[aresta.tipo];
  });

  const grafo = new Graph(alvo, {
    backgroundColor: '#ffffff',
    spaceSize: 4096,
    pointDefaultColor: COR.ponto,
    pointOpacity: 0.9,
    renderHoveredPointRing: true,
    hoveredPointRingColor: '#1a2a3e',
    hoveredPointCursor: 'pointer',
    linkWidthScale: 1,
    linkOpacity: 1,
    curvedLinks: false,
    // A forca de cluster e o que transforma o tema em bloco visivel; sem ela o
    // layout so evita sobreposicao e os assuntos ficam misturados.
    simulationCluster: 0.35,
    simulationRepulsion: 0.6,
    simulationLinkSpring: 1.2,
    // Escala com o tamanho do grafo. O 8 foi calibrado com o schema inteiro
    // (~1.650 nos) e continua valendo la -- 400/sqrt(1650) da 9,8. O que ele nao
    // aguenta e o regime da busca: 50 nos, todos parecidos entre si por
    // construcao, contraiam ate virar um ponto. 400/sqrt(50) da 57.
    simulationLinkDistance: Math.max(8, 400 / Math.sqrt(dados.nodes.length)),
    simulationGravity: 0.15,
    simulationFriction: 0.85,
    fitViewOnInit: true,
    fitViewPadding: 0.2,
    onSimulationEnd: () => {
      grafo.fitView();
      if (estado) estado.textContent = 'Arraste para navegar · clique num nó para abrir a tabela.';
    },
    onPointMouseOver: (i, pos) => mostrarDica(dica, dados.nodes[i], pos),
    onPointMouseOut: () => { dica.hidden = true; },
    onPointClick: (i) => {
      location.href = '/oracle/objetos/' + encodeURIComponent(dados.nodes[i].nome);
    },
  });

  grafo.setPointPositions(posicoes);
  grafo.setPointSizes(tamanhos);
  grafo.setPointClusters(dados.nodes.map((no) => no.tema));
  grafo.setLinks(arestas);
  grafo.setLinkColors(cores);
  grafo.setLinkWidths(larguras);
  grafo.render();
  if (estado) estado.textContent = 'Acomodando os blocos…';

  // Reenquadrar no relogio: fitViewOnInit enquadra o circulo de 900 de raio da
  // semeadura, e o layout so encontra a extensao real depois de acomodar. O
  // onSimulationEnd nao serve para isto -- medido, ele nao dispara neste cosmos.
  [1500, 5000].forEach((ms) => setTimeout(() => {
    grafo.fitView();
    if (estado) estado.textContent = 'Arraste para navegar · clique num nó para abrir a tabela.';
  }, ms));

  rotularTemas(grafo, dados, camadaTemas);
}

// --------------------------------------------------------------------------
// Rotulo dos temas: o nome do assunto flutuando sobre o centro do bloco
// --------------------------------------------------------------------------

function rotularTemas(grafo, dados, camada) {
  if (!camada) return;

  const porTema = new Map();
  dados.nodes.forEach((no, i) => {
    if (!porTema.has(no.tema)) porTema.set(no.tema, []);
    porTema.get(no.tema).push(i);
  });

  // Bloco de uma ou duas tabelas nao e um assunto, e o rotulo dele so competiria
  // por espaco com os que sao.
  const nomeDoTema = new Map(dados.temas.map((t) => [t.id, t]));
  const desenhaveis = [...porTema.entries()].filter(([, ids]) => ids.length >= 3);

  const elementos = new Map();
  desenhaveis.forEach(([tema]) => {
    const el = document.createElement('span');
    el.className = 'ds-mapa-tema';
    el.textContent = (nomeDoTema.get(tema) || {}).nome || '';
    camada.appendChild(el);
    elementos.set(tema, el);
  });

  // Acompanha o layout enquanto ele se acomoda e o usuario navega. Ler 230
  // posicoes por quadro e barato; o custo real estaria em recriar os elementos.
  function acompanhar() {
    // O init do cosmos e assincrono: nos primeiros quadros o buffer de posicoes
    // ainda nao existe, e o centroide sairia NaN.
    const pos = grafo.getPointPositions();
    if (!pos || pos.length < dados.nodes.length * 2) {
      requestAnimationFrame(acompanhar);
      return;
    }
    desenhaveis.forEach(([tema, ids]) => {
      let x = 0;
      let y = 0;
      ids.forEach((i) => { x += pos[i * 2]; y += pos[i * 2 + 1]; });
      const [ex, ey] = grafo.spaceToScreenPosition([x / ids.length, y / ids.length]);
      const el = elementos.get(tema);
      el.style.transform = `translate(${Math.round(ex)}px, ${Math.round(ey)}px) translate(-50%, -50%)`;
    });
    requestAnimationFrame(acompanhar);
  }
  requestAnimationFrame(acompanhar);
}

function mostrarDica(dica, no, pos) {
  if (!dica || !no) return;
  dica.innerHTML =
    `<strong>${escapar(no.rotulo)}</strong>` +
    `<span class="mono">${escapar(no.nome)}</span>` +
    `<span>${no.dependentes} dependentes · ${no.dependencias} dependências</span>`;
  dica.hidden = false;
  if (pos) {
    dica.style.left = Math.round(pos[0]) + 'px';
    dica.style.top = Math.round(pos[1]) + 'px';
  }
}

// --------------------------------------------------------------------------
// As duas tabelas abaixo do mapa
//
// Elas nao sao enfeite: a cor de aresta amarela fica abaixo de 3:1 sobre o
// branco, e a regra de alivio pede que o mesmo dado exista em forma de texto.
// --------------------------------------------------------------------------

function tabelaGemeas(gemeas) {
  const destino = document.getElementById('mapa-gemeas');
  if (!destino) return;
  if (!gemeas.length) {
    destino.innerHTML = '<p class="ds-vazio">Nenhum par acima de 0,95 neste recorte.</p>';
    return;
  }
  const linhas = gemeas.map((g) => `
    <tr>
      <td><a href="/oracle/objetos/${encodeURIComponent(g.a)}" class="mono">${escapar(g.a)}</a></td>
      <td><a href="/oracle/objetos/${encodeURIComponent(g.b)}" class="mono">${escapar(g.b)}</a></td>
      <td class="num">${g.cos.toFixed(4).replace('.', ',')}</td>
    </tr>`).join('');
  destino.innerHTML = `
    <div class="ds-table-wrap">
      <table class="ds-table">
        <thead><tr><th>Tabela</th><th>Quase igual a</th><th class="num">Similaridade</th></tr></thead>
        <tbody>${linhas}</tbody>
      </table>
    </div>`;
}

function tabelaTemas(temas) {
  const destino = document.getElementById('mapa-lista-temas');
  if (!destino) return;
  const linhas = [...temas]
    .sort((a, b) => b.tamanho - a.tamanho)
    .map((t) => `
      <tr>
        <td>${escapar(t.nome)}</td>
        <td><a href="/oracle/objetos/${encodeURIComponent(t.tabela)}" class="mono">${escapar(t.tabela)}</a></td>
        <td class="num">${t.tamanho}</td>
      </tr>`).join('');
  destino.innerHTML = `
    <table class="ds-table">
      <thead><tr><th>Assunto</th><th>Tabela mais central</th><th class="num">Tabelas</th></tr></thead>
      <tbody>${linhas}</tbody>
    </table>`;
}

// --------------------------------------------------------------------------

function rgb(hex) {
  return [
    parseInt(hex.slice(1, 3), 16) / 255,
    parseInt(hex.slice(3, 5), 16) / 255,
    parseInt(hex.slice(5, 7), 16) / 255,
  ];
}

function escapar(texto) {
  const d = document.createElement('div');
  d.textContent = texto == null ? '' : texto;
  return d.innerHTML;
}
