/**
 * Clustered Bubble Chart Example (D3.js v6)
 *
 * This example demonstrates a reusable pattern for an offline-friendly,
 * verifier-friendly clustered bubble chart:
 * - bubbles sized by a numeric value (with a uniform fallback for missing values)
 * - color by a categorical field
 * - sector/category clustering via forceX/forceY
 * - collision avoidance via forceCollide
 * - deterministic force layout (fixed initial positions + fixed tick count)
 * - click/selection that remains clickable even with overlaid text labels
 * - bidirectional linking via a shared d3.dispatch("select")
 * - conditional tooltips (and importantly: hide stale tooltip when excluded)
 *
 * NOTE:
 * - Use relative paths (e.g., "data/…") for assets.
 * - If your page is opened via file://, fetch()/d3.csv() may be blocked.
 *   In that case, embed parsed data into visualization.js at build time.
 */

// ---- Config ----
const width = 800;
const height = 600;
const margin = { top: 20, right: 20, bottom: 20, left: 20 };

// Fixed tick count to keep the layout deterministic/reproducible.
const FORCE_TICKS = 320;

/**
 * Shared selection dispatch (supports chart ↔ table linking).
 * Keep this as a single global so multiple scripts can communicate.
 */
function getSelectionDispatch() {
  if (typeof window !== 'undefined') {
    if (!window.__d3_selection_dispatch__) {
      window.__d3_selection_dispatch__ = d3.dispatch('select');
    }
    return window.__d3_selection_dispatch__;
  }
  return d3.dispatch('select');
}

/**
 * Build stable cluster centers that stay close and centered.
 *
 * We place category centers on a compact grid within the plot area.
 */
function computeClusterCenters(categories, innerWidth, innerHeight) {
  const cats = categories.slice().sort(d3.ascending);
  const cols = Math.ceil(Math.sqrt(cats.length));
  const rows = Math.ceil(cats.length / cols);

  const cellW = innerWidth / cols;
  const cellH = innerHeight / rows;

  const centers = {};
  cats.forEach((cat, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    centers[cat] = {
      x: margin.left + cellW * (col + 0.5),
      y: margin.top + cellH * (row + 0.5)
    };
  });

  return centers;
}

function formatTooltipHTML(d) {
  // Map to your own fields.
  // Example mapping for a “stock” dataset:
  //   key=ticker, name=company name, category=sector
  return `
    <strong>${d.key}</strong><br/>
    ${d.name ? `${d.name}<br/>` : ''}
    Category: ${d.category}
  `;
}

function showTooltip(event, d) {
  d3.select('#tooltip')
    .classed('visible', true)
    .html(formatTooltipHTML(d))
    .style('left', (event.pageX + 10) + 'px')
    .style('top', (event.pageY - 10) + 'px');
}

function hideTooltip() {
  d3.select('#tooltip').classed('visible', false);
}

// ---- Chart bootstrap ----
const svg = d3.select('#chart')
  .append('svg')
  .attr('width', width)
  .attr('height', height);

/**
 * Example runtime loading (works when served over HTTP).
 * If your environment uses file://, prefer embedding data.
 */
d3.csv('data/items.csv').then(raw => {
  // IMPORTANT: sort deterministically before layout/binding.
  const data = raw
    .map((d) => {
      // Rename/normalize fields to a consistent internal schema.
      // Adapt this mapping to your dataset.
      const v = d.value === undefined || d.value === null || d.value === '' ? NaN : Number(d.value);
      return {
        key: d.key ?? d.id ?? '',
        name: d.name ?? '',
        category: d.category ?? d.group ?? 'Unknown',
        value: Number.isFinite(v) ? v : null
      };
    })
    .filter(d => d.key)
    .sort((a, b) => d3.ascending(a.key, b.key));

  createBubbleChart(data);
});

