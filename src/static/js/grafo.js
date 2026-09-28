// Visao Grafo: comeca pelos hubs e cresce a cada clique.
//
// O grafo inteiro (209 nos) ja vem no primeiro fetch, entao expandir e recolher
// acontece em memoria -- clicar nao volta ao servidor.
(function () {
  const alvo = document.getElementById('grafo');
  if (!alvo || typeof cytoscape === 'undefined') return;

  const estado = document.getElementById('grafo-estado');
  const aviso = (texto) => { if (estado) estado.textContent = texto; };

  fetch('/oracle/grafo.json')
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((dados) => montar(dados))
    .catch((e) => aviso('Não conseguimos carregar o grafo (' + e + ').'));

  function montar(dados) {
    const porId = new Map(dados.nodes.map((n) => [n.data.id, n]));
    // Lista de adjacencia nas duas direcoes: expandir mostra quem aponta para o
    // no E para quem ele aponta
    const vizinhos = new Map();
    const ligar = (a, b) => {
      if (!vizinhos.has(a)) vizinhos.set(a, new Set());
      vizinhos.get(a).add(b);
    };
    dados.edges.forEach(({ data }) => {
      ligar(data.source, data.target);
      ligar(data.target, data.source);
    });

    const sementes = new Set(dados.sementes);
    const expandidos = new Set();

    function visiveis() {
      const set = new Set(sementes);
      expandidos.forEach((id) => (vizinhos.get(id) || []).forEach((v) => set.add(v)));
      return set;
    }

    const cy = cytoscape({
      container: alvo,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(rotulo)',
            'font-size': 9,
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': 90,
            color: '#fff',
            'background-color': '#233751',
            width: 'mapData(dependentes, 0, 40, 26, 90)',
            height: 'mapData(dependentes, 0, 40, 26, 90)',
          },
        },
        { selector: 'node.semente', style: { 'background-color': '#004e84' } },
        {
          selector: 'node.aberto',
          style: { 'background-color': '#00afb9', 'border-width': 3, 'border-color': '#233751' },
        },
        {
          selector: 'edge',
          style: {
            width: 1.2,
            'line-color': '#96b4d6',
            'target-arrow-color': '#96b4d6',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.7,
            'curve-style': 'bezier',
          },
        },
      ],
    });

    function desenhar() {
      const set = visiveis();
      const nos = [...set].map((id) => porId.get(id)).filter(Boolean);
      const arestas = dados.edges.filter(
        (e) => set.has(e.data.source) && set.has(e.data.target)
      );

      cy.elements().remove();
      cy.add(nos.concat(arestas));
      cy.nodes().forEach((n) => {
        n.toggleClass('semente', sementes.has(n.id()));
        n.toggleClass('aberto', expandidos.has(n.id()));
      });
      cy.layout({ name: 'cose', animate: false, nodeRepulsion: 9000, idealEdgeLength: 90 }).run();

      aviso(
        nos.length + ' de ' + dados.nodes.length + ' tabelas na tela · ' +
        arestas.length + ' relacionamentos · clique num nó para abrir ou fechar a árvore dele'
      );
    }

    cy.on('tap', 'node', (evt) => {
      const id = evt.target.id();
      expandidos.has(id) ? expandidos.delete(id) : expandidos.add(id);
      desenhar();
    });

    const botao = document.getElementById('grafo-recolher');
    if (botao) botao.addEventListener('click', () => { expandidos.clear(); desenhar(); });

    desenhar();
  }
})();
