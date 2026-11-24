/* global d3 */

(function () {
  const WIDTH = 820;
  const HEIGHT = 560;
  const MARGIN = { top: 18, right: 18, bottom: 18, left: 18 };

  const ETF_RADIUS = 14;
  const STOCK_RADIUS_RANGE = [11, 46];

  const svg = d3
    .select('#bubble-svg')
    .attr('width', WIDTH)
    .attr('height', HEIGHT)
    .attr('viewBox', `0 0 ${WIDTH} ${HEIGHT}`);

  const plot = svg
    .append('g')
    .attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

  const innerW = WIDTH - MARGIN.left - MARGIN.right;
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;

  const tooltip = d3.select('#tooltip');

  let selectedTicker = null;
  let nodesSelection = null;
  let rowSelection = null;

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function isETFRow(d) {
    return d.sector === 'ETF' || d.marketCap == null || Number.isNaN(d.marketCap);
  }

  function formatMarketCap(v) {
    if (v == null || Number.isNaN(v)) return '—';

    const abs = Math.abs(v);
    const trim = (s) => s.replace(/\.0+$/, '').replace(/(\.[0-9]*?)0+$/, '$1');

    if (abs >= 1e12) return `${trim((v / 1e12).toFixed(2))}T`;
    if (abs >= 1e9) return `${trim((v / 1e9).toFixed(2))}B`;
    if (abs >= 1e6) return `${trim((v / 1e6).toFixed(2))}M`;
    if (abs >= 1e3) return `${trim((v / 1e3).toFixed(2))}K`;

    return d3.format(',')(v);
  }

  function setSelected(ticker) {
    selectedTicker = ticker;

    if (nodesSelection) {
      nodesSelection.classed('selected', (d) => d.ticker === selectedTicker);
    }

    if (rowSelection) {
      rowSelection.classed('selected', (d) => d.ticker === selectedTicker);
      const el = document.querySelector(`tr[data-ticker="${selectedTicker}"]`);
      if (el) {
        el.scrollIntoView({ block: 'nearest' });
      }
    }
  }

  function hideTooltip() {
    tooltip.classed('visible', false).attr('aria-hidden', 'true');
  }

  function showTooltip(event, d) {
    if (d.isETF) {
      hideTooltip();
      return;
    }

    tooltip
      .html(
        `<div class="ticker">${d.ticker}</div>` +
          `<div>${d.fullName}</div>` +
          `<div class="muted">Sector: ${d.sector}</div>`
      )
      .classed('visible', true)
      .attr('aria-hidden', 'false');

    const pad = 14;
    const tt = tooltip.node();
    const rect = tt.getBoundingClientRect();

    const x = clamp(event.pageX + 12, pad, window.pageXOffset + window.innerWidth - rect.width - pad);
    const y = clamp(event.pageY - 10, pad, window.pageYOffset + window.innerHeight - rect.height - pad);

    tooltip.style('left', `${x}px`).style('top', `${y}px`);
  }

  async function loadStockDescriptions() {
    const embedded = document.getElementById('stock-descriptions-csv');
    if (embedded && embedded.textContent.trim()) {
      return d3.csvParse(embedded.textContent.trim());
    }

    const resp = await fetch('data/stock-descriptions.csv');
    const text = await resp.text();
    return d3.csvParse(text);
  }

  function computeSectorCenters(sectors) {
    const sorted = sectors.slice().sort(d3.ascending);
    const cols = Math.ceil(Math.sqrt(sorted.length));
    const rows = Math.ceil(sorted.length / cols);

    const xPad = innerW * 0.10;
    const yPad = innerH * 0.12;

    const usableW = innerW - xPad * 2;
    const usableH = innerH - yPad * 2;

    const centers = {};

    for (let i = 0; i < sorted.length; i++) {
      const sector = sorted[i];
      const col = i % cols;
      const row = Math.floor(i / cols);

      const x = xPad + usableW * ((col + 0.5) / cols);
      const y = yPad + usableH * ((row + 0.5) / rows);

      centers[sector] = { x, y };
    }

    return centers;
  }

  function renderLegend(sectors, color) {
    const container = d3.select('#legend');

    const items = container.selectAll('.legend-item').data(sectors, (d) => d);

    const enter = items
      .enter()
      .append('div')
      .attr('class', 'legend-item');

    enter.append('span').attr('class', 'legend-swatch').style('background', (d) => color(d));
    enter.append('span').text((d) => d);

    items
      .select('.legend-swatch')
      .style('background', (d) => color(d));

    items.exit().remove();
  }

  function renderTable(data) {
    const tableData = data
      .slice()
      .sort((a, b) => d3.ascending(a.ticker, b.ticker));

    const container = d3.select('#table-container');
    container.selectAll('*').remove();

    const scroller = container.append('div').attr('class', 'table-scroller');

    const table = scroller.append('table').attr('class', 'stock-table');

    table
      .append('thead')
      .append('tr')
      .selectAll('th')
      .data(['Ticker symbol', 'Full company name', 'Sector', 'Market cap'])
      .enter()
      .append('th')
      .text((d) => d);

    const tbody = table.append('tbody');

    rowSelection = tbody
      .selectAll('tr')
      .data(tableData, (d) => d.ticker)
      .enter()
      .append('tr')
      .attr('data-ticker', (d) => d.ticker)
      .on('click', function (event, d) {
        event.preventDefault();
        event.stopPropagation();
        setSelected(d.ticker);
      });

    rowSelection.append('td').attr('class', 'ticker').text((d) => d.ticker);
    rowSelection.append('td').text((d) => d.fullName);
    rowSelection.append('td').text((d) => d.sector);
    rowSelection.append('td').attr('class', 'marketcap').text((d) => formatMarketCap(d.marketCap));
  }

  function renderBubbles(data, color, sectorCenters) {
    plot.selectAll('*').remove();

    const nodes = data
      .slice()
      .sort((a, b) => d3.ascending(a.ticker, b.ticker))
      .map((d, i) => {
        const c = sectorCenters[d.sector];
        const jitterX = ((i % 9) - 4) * 2;
        const jitterY = ((Math.floor(i / 9) % 7) - 3) * 2;
        return {
          ...d,
          x: c.x + jitterX,
          y: c.y + jitterY,
        };
      });

    const maxR = d3.max(nodes, (d) => d.r) || 40;

    plot
      .append('rect')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', innerW)
      .attr('height', innerH)
      .attr('fill', 'transparent')
      .on('click', function () {
        setSelected(null);
      });

    const node = plot
      .selectAll('.node')
      .data(nodes, (d) => d.ticker)
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .on('click', function (event, d) {
        event.preventDefault();
        event.stopPropagation();
        setSelected(d.ticker);
      })
      .on('mouseover', function (event, d) {
        showTooltip(event, d);
      })
      .on('mousemove', function (event, d) {
        showTooltip(event, d);
      })
      .on('mouseout', function () {
        hideTooltip();
      });

    node
      .append('circle')
      .attr('r', (d) => d.r)
      .attr('fill', (d) => color(d.sector))
      .attr('fill-opacity', 0.88);

    node
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .text((d) => d.ticker)
      .each(function (d) {
        const text = d3.select(this);
        const maxChars = Math.max(2, Math.floor((d.r * 1.6) / 7));
        if (d.ticker.length > maxChars) {
          text.text(d.ticker.slice(0, maxChars));
        }
      });

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'x',
        d3
          .forceX((d) => sectorCenters[d.sector].x)
          .strength(0.12)
      )
      .force(
        'y',
        d3
          .forceY((d) => sectorCenters[d.sector].y)
          .strength(0.12)
      )
      .force('collide', d3.forceCollide((d) => d.r + 1).iterations(2))
      .force('charge', d3.forceManyBody().strength(-5))
      .force('center', d3.forceCenter(innerW / 2, innerH / 2));

    simulation.stop();
    for (let i = 0; i < 340; i++) simulation.tick();

    node.attr('transform', (d) => `translate(${clamp(d.x, d.r, innerW - d.r)},${clamp(d.y, d.r, innerH - d.r)})`);

    nodesSelection = node;
  }

  function prepareData(raw) {
    const cleaned = raw
      .map((row) => {
        const marketCapStr = (row.marketCap || '').trim();
        const marketCap = marketCapStr === '' ? null : +marketCapStr;
        const sector = (row.sector || '').trim();
        const ticker = (row.ticker || '').trim();
        const fullName = (row['full name'] || '').trim();

        return {
          ticker,
          sector,
          fullName,
          marketCap: Number.isFinite(marketCap) ? marketCap : null,
        };
      })
      .filter((d) => d.ticker);

    const marketCaps = cleaned.filter((d) => d.marketCap != null).map((d) => d.marketCap);
    const mcExtent = d3.extent(marketCaps);

    const radiusScale = d3
      .scaleSqrt()
      .domain(mcExtent[0] == null ? [0, 1] : mcExtent)
      .range(STOCK_RADIUS_RANGE);

    return cleaned.map((d) => {
      const isETF = isETFRow(d);
      const r = isETF ? ETF_RADIUS : radiusScale(d.marketCap);

      return {
        ...d,
        isETF,
        r,
      };
    });
  }

  async function main() {
    const raw = await loadStockDescriptions();
    const data = prepareData(raw);

    const sectors = Array.from(new Set(data.map((d) => d.sector))).sort(d3.ascending);

    const color = d3.scaleOrdinal().domain(sectors).range(d3.schemeTableau10);
    const sectorCenters = computeSectorCenters(sectors);

    renderLegend(sectors, color);
    renderBubbles(data, color, sectorCenters);
    renderTable(data);

    d3.select(window).on('keydown', (event) => {
      if (event.key === 'Escape') {
        setSelected(null);
        hideTooltip();
      }
    });
  }

  main().catch((err) => {
    console.error(err);
    const container = document.getElementById('table-container');
    if (container) {
      container.innerHTML = `<div style="color: rgba(231,236,255,0.8); padding: 10px;">Failed to load data. If you opened this via file:// and your browser blocks fetch, run a local server.</div>`;
    }
  });
})();
