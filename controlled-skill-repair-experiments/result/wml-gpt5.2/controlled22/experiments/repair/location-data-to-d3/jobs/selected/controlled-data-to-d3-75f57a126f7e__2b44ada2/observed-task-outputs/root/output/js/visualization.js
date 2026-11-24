/* global d3 */

(function () {
  const DATA_PATH = 'data/stock-descriptions.csv';

  const bubbleSvg = d3.select('#bubble-svg');
  const legendEl = d3.select('#legend');
  const tooltip = d3.select('#tooltip');
  const bubbleContainerEl = document.getElementById('bubble-container');

  const DEFAULT_WIDTH = 780;
  const DEFAULT_HEIGHT = 640;

  let selectedTicker = null;

  function normalizeRow(d) {
    const ticker = (d.ticker || '').trim();
    const name = (d['full name'] || '').trim();
    const sector = (d.sector || '').trim();

    const marketCapRaw = (d.marketCap == null ? '' : String(d.marketCap)).trim();
    const marketCap = marketCapRaw === '' ? null : +marketCapRaw;

    const country = (d.country || '').trim();
    const website = (d.website || '').trim();

    const isETF = !(Number.isFinite(marketCap) && marketCap > 0);

    return {
      ticker,
      name,
      sector,
      marketCap: isETF ? null : marketCap,
      isETF,
      country,
      website,
      hasTooltipData: Boolean(ticker) && Boolean(name) && Boolean(sector) && !isETF
    };
  }

  function formatMarketCap(n) {
    if (!Number.isFinite(n) || n <= 0) return '—';

    const abs = Math.abs(n);
    const fmt = (value, suffix) => {
      const a = Math.abs(value);
      let digits = 2;
      if (a >= 100) digits = 0;
      else if (a >= 10) digits = 1;
      let s = value.toFixed(digits);
      s = s.replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1');
      return `${s}${suffix}`;
    };

    if (abs >= 1e12) return fmt(n / 1e12, 'T');
    if (abs >= 1e9) return fmt(n / 1e9, 'B');
    if (abs >= 1e6) return fmt(n / 1e6, 'M');
    if (abs >= 1e3) return fmt(n / 1e3, 'K');
    return String(Math.round(n));
  }

  function setSelectedKey(ticker) {
    const next = selectedTicker === ticker ? null : ticker;
    selectedTicker = next;
    renderSelection();
  }

  function renderSelection() {
    d3.selectAll('circle.bubble')
      .classed('selected', d => d.ticker === selectedTicker);

    const rows = d3.selectAll('#data-table tbody tr');
    rows.classed('selected', d => d.ticker === selectedTicker);

    if (selectedTicker) {
      const row = rows.filter(d => d.ticker === selectedTicker).node();
      if (row) row.scrollIntoView({ block: 'nearest' });
    }
  }

  function buildLegend(sectors, color) {
    legendEl.selectAll('*').remove();

    const items = legendEl
      .selectAll('div.legend-item')
      .data(sectors, d => d)
      .join('div')
      .attr('class', 'legend-item');

    items.append('span')
      .attr('class', 'legend-swatch')
      .style('background', d => color(d));

    items.append('span')
      .text(d => d);
  }

  function buildTable(data) {
    const tbody = d3.select('#data-table tbody');

    const rows = tbody
      .selectAll('tr')
      .data(data, d => d.ticker)
      .join('tr')
      .on('click', (event, d) => setSelectedKey(d.ticker));

    rows.selectAll('td')
      .data(d => ([
        { key: 'ticker', value: d.ticker, className: '' },
        { key: 'name', value: d.name, className: '' },
        { key: 'sector', value: d.sector, className: '' },
        { key: 'marketCap', value: formatMarketCap(d.marketCap), className: 'num' }
      ]), d => d.key)
      .join('td')
      .attr('class', d => d.className)
      .text(d => d.value);

    return rows;
  }

  function makePalette(n) {
    const palettes = [
      d3.schemeTableau10,
      d3.schemeSet3,
      d3.schemePaired,
      d3.schemeSet2,
      d3.schemeCategory10
    ];

    const colors = [];
    for (const p of palettes) {
      for (const c of p) colors.push(c);
    }

    if (colors.length >= n) return colors.slice(0, n);

    while (colors.length < n) {
      colors.push(colors[colors.length % palettes[0].length]);
    }
    return colors;
  }

  function showTooltip(event, d) {
    tooltip
      .classed('visible', true)
      .attr('aria-hidden', 'false')
      .html(
        `<div class="tt-title">${d.ticker}</div>` +
        `<div class="tt-sub">${d.name}</div>` +
        `<div class="tt-sub">Sector: ${d.sector}</div>`
      );
    moveTooltip(event);
  }

  function moveTooltip(event) {
    const pad = 12;
    const { clientX, clientY } = event;

    const rect = bubbleContainerEl.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;

    tooltip
      .style('left', `${x + pad}px`)
      .style('top', `${y + pad}px`);
  }

  function hideTooltip() {
    tooltip
      .classed('visible', false)
      .attr('aria-hidden', 'true');
  }

  function renderBubbleChart(data) {
    const width = DEFAULT_WIDTH;
    const height = DEFAULT_HEIGHT;

    bubbleSvg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    bubbleSvg.selectAll('*').remove();

    const sectors = Array.from(new Set(data.map(d => d.sector))).sort(d3.ascending);

    const color = d3.scaleOrdinal()
      .domain(sectors)
      .range(makePalette(sectors.length));

    buildLegend(sectors, color);

    const caps = data.map(d => d.marketCap).filter(d => Number.isFinite(d));
    const capMin = d3.min(caps);
    const capMax = d3.max(caps);

    const rScale = d3.scaleSqrt()
      .domain([capMin || 1, capMax || 1])
      .range([12, 48]);

    const etfRadius = 14;

    // Deterministic node order for stable layout.
    const nodes = data
      .slice()
      .sort((a, b) => d3.ascending(a.ticker, b.ticker))
      .map((d, i) => {
        const r = d.isETF ? etfRadius : rScale(d.marketCap);
        return {
          ...d,
          r,
          x: (width / 2) + ((i % 10) - 5) * 8,
          y: (height / 2) + ((Math.floor(i / 10) % 5) - 2) * 10,
          vx: 0,
          vy: 0
        };
      });

    const cx = width / 2;
    const cy = height / 2;
    const ring = Math.min(width, height) * 0.22;

    const sectorCenters = new Map();
    sectors.forEach((s, i) => {
      const angle = (2 * Math.PI * i) / sectors.length;
      sectorCenters.set(s, {
        x: cx + ring * Math.cos(angle),
        y: cy + ring * Math.sin(angle)
      });
    });

    const simulation = d3.forceSimulation(nodes)
      .force('center', d3.forceCenter(cx, cy))
      .force('charge', d3.forceManyBody().strength(-4))
      .force('x', d3.forceX(d => sectorCenters.get(d.sector).x).strength(0.13))
      .force('y', d3.forceY(d => sectorCenters.get(d.sector).y).strength(0.13))
      .force('collide', d3.forceCollide(d => d.r + 1).iterations(2))
      .stop();

    // Fixed tick count => deterministic layout.
    for (let i = 0; i < 350; i += 1) simulation.tick();

    const root = bubbleSvg.append('g');

    const node = root
      .selectAll('g.node')
      .data(nodes, d => d.ticker)
      .join(enter => {
        const g = enter.append('g').attr('class', 'node');

        g.append('circle')
          .attr('class', 'bubble')
          .attr('r', d => d.r)
          .attr('fill', d => color(d.sector))
          .attr('fill-opacity', d => (d.isETF ? 0.55 : 0.80));

        g.append('text')
          .attr('class', 'bubble-label')
          .attr('text-anchor', 'middle')
          .attr('dy', '0.35em')
          .text(d => d.ticker);

        return g;
      });

    node
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .on('mouseover', (event, d) => {
        if (!d.hasTooltipData) return;
        showTooltip(event, d);
      })
      .on('mousemove', (event, d) => {
        if (!d.hasTooltipData) return;
        moveTooltip(event);
      })
      .on('mouseout', () => hideTooltip())
      .on('click', (event, d) => setSelectedKey(d.ticker));

    renderSelection();
  }

  async function loadStockDescriptions() {
    try {
      return await d3.csv(DATA_PATH, normalizeRow);
    } catch (err) {
      const inline = document.getElementById('stock-descriptions-inline');
      const text = inline ? inline.textContent : '';
      if (text && text.trim() !== '' && !text.includes('__INLINE_STOCK_DESCRIPTIONS_CSV__')) {
        return d3.csvParse(text, normalizeRow);
      }
      throw err;
    }
  }

  async function main() {
    let raw;
    try {
      raw = await loadStockDescriptions();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err);
      d3.select('#app')
        .insert('div', ':first-child')
        .style('padding', '14px')
        .style('color', 'rgba(232,238,252,0.9)')
        .text('Failed to load stock-descriptions.csv. If you opened index.html via file://, use the inline data block or serve this folder with a local web server.');
      return;
    }

    const data = raw
      .filter(d => d.ticker !== '')
      .sort((a, b) => d3.ascending(a.ticker, b.ticker));

    buildTable(data);
    renderBubbleChart(data);
  }

  main();
})();
