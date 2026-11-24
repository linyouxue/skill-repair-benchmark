/* global d3 */

(function () {
  const EMBEDDED = document.getElementById('stocks-json');
  const stocks = JSON.parse(EMBEDDED?.textContent ?? '[]');

  const bubbleContainer = d3.select('#bubble-chart');
  const legendContainer = d3.select('#legend');
  const tableContainer = d3.select('#table-container');
  const tooltip = d3.select('#tooltip');

  const state = { selectedTicker: null };

  function formatMarketCap(n) {
    if (n === null || n === undefined || !Number.isFinite(n)) return '—';

    const abs = Math.abs(n);
    const fmt2 = d3.format(',.2f');
    const fmt1 = d3.format(',.1f');

    if (abs >= 1e12) {
      const v = n / 1e12;
      return (Math.abs(v) < 10 ? fmt2(v) : fmt1(v)) + 'T';
    }
    if (abs >= 1e9) {
      const v = n / 1e9;
      return (Math.abs(v) < 10 ? fmt2(v) : fmt1(v)) + 'B';
    }
    if (abs >= 1e6) {
      const v = n / 1e6;
      return (Math.abs(v) < 10 ? fmt2(v) : fmt1(v)) + 'M';
    }
    if (abs >= 1e3) {
      const v = n / 1e3;
      return (Math.abs(v) < 10 ? fmt2(v) : fmt1(v)) + 'K';
    }
    return d3.format(',')(n);
  }

  function isEtfRow(d) {
    return d.marketCap === null;
  }

  function setTooltipVisible(visible) {
    tooltip.classed('is-visible', !!visible);
    if (!visible) {
      tooltip.style('transform', 'translate(-9999px, -9999px)');
    }
  }

  function moveTooltip(event) {
    const pad = 12;
    tooltip.style('transform', `translate(${event.pageX + pad}px, ${event.pageY + pad}px)`);
  }

  function showTooltip(event, d) {
    if (isEtfRow(d)) return;

    tooltip.html(
      `<div class="tooltip__ticker">${d.ticker}</div>` +
      `<div class="tooltip__name">${d.fullName}</div>` +
      `<div class="tooltip__sector">Sector: ${d.sector}</div>`
    );

    setTooltipVisible(true);
    moveTooltip(event);
  }

  function hideTooltip() {
    setTooltipVisible(false);
  }

  function setSelectedTicker(ticker) {
    state.selectedTicker = ticker;

    d3.selectAll('.node')
      .classed('is-selected', d => d.ticker === ticker);

    d3.selectAll('tr[data-ticker]')
      .classed('is-selected', function () {
        return this.getAttribute('data-ticker') === ticker;
      });

    const row = document.querySelector(`tr[data-ticker="${CSS.escape(ticker)}"]`);
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  function buildLegend(sectors, color) {
    const items = legendContainer
      .selectAll('.legend__item')
      .data(sectors, d => d);

    const enter = items.enter()
      .append('div')
      .attr('class', 'legend__item');

    enter.append('div')
      .attr('class', 'legend__swatch')
      .style('background', d => color(d));

    enter.append('div')
      .attr('class', 'legend__label')
      .text(d => d);

    items.exit().remove();
  }

  function computeSectorCenters(sectors, width, height) {
    const n = sectors.length;
    const cols = Math.ceil(Math.sqrt(n));
    const rows = Math.ceil(n / cols);

    const gridW = width * 0.86;
    const gridH = height * 0.80;
    const x0 = (width - gridW) / 2;
    const y0 = (height - gridH) / 2;

    const centers = new Map();
    sectors.forEach((s, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      centers.set(s, {
        x: x0 + (col + 0.5) * (gridW / cols),
        y: y0 + (row + 0.5) * (gridH / rows),
      });
    });
    return centers;
  }

  function buildBubbleChart(data) {
    bubbleContainer.selectAll('*').remove();

    const rect = bubbleContainer.node().getBoundingClientRect();
    const width = Math.max(520, Math.floor(rect.width));
    const height = Math.max(520, Math.floor(rect.height));

    const svg = bubbleContainer.append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', `0 0 ${width} ${height}`);

    const sectors = Array.from(new Set(data.map(d => d.sector))).sort(d3.ascending);

    const palette = (d3.schemeTableau10 || []).concat(d3.schemeSet3 || []).concat(d3.schemePaired || []);
    const color = d3.scaleOrdinal().domain(sectors).range(palette.slice(0, Math.max(1, sectors.length)));

    buildLegend(sectors, color);

    const nonEtf = data.filter(d => !isEtfRow(d));
    const mcExtent = d3.extent(nonEtf, d => d.marketCap);

    const rScale = d3.scaleSqrt()
      .domain([Math.max(1, mcExtent[0] ?? 1), mcExtent[1] ?? 1])
      .range([10, 44]);

    const ETF_RADIUS = 14;
    data.forEach(d => { d.r = isEtfRow(d) ? ETF_RADIUS : rScale(d.marketCap); });

    const centers = computeSectorCenters(sectors, width, height);

    const initCols = Math.ceil(Math.sqrt(data.length));
    const initRows = Math.ceil(data.length / initCols);
    const pad = 8;

    data.forEach((d, i) => {
      const col = i % initCols;
      const row = Math.floor(i / initCols);
      d.x = (width * 0.12) + col * ((width * 0.76) / Math.max(1, initCols - 1));
      d.y = (height * 0.12) + row * ((height * 0.76) / Math.max(1, initRows - 1));
      d.x += (i % 2) * pad;
      d.y += ((i + 1) % 2) * pad;
    });

    const simulation = d3.forceSimulation(data)
      .alpha(1)
      .alphaDecay(0.06)
      .velocityDecay(0.28)
      .force('x', d3.forceX(d => centers.get(d.sector).x).strength(0.16))
      .force('y', d3.forceY(d => centers.get(d.sector).y).strength(0.16))
      .force('charge', d3.forceManyBody().strength(-10))
      .force('collide', d3.forceCollide().radius(d => d.r + 1.5).iterations(2))
      .stop();

    for (let i = 0; i < 320; i += 1) simulation.tick();

    const nodes = svg.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(data, d => d.ticker)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.x}, ${d.y})`);

    nodes.append('circle')
      .attr('r', d => d.r)
      .attr('fill', d => color(d.sector))
      .attr('fill-opacity', 0.92)
      .on('mouseover', (event, d) => showTooltip(event, d))
      .on('mousemove', (event, d) => { if (!isEtfRow(d)) moveTooltip(event); })
      .on('mouseout', hideTooltip)
      .on('click', (event, d) => setSelectedTicker(d.ticker));

    nodes.append('text')
      .text(d => d.ticker)
      .attr('font-size', d => `${Math.max(9, Math.min(14, d.r * 0.55))}px`);

    setSelectedTicker(state.selectedTicker ?? data[0]?.ticker);

    window.addEventListener('resize', () => {
      clearTimeout(window.__bubbleResizeTimer);
      window.__bubbleResizeTimer = setTimeout(() => buildBubbleChart(data), 120);
    }, { passive: true });
  }

  function buildTable(data) {
    tableContainer.selectAll('*').remove();

    const table = tableContainer.append('table').attr('class', 'table');
    const thead = table.append('thead');
    const tbody = table.append('tbody');

    thead.append('tr')
      .selectAll('th')
      .data(['Ticker symbol', 'Full company name', 'Sector', 'Market cap'])
      .enter()
      .append('th')
      .text(d => d);

    const rows = tbody.selectAll('tr')
      .data(data, d => d.ticker)
      .enter()
      .append('tr')
      .attr('data-ticker', d => d.ticker)
      .on('click', (event, d) => setSelectedTicker(d.ticker));

    rows.append('td').attr('class', 'ticker').text(d => d.ticker);
    rows.append('td').text(d => d.fullName);
    rows.append('td').text(d => d.sector);
    rows.append('td').text(d => formatMarketCap(d.marketCap));

    setSelectedTicker(state.selectedTicker ?? data[0]?.ticker);
  }

  function init() {
    const data = stocks.slice().sort((a, b) => d3.ascending(a.sector, b.sector) || d3.ascending(a.ticker, b.ticker));
    buildBubbleChart(data);

    const tableData = stocks.slice().sort((a, b) => d3.ascending(a.ticker, b.ticker));
    buildTable(tableData);
  }

  init();
})();
