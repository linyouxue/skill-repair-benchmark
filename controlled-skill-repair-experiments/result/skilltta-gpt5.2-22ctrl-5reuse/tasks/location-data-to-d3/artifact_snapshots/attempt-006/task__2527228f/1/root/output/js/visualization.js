(() => {
  const DATA_URL = 'data/stock-descriptions.csv';

  const state = {
    selectedTicker: null,
    nodes: [],
    sectors: [],
    color: null,
    simulation: null,
  };

  function isMissing(x) {
    return x === null || x === undefined || x === '' || (typeof x === 'number' && !Number.isFinite(x));
  }

  function formatMarketCap(n) {
    if (!Number.isFinite(n)) return '—';

    const abs = Math.abs(n);
    const fmt = (value, suffix, digits) => {
      const s = value.toFixed(digits);
      const trimmed = s.replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1');
      return `${trimmed}${suffix}`;
    };

    if (abs >= 1e12) return fmt(n / 1e12, 'T', abs >= 1e13 ? 1 : 2);
    if (abs >= 1e9) return fmt(n / 1e9, 'B', abs >= 1e10 ? 1 : 2);
    if (abs >= 1e6) return fmt(n / 1e6, 'M', abs >= 1e7 ? 1 : 2);
    if (abs >= 1e3) return fmt(n / 1e3, 'K', abs >= 1e4 ? 1 : 2);
    return String(Math.round(n));
  }

  function parseRow(d) {
    const marketCap = d.marketCap === '' ? NaN : +d.marketCap;
    const sector = d.sector;

    const etf = sector === 'ETF' || !Number.isFinite(marketCap);

    return {
      ticker: d.ticker,
      sector,
      fullName: d['full name'],
      marketCap: Number.isFinite(marketCap) ? marketCap : null,
      isETF: etf,
    };
  }

  async function loadStockDescriptions() {
    try {
      return await d3.csv(DATA_URL, parseRow);
    } catch (err) {
      const embedded = document.getElementById('embedded-stock-descriptions');
      if (!embedded) throw err;
      const text = embedded.textContent.trim();
      return d3.csvParse(text, parseRow);
    }
  }

  function computeSectorTargets(sectors, width, height) {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.22;

    const targets = new Map();
    sectors.forEach((s, i) => {
      const angle = (i / sectors.length) * Math.PI * 2 - Math.PI / 2;
      targets.set(s, {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      });
    });

    return targets;
  }

  function setSelected(ticker) {
    state.selectedTicker = ticker;

    d3.selectAll('.node')
      .classed('selected', d => d.ticker === ticker);

    d3.selectAll('tbody tr')
      .classed('selected', function (d) {
        return d && d.ticker === ticker;
      });

    if (ticker) {
      const row = d3.select(`tbody tr[data-ticker="${ticker}"]`);
      if (!row.empty()) {
        const scroller = document.querySelector('.table-scroller');
        row.node().scrollIntoView({ block: 'nearest' });
        if (scroller) scroller.focus?.();
      }
    }
  }

  function renderLegend(containerSel) {
    const container = d3.select(containerSel);
    container.selectAll('*').remove();

    const items = container
      .selectAll('.legend-item')
      .data(state.sectors)
      .enter()
      .append('div')
      .attr('class', 'legend-item');

    items
      .append('span')
      .attr('class', 'legend-swatch')
      .style('background', d => state.color(d));

    items
      .append('span')
      .text(d => d);
  }

  function renderTable(containerSel) {
    const container = d3.select(containerSel);
    container.selectAll('*').remove();

    const wrap = container.append('div').attr('class', 'table-scroller').attr('tabindex', '0');

    const table = wrap.append('table');

    table.append('thead').append('tr')
      .selectAll('th')
      .data(['Ticker symbol', 'Full company name', 'Sector', 'Market cap'])
      .enter()
      .append('th')
      .text(d => d);

    const tbody = table.append('tbody');

    const rows = tbody
      .selectAll('tr')
      .data(state.nodes, d => d.ticker)
      .enter()
      .append('tr')
      .attr('data-ticker', d => d.ticker)
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelected(d.ticker);
      });

    rows.append('td').attr('class', 'ticker').text(d => d.ticker);
    rows.append('td').text(d => d.fullName);
    rows.append('td').attr('class', 'muted').text(d => d.sector);
    rows.append('td').text(d => formatMarketCap(d.marketCap));
  }

  function renderBubbleChart(svgSel, tooltipSel) {
    const svg = d3.select(svgSel);

    const width = 700;
    const height = 520;

    svg
      .attr('viewBox', [0, 0, width, height])
      .attr('role', 'img')
      .attr('aria-label', 'Bubble chart of stocks clustered by sector');

    svg.selectAll('*').remove();

    const tooltip = d3.select(tooltipSel);

    const nonEtfCaps = state.nodes
      .filter(d => !d.isETF && Number.isFinite(d.marketCap))
      .map(d => d.marketCap);

    const minCap = d3.min(nonEtfCaps);
    const maxCap = d3.max(nonEtfCaps);

    const rScale = d3.scaleSqrt()
      .domain([minCap || 1, maxCap || 1])
      .range([12, 48]);

    state.nodes.forEach(d => {
      d.r = d.isETF ? 14 : rScale(d.marketCap);
    });

    const targets = computeSectorTargets(state.sectors, width, height);

    const g = svg.append('g');

    svg.on('click', () => setSelected(null));

    const node = g
      .selectAll('.node')
      .data(state.nodes, d => d.ticker)
      .enter()
      .append('g')
      .attr('class', d => `node${d.isETF ? ' is-etf' : ''}`)
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelected(d.ticker);
      })
      .on('mouseover', (event, d) => {
        if (d.isETF) return;
        tooltip
          .style('opacity', 1)
          .html(
            `<p class="t">${d.ticker}</p>` +
            `<p class="row">${d.fullName}</p>` +
            `<p class="row">Sector: ${d.sector}</p>`
          );
      })
      .on('mousemove', (event, d) => {
        if (d.isETF) return;
        const [x, y] = d3.pointer(event, document.getElementById('bubble-wrap'));
        tooltip
          .style('left', `${x}px`)
          .style('top', `${y}px`);
      })
      .on('mouseout', (event, d) => {
        if (d.isETF) return;
        tooltip.style('opacity', 0);
      });

    node.append('circle')
      .attr('r', d => d.r)
      .attr('fill', d => state.color(d.sector));

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .style('font-size', d => `${Math.max(9, Math.min(14, d.r * 0.55))}px`)
      .text(d => d.ticker);

    state.simulation = d3.forceSimulation(state.nodes)
      .force('x', d3.forceX(d => targets.get(d.sector).x).strength(0.28))
      .force('y', d3.forceY(d => targets.get(d.sector).y).strength(0.28))
      .force('collide', d3.forceCollide(d => d.r + 1.4).strength(1))
      .force('charge', d3.forceManyBody().strength(-10))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .alpha(1)
      .alphaDecay(0.03)
      .on('tick', () => {
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
  }

  async function main() {
    const data = await loadStockDescriptions();

    state.nodes = data
      .filter(d => d.ticker)
      .sort((a, b) => d3.ascending(a.ticker, b.ticker));

    state.sectors = Array.from(new Set(state.nodes.map(d => d.sector)));

    state.color = d3.scaleOrdinal()
      .domain(state.sectors)
      .range(d3.schemeTableau10.slice(0, state.sectors.length));

    const metaBubble = document.getElementById('meta-bubble');
    const metaTable = document.getElementById('meta-table');
    if (metaBubble) metaBubble.textContent = `${state.nodes.length} tickers across ${state.sectors.length} sectors`;
    if (metaTable) metaTable.textContent = `${state.nodes.length} rows`;

    renderLegend('#legend');
    renderTable('#table-container');
    renderBubbleChart('#bubble-svg', '#tooltip');

    setSelected(null);
  }

  window.addEventListener('DOMContentLoaded', () => {
    main().catch(err => {
      // Last-resort failure message for file:// loading issues.
      const el = document.getElementById('fatal');
      if (el) {
        el.textContent = `Failed to load data: ${err?.message || err}`;
        el.style.display = 'block';
      }
      // eslint-disable-next-line no-console
      console.error(err);
    });
  });
})();
