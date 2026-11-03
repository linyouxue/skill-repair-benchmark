/* global d3 */
(function () {
  'use strict';

  const WIDTH = 716;
  const HEIGHT = 650;

  const svg = d3
    .select('#bubble-svg')
    .attr('width', WIDTH)
    .attr('height', HEIGHT)
    .attr('viewBox', `0 0 ${WIDTH} ${HEIGHT}`);

  const tooltip = d3.select('#tooltip');
  const errorBox = d3.select('#error');
  const EMBEDDED_CSV_ID = 'embedded-stock-descriptions';

  function showError(msg, err) {
    const details = err ? `\n${String(err)}` : '';
    errorBox.style('display', 'block').text(`${msg}${details}`);
  }

  function hashStringFNV1a(str) {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i += 1) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  }

  function parseMarketCap(v) {
    const s = (v == null ? '' : String(v)).replace(/,/g, '').trim();
    if (!s) return null;
    const n = +s;
    return Number.isFinite(n) ? n : null;
  }

  function formatMarketCap(v) {
    if (v == null || !Number.isFinite(v)) return '—';
    const s = d3.format('.3~s')(v);
    return s.replace('G', 'B');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function loadStockDescriptions() {
    try {
      return await d3.csv('data/stock-descriptions.csv');
    } catch (err) {
      const el = document.getElementById(EMBEDDED_CSV_ID);
      if (el && el.textContent && el.textContent.trim().length > 0) {
        return d3.csvParse(el.textContent.trim());
      }
      throw err;
    }
  }

  function computeSectorCenters(sectors) {
    const cx = WIDTH / 2;
    const cy = HEIGHT / 2;
    const ring = Math.min(WIDTH, HEIGHT) * 0.24;

    const centers = new Map();
    sectors.forEach((sector, i) => {
      const a = (i / sectors.length) * Math.PI * 2 - Math.PI / 2;
      centers.set(sector, {
        x: cx + ring * Math.cos(a),
        y: cy + ring * Math.sin(a),
      });
    });

    return centers;
  }

  function init(rawRows) {
    const stocks = rawRows
      .map((row) => {
        const ticker = (row.ticker || '').trim();
        const name = (row['full name'] || '').trim();
        const sector = (row.sector || 'Unknown').trim() || 'Unknown';
        const marketCap = parseMarketCap(row.marketCap);
        const country = (row.country || '').trim();
        const website = (row.website || '').trim();

        const isEtf = sector === 'ETF' || (marketCap == null && !country && !website);

        return {
          ticker,
          name,
          sector,
          marketCap,
          country,
          website,
          isEtf,
        };
      })
      .filter((d) => d.ticker.length > 0);

    stocks.sort((a, b) => d3.ascending(a.ticker, b.ticker));

    const sectors = Array.from(new Set(stocks.map((d) => d.sector))).sort(d3.ascending);

    const palette = (d3.schemeTableau10 || []).concat(d3.schemeSet3 || []);
    const color = d3
      .scaleOrdinal()
      .domain(sectors)
      .range(palette.slice(0, Math.max(1, sectors.length)));

    const marketCaps = stocks.filter((d) => d.marketCap != null).map((d) => d.marketCap);
    const capExtent = d3.extent(marketCaps);

    const rScale = d3
      .scaleSqrt()
      .domain(capExtent[0] == null ? [0, 1] : capExtent)
      .range([12, 48]);

    const etfRadius = 14;
    stocks.forEach((d) => {
      d.r = d.marketCap != null ? rScale(d.marketCap) : etfRadius;
    });

    const centers = computeSectorCenters(sectors);

    // Deterministic initial positions (avoid Math.random).
    stocks.forEach((d) => {
      const c = centers.get(d.sector);
      const h = hashStringFNV1a(d.ticker);
      const angle = ((h % 360) * Math.PI) / 180;
      const mag = ((h >>> 8) % 41) - 20;
      d.x = c.x + mag * Math.cos(angle);
      d.y = c.y + mag * Math.sin(angle);
      d.vx = 0;
      d.vy = 0;
    });

    svg.selectAll('*').remove();

    svg
      .append('rect')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', WIDTH)
      .attr('height', HEIGHT)
      .attr('fill', '#ffffff');

    // Legend
    const legend = svg.append('g').attr('class', 'legend').attr('transform', 'translate(14, 14)');

    legend
      .append('text')
      .attr('class', 'legend-title')
      .attr('x', 0)
      .attr('y', 0)
      .attr('dy', '0.9em')
      .text('Sector');

    const legendItems = legend
      .selectAll('g.legend-item')
      .data(sectors, (d) => d)
      .join('g')
      .attr('class', 'legend-item')
      .attr('transform', (d, i) => `translate(0, ${24 + i * 16})`);

    legendItems
      .append('rect')
      .attr('class', 'legend-swatch')
      .attr('width', 12)
      .attr('height', 12)
      .attr('rx', 2)
      .attr('ry', 2)
      .attr('y', -10)
      .attr('fill', (d) => color(d));

    legendItems
      .append('text')
      .attr('class', 'legend-label')
      .attr('x', 16)
      .attr('y', 0)
      .attr('dy', '0.35em')
      .text((d) => d);

    // Nodes
    const nodesLayer = svg.append('g').attr('class', 'nodes');

    const node = nodesLayer
      .selectAll('g.node')
      .data(stocks, (d) => d.ticker)
      .join((enter) => {
        const g = enter.append('g').attr('class', 'node').style('cursor', 'pointer');
        g.append('circle').attr('class', 'bubble');
        g.append('text').attr('class', 'bubble-label');
        return g;
      });

    node
      .select('circle')
      .attr('r', (d) => d.r)
      .attr('fill', (d) => color(d.sector));

    node
      .select('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .style('font-size', (d) => `${Math.max(9, Math.min(14, d.r * 0.65))}px`)
      .text((d) => d.ticker);

    // Tooltip
    function positionTooltip(event) {
      const pad = 12;
      tooltip.style('left', `${event.pageX + pad}px`).style('top', `${event.pageY - pad}px`);
    }

    function onMouseOver(event, d) {
      if (d.isEtf) {
        tooltip.classed('visible', false);
        return;
      }

      tooltip
        .classed('visible', true)
        .html(
          [
            `<div class="tt-ticker">${escapeHtml(d.ticker)}</div>`,
            `<div class="tt-name">${escapeHtml(d.name)}</div>`,
            `<div class="tt-meta">Sector: ${escapeHtml(d.sector)}</div>`,
          ].join('')
        );

      positionTooltip(event);
    }

    function onMouseMove(event, d) {
      if (d.isEtf) return;
      positionTooltip(event);
    }

    function onMouseOut() {
      tooltip.classed('visible', false);
    }

    // Table
    const tableBody = d3.select('#stock-table tbody');
    tableBody.selectAll('*').remove();

    const rows = tableBody
      .selectAll('tr')
      .data(stocks, (d) => d.ticker)
      .join('tr')
      .attr('class', 'table-row');

    rows.append('td').attr('class', 'col-ticker').text((d) => d.ticker);
    rows.append('td').attr('class', 'col-name').text((d) => d.name);
    rows.append('td').attr('class', 'col-sector').text((d) => d.sector);
    rows.append('td').attr('class', 'col-marketcap').text((d) => formatMarketCap(d.marketCap));

    // Selection linking
    let selectedTicker = null;

    function setSelected(ticker) {
      selectedTicker = ticker;

      node.classed('selected', (d) => d.ticker === selectedTicker);
      rows.classed('selected', (d) => d.ticker === selectedTicker);

      node.filter((d) => d.ticker === selectedTicker).raise();

      const rowEl = rows.filter((d) => d.ticker === selectedTicker).node();
      if (rowEl && rowEl.scrollIntoView) {
        rowEl.scrollIntoView({ block: 'nearest' });
      }
    }

    function onSelect(event, d) {
      setSelected(d.ticker);
    }

    node.on('click', onSelect);
    node
      .select('circle')
      .on('mouseover', onMouseOver)
      .on('mousemove', onMouseMove)
      .on('mouseout', onMouseOut)
      .on('click', onSelect);

    node
      .select('text')
      .on('mouseover', onMouseOver)
      .on('mousemove', onMouseMove)
      .on('mouseout', onMouseOut)
      .on('click', onSelect);

    rows.on('click', (event, d) => setSelected(d.ticker));

    // Force simulation
    const simulation = d3
      .forceSimulation(stocks)
      .force(
        'x',
        d3
          .forceX((d) => centers.get(d.sector).x)
          .strength(0.18)
      )
      .force(
        'y',
        d3
          .forceY((d) => centers.get(d.sector).y)
          .strength(0.18)
      )
      .force('collide', d3.forceCollide((d) => d.r + 2).iterations(2))
      .force('center', d3.forceCenter(WIDTH / 2, HEIGHT / 2))
      .alpha(1)
      .alphaDecay(0.03)
      .on('tick', ticked);

    function clampToBounds(d) {
      d.x = Math.max(d.r, Math.min(WIDTH - d.r, d.x));
      d.y = Math.max(d.r, Math.min(HEIGHT - d.r, d.y));
    }

    function ticked() {
      node.attr('transform', (d) => {
        clampToBounds(d);
        return `translate(${d.x.toFixed(2)},${d.y.toFixed(2)})`;
      });
    }

    if (stocks.length > 0) {
      setSelected(stocks[0].ticker);
    }

    simulation.alphaTarget(0);
  }

  loadStockDescriptions()
    .then(init)
    .catch((err) => {
      showError('Failed to load stock data. If you opened the HTML directly, try a local web server.', err);
    });
})();
