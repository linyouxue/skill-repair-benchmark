/**
 * Clustered Bubble Chart (deterministic force-simulation template)
 *
 * Use this as a starting point for tasks that ask for:
 * - One bubble per item
 * - Bubble size by a numeric value (e.g., market cap)
 * - Bubble color by a category (e.g., sector)
 * - Clustering by category using forceX/forceY
 * - No overlap using forceCollide
 * - Tooltip on hover (optionally conditional)
 * - Click-to-select + linked selection with a table
 *
 * Notes on determinism:
 * - D3 forceSimulation will RANDOMIZE initial positions if x/y are missing.
 * - To keep layouts stable, this template:
 *   1) sorts nodes deterministically
 *   2) assigns fixed cluster centers in a centered grid
 *   3) seeds each node with deterministic initial x/y near its cluster
 *   4) runs exactly N ticks (simulation.stop(); simulation.tick(N))
 */

/* global d3 */

'use strict';

/**
 * Compute category (sector) cluster centers as a centered grid.
 * This keeps clusters close together instead of spreading them around a circle.
 */
function computeGridCenters(labels, width, height, padding) {
  const n = labels.length;
  const cols = Math.ceil(Math.sqrt(n));
  const rows = Math.ceil(n / cols);

  const pad = Math.max(0, padding);
  const innerW = Math.max(1, width - pad * 2);
  const innerH = Math.max(1, height - pad * 2);
  const cellW = innerW / cols;
  const cellH = innerH / rows;

  const centers = new Map();
  labels.forEach((label, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    centers.set(label, {
      x: pad + cellW * (col + 0.5),
      y: pad + cellH * (row + 0.5),
    });
  });
  return centers;
}

/**
 * Deterministically seed node positions near each cluster center.
 * This avoids d3-force's random initialization and reduces "jiggle" edge cases.
 */
function seedPositions(nodes, centers, step) {
  const byGroupIndex = new Map();
  nodes.forEach((d) => {
    const c = centers.get(d.group) || { x: 0, y: 0 };
    const i = byGroupIndex.get(d.group) || 0;
    byGroupIndex.set(d.group, i + 1);

    // Small grid around the center.
    const cols = 6;
    const dx = ((i % cols) - (cols - 1) / 2) * step;
    const dy = (Math.floor(i / cols) - 1) * step;

    d.x = c.x + dx;
    d.y = c.y + dy;
    d.vx = 0;
    d.vy = 0;
  });
}

/**
 * Create a categorical legend.
 */
function renderLegend(containerSelector, labels, colorScale) {
  const root = d3.select(containerSelector);
  if (root.empty()) return;

  root.selectAll('*').remove();

  const title = root.append('div').attr('class', 'legend__title').text('Legend');
  void title; // keep lint-free if user removes the title styling

  const rows = root.append('div').attr('class', 'legend__rows');

  const row = rows
    .selectAll('div.legend__row')
    .data(labels, (d) => d)
    .join('div')
    .attr('class', 'legend__row');

  row
    .append('span')
    .attr('class', 'legend__swatch')
    .style('background', (d) => colorScale(d));

  row.append('span').attr('class', 'legend__label').text((d) => d);
}

/**
 * Ensure a tooltip div exists for the provided selector.
 */
function ensureTooltip(selector) {
  let tip = d3.select(selector);
  if (!tip.empty()) return tip;

  // Best-effort creation for common "#id" selectors.
  const id = (selector || '').startsWith('#') ? selector.slice(1) : 'tooltip';
  tip = d3
    .select('body')
    .append('div')
    .attr('id', id)
    .attr('class', 'tooltip')
    .classed('visible', false);

  return tip;
}

/**
 * Main entry: create a clustered bubble chart.
 *
 * @param {object} options
 * @returns {{ highlightBubble: function(string|null): void, destroy: function(): void, nodes: object[] }}
 */