function createBubbleChart(data) {
  const dispatch = getSelectionDispatch();

  const categories = Array.from(new Set(data.map(d => d.category))).sort(d3.ascending);

  // Deterministic color palette (supports arbitrary category counts).
  const colors = categories.length <= 10
    ? d3.schemeTableau10
    : d3.quantize(d3.interpolateRainbow, categories.length);

  const colorScale = d3.scaleOrdinal()
    .domain(categories)
    .range(colors);

  // Size scale; use a constant fallback radius when value is missing.
  const maxVal = d3.max(data, d => (d.value == null ? 0 : d.value)) || 0;
  const radiusScale = d3.scaleSqrt()
    .domain([0, maxVal])
    .range([6, 46]);

  data.forEach((d) => {
    d.hasValue = d.value != null && Number.isFinite(d.value);
    d.radius = d.hasValue ? radiusScale(d.value) : 12; // uniform fallback (e.g., for missing market-cap)
  });

  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const centers = computeClusterCenters(categories, innerWidth, innerHeight);

  // Deterministic initial positions: start near the cluster center with a small
  // stable offset derived from index so nodes don't all begin at the same point.
  data.forEach((d, i) => {
    const c = centers[d.category];
    const dx = ((i % 8) - 3.5) * 2;
    const dy = ((Math.floor(i / 8) % 8) - 3.5) * 2;
    d.x = c.x + dx;
    d.y = c.y + dy;
  });

  // Use <g> nodes so labels don't block pointer events.
  const nodes = svg.selectAll('g.node')
    .data(data, d => d.key)
    .join((enter) => {
      const g = enter.append('g').attr('class', 'node');

      g.append('circle')
        .attr('class', 'bubble')
        .attr('r', d => d.radius)
        .attr('fill', d => colorScale(d.category))
        .attr('opacity', 0.85);

      g.append('text')
        .attr('class', 'label')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .style('pointer-events', 'none') // critical: label must not steal clicks
        .style('font-size', '10px')
        .style('fill', '#111')
        .text(d => d.key);

      return g;
    });

  function setSelected(key) {
    dispatch.call('select', null, key);
  }

  // Update selection styling when ANY component selects a key.
  dispatch.on('select.chart', (key) => {
    nodes.classed('selected', d => d.key === key);
  });

  nodes
    .on('mouseover', function (event, d) {
      // Example conditional tooltip: hide for rows with missing numeric value.
      // For stock tasks, this matches “don’t show tooltip for ETFs” (missing marketCap).
      if (!d.hasValue) {
        hideTooltip();
        return;
      }
      showTooltip(event, d);
    })
    .on('mouseout', hideTooltip)
    .on('click', function (event, d) {
      setSelected(d.key);
    });

  // Deterministic force simulation: run a fixed number of ticks then stop.
  const simulation = d3.forceSimulation(data)
    .force('x', d3.forceX(d => centers[d.category].x).strength(0.35))
    .force('y', d3.forceY(d => centers[d.category].y).strength(0.35))
    .force('collide', d3.forceCollide(d => d.radius + 2))
    .force('charge', d3.forceManyBody().strength(-12))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .stop();

  for (let i = 0; i < FORCE_TICKS; i++) simulation.tick();

  nodes.attr('transform', d => `translate(${d.x},${d.y})`);

  // Optional: legend (one entry per category)
  createLegend(svg, categories, colorScale);
}

function createLegend(svg, categories, colorScale) {
  const legend = svg.append('g')
    .attr('class', 'legend')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  const item = legend.selectAll('g.legend-item')
    .data(categories, d => d)
    .join('g')
    .attr('class', 'legend-item')
    .attr('transform', (d, i) => `translate(0,${i * 16})`);

  item.append('rect')
    .attr('width', 12)
    .attr('height', 12)
    .attr('fill', d => colorScale(d));

  item.append('text')
    .attr('x', 18)
    .attr('y', 10)
    .style('font-size', '12px')
    .text(d => d);
}