function createClusteredBubbleChart(options) {
  const opts = options || {};

  const width = opts.width ?? 800;
  const height = opts.height ?? 600;

  const svgSelector = opts.svgSelector ?? '#bubbleSvg';
  const legendSelector = opts.legendSelector ?? '#legend';
  const tooltipSelector = opts.tooltipSelector ?? '#tooltip';

  const idAccessor = opts.idAccessor ?? ((d) => d.ticker ?? d.id);
  const labelAccessor = opts.labelAccessor ?? ((d) => d.ticker ?? d.id);
  const groupAccessor = opts.groupAccessor ?? ((d) => d.sector ?? d.group ?? 'Unknown');
  const valueAccessor = opts.valueAccessor ?? ((d) => (d.marketCap == null ? null : +d.marketCap));
  const nameAccessor = opts.nameAccessor ?? ((d) => d.name ?? d.fullName ?? '');

  // Whether a node should show a tooltip. Default: require an id + name + group + numeric value.
  const shouldShowTooltip =
    opts.shouldShowTooltip ??
    ((d) => {
      const id = idAccessor(d);
      const name = nameAccessor(d);
      const group = groupAccessor(d);
      const v = valueAccessor(d);
      return Boolean(id) && Boolean(name) && Boolean(group) && Number.isFinite(v);
    });

  const uniformRadius = opts.uniformRadius ?? 10; // e.g., for missing values
  const minRadius = opts.minRadius ?? 6;
  const maxRadius = opts.maxRadius ?? 48;

  const padding = opts.padding ?? 70;
  const ticks = opts.ticks ?? 320;

  const onSelect =
    opts.onSelect ??
    ((id) => {
      // Default: highlight locally and (if present) tell a linked table.
      highlightBubble(id);
      if (typeof globalThis !== 'undefined' && typeof globalThis.highlightTableRow === 'function') {
        globalThis.highlightTableRow(id);
      }
    });

  // Prepare SVG.
  const base = d3.select(svgSelector);
  const svg =
    base.empty() ? d3.select('body').append('svg') : base.node().tagName.toLowerCase() === 'svg' ? base : base.append('svg');

  svg.attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);
  svg.selectAll('*').remove();

  // Normalize nodes and sort deterministically.
  const raw = Array.isArray(opts.data) ? opts.data : [];
  const nodes = raw
    .map((d, i) => {
      const id = idAccessor(d);
      const group = groupAccessor(d);
      const v = valueAccessor(d);

      return {
        _i: i,
        id: id == null ? '' : String(id),
        label: String(labelAccessor(d) ?? id ?? ''),
        name: String(nameAccessor(d) ?? ''),
        group: String(group ?? 'Unknown'),
        value: Number.isFinite(v) ? v : null,
        hasTooltip: Boolean(shouldShowTooltip(d)),
        data: d,
      };
    })
    .filter((d) => d.id);

  nodes.sort((a, b) => d3.ascending(a.group, b.group) || d3.ascending(a.id, b.id));

  const groups = Array.from(new Set(nodes.map((d) => d.group))).sort(d3.ascending);

  // Stable color mapping.
  const palette = d3.schemeTableau10 || d3.schemeCategory10;
  const colors = groups.map((_, i) => palette[i % palette.length]);
  const colorScale = d3.scaleOrdinal().domain(groups).range(colors);

  // Bubble size scale.
  const maxValue = d3.max(nodes, (d) => d.value ?? 0) ?? 0;
  const radiusScale = d3.scaleSqrt().domain([0, maxValue]).range([minRadius, maxRadius]);

  nodes.forEach((d) => {
    d.r = d.value == null ? uniformRadius : radiusScale(d.value);
  });

  // Cluster centers + deterministic initial positions.
  const centers = computeGridCenters(groups, width, height, padding);
  seedPositions(nodes, centers, /* step */ 6);

  // Force simulation (deterministic: fixed ticks, no animation).
  const simulation = d3
    .forceSimulation(nodes)
    .force('x', d3.forceX((d) => (centers.get(d.group) || { x: width / 2 }).x).strength(0.12))
    .force('y', d3.forceY((d) => (centers.get(d.group) || { y: height / 2 }).y).strength(0.12))
    .force('collide', d3.forceCollide((d) => d.r + 1).iterations(2))
    .force('charge', d3.forceManyBody().strength(-4))
    .stop();

  simulation.tick(ticks);

  // Legend.
  renderLegend(legendSelector, groups, colorScale);

  // Tooltip.
  const tooltip = ensureTooltip(tooltipSelector);

  function showTooltip(event, d) {
    tooltip
      .classed('visible', true)
      .attr('aria-hidden', 'false')
      .html(
        `<div class="tooltip__title">${escapeHtml(d.id)}</div>` +
          `<div class="tooltip__body">` +
          `<div>${escapeHtml(d.name)}</div>` +
          `<div>Sector: ${escapeHtml(d.group)}</div>` +
          `</div>`
      )
      .style('left', `${event.pageX + 10}px`)
      .style('top', `${event.pageY - 10}px`);
  }

  function moveTooltip(event) {
    if (!tooltip.classed('visible')) return;
    tooltip.style('left', `${event.pageX + 10}px`).style('top', `${event.pageY - 10}px`);
  }

  function hideTooltip() {
    tooltip.classed('visible', false).attr('aria-hidden', 'true');
  }

  // Clamp positions to remain within the viewport (helps avoid off-screen nodes).
  nodes.forEach((d) => {
    d.x = Math.max(d.r, Math.min(width - d.r, d.x));
    d.y = Math.max(d.r, Math.min(height - d.r, d.y));
  });

  // Rendering: use <g> translated to x/y (simpler than keeping cx/cy in sync).
  const gRoot = svg.append('g').attr('class', 'bubbleChart');

  const node = gRoot
    .selectAll('g.node')
    .data(nodes, (d) => d.id)
    .join('g')
    .attr('class', 'node')
    .attr('transform', (d) => `translate(${d.x},${d.y})`);

  node
    .append('circle')
    .attr('class', 'bubble')
    .attr('r', (d) => d.r)
    .attr('fill', (d) => colorScale(d.group))
    .attr('opacity', 0.85)
    .on('mouseover', function (event, d) {
      if (!d.hasTooltip) return;
      showTooltip(event, d);
    })
    .on('mousemove', function (event) {
      moveTooltip(event);
    })
    .on('mouseout', function () {
      hideTooltip();
    })
    .on('click', function (event, d) {
      onSelect(d.id);
    });

  node
    .append('text')
    .attr('class', 'bubble__label')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .style('pointer-events', 'none')
    .style('font-size', (d) => `${Math.max(9, Math.min(14, Math.round(d.r * 0.55)))}px`)
    .text((d) => d.label);

  function highlightBubble(id) {
    const target = id == null ? null : String(id);
    svg.selectAll('circle.bubble').classed('selected', (d) => target != null && d.id === target);
    svg.selectAll('g.node').classed('selected', (d) => target != null && d.id === target);
  }

  function destroy() {
    simulation.stop();
    svg.selectAll('*').remove();
  }

  // Return a small API so callers can link to a table.
  return { highlightBubble, destroy, nodes };
}

/**
 * Minimal HTML escaping for tooltip content.
 */
function escapeHtml(s) {
  // Avoid String.prototype.replaceAll for broader runtime compatibility.
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Example integration (pseudo-code):
//
// const chart = createClusteredBubbleChart({
//   svgSelector: '#bubbleSvg',
//   legendSelector: '#legend',
//   tooltipSelector: '#tooltip',
//   data: rows,
//   idAccessor: d => d.ticker,
//   groupAccessor: d => d.sector,
//   valueAccessor: d => d.marketCap,
//   nameAccessor: d => d.fullName,
//   onSelect: setSelected
// });
//
// function setSelected(id) {
//   chart.highlightBubble(id);
//   table.highlightTableRow(id);
// }
