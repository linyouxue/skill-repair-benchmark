/**
 * Reference Bubble Chart with Force-Directed Clustering
 *
 * Pattern to adapt for any task that needs:
 * - Force-directed layout clustered by a categorical field
 * - Collision detection (no overlap)
 * - Area-proportional sizing (scaleSqrt) with a uniform fallback for missing values
 * - Stable per-category colors
 * - In-mark labels (e.g. ticker symbol inside each bubble)
 * - Conditional tooltip (skips records missing the fields the tooltip would show)
 * - A `highlight(key)` / `onSelect(cb)` API so a sibling table can stay in sync
 *
 * IMPORTANT: this file uses D3 v6+ event signatures: `.on('event', (event, d) => ...)`.
 * When adapting, rename fields (ticker/sector/marketCap) and sector names to match
 * the task data — do not keep these identifiers if they don't apply.
 */

// Configuration — override from the caller when embedding.
const DEFAULT_CONFIG = {
    width: 740,
    height: 600,
    radiusRange: [14, 50],     // min/max pixel radius for scaled bubbles
    uniformRadius: 20,         // radius for records missing the numeric field
    clusterRadiusFrac: 0.24,   // attractor circle radius as a fraction of min(width, height)
    forceStrength: 0.18,       // forceX/forceY strength toward each cluster center
    collidePadding: 2,
    collideIterations: 3,
    preTicks: 300,             // run this many ticks up front for a stable initial layout
};

/**
 * Build a clustered bubble chart.
 *
 * @param {Object}   opts
 * @param {string}   opts.container   CSS selector for the chart container, e.g. '#bubble-chart'
 * @param {Array}    opts.data        records; each must expose `.ticker`, `.name`, `.sector`, `.marketCap`
 * @param {string}   [opts.tooltip]   CSS selector for an existing tooltip element, e.g. '#tooltip'
 * @param {function} [opts.shouldTooltip]  (d) => boolean. Return false to suppress tooltip for this record.
 * @param {function} [opts.tooltipHtml]    (d) => html string for the tooltip body.
 * @param {Object}   [opts.colors]    sector -> color hex map (stable palette).
 * @param {Object}   [opts.config]    overrides merged onto DEFAULT_CONFIG.
 */
function buildClusteredBubbleChart(opts) {
    const cfg = Object.assign({}, DEFAULT_CONFIG, opts.config || {});
    const data = opts.data.slice();
    const colors = opts.colors || buildDefaultColors(data.map(d => d.sector));
    const colorOf = s => colors[s] || '#6b7280';

    // Radius scale: scaleSqrt so AREA encodes the value.
    const valued = data.filter(d => isFinite(+d.marketCap) && +d.marketCap > 0);
    const radiusScale = d3.scaleSqrt()
        .domain([
            d3.min(valued, d => +d.marketCap) || 1,
            d3.max(valued, d => +d.marketCap) || 1,
        ])
        .range(cfg.radiusRange);

    data.forEach(d => {
        d.r = (isFinite(+d.marketCap) && +d.marketCap > 0)
            ? radiusScale(+d.marketCap)
            : cfg.uniformRadius;
    });

    // Cluster centers arranged on a small circle around the chart center —
    // "close together and centered", not in the corners.
    const sectors = Array.from(new Set(data.map(d => d.sector)));
    const centers = {};
    const cx = cfg.width / 2;
    const cy = cfg.height / 2;
    const rCluster = Math.min(cfg.width, cfg.height) * cfg.clusterRadiusFrac;
    sectors.forEach((s, i) => {
        const angle = (i / sectors.length) * 2 * Math.PI - Math.PI / 2;
        centers[s] = { x: cx + rCluster * Math.cos(angle), y: cy + rCluster * Math.sin(angle) };
    });

    // Seed positions near each record's cluster so the layout starts settled.
    data.forEach((d, i) => {
        const c = centers[d.sector] || { x: cx, y: cy };
        d.x = c.x + ((i % 5) - 2) * 4;
        d.y = c.y + ((Math.floor(i / 5) % 5) - 2) * 4;
    });

    const svg = d3.select(opts.container)
        .append('svg')
        .attr('viewBox', `0 0 ${cfg.width} ${cfg.height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    const tooltip = opts.tooltip ? d3.select(opts.tooltip) : null;
    const shouldTooltip = opts.shouldTooltip || (d => true);
    const tooltipHtml = opts.tooltipHtml || (d =>
        `<strong>${d.ticker}</strong><br/>${d.name || ''}<br/>${d.sector || ''}`
    );

    let selectedKey = null;
    let selectCallback = () => {};

    const nodes = svg.selectAll('g.node')
        .data(data, d => d.ticker)
        .join('g')
        .attr('class', 'node');

    const bubbles = nodes.append('circle')
        .attr('class', 'bubble')
        .attr('r', d => d.r)
        .attr('fill', d => colorOf(d.sector))
        .on('mouseover', function (event, d) {
            if (!tooltip || !shouldTooltip(d)) return;   // conditional tooltip
            tooltip
                .classed('visible', true)
                .html(tooltipHtml(d))
                .style('left', (event.pageX + 12) + 'px')
                .style('top',  (event.pageY + 12) + 'px');
        })
        .on('mousemove', function (event, d) {
            if (!tooltip || !shouldTooltip(d)) return;
            tooltip
                .style('left', (event.pageX + 12) + 'px')
                .style('top',  (event.pageY + 12) + 'px');
        })
        .on('mouseout', function () {
            if (!tooltip) return;
            tooltip.classed('visible', false);
        })
        .on('click', function (event, d) {
            selectedKey = d.ticker;       // idempotent: click always sets selection
            selectCallback(selectedKey);
        });

    // In-bubble labels: ticker symbol centered. `pointer-events: none` is applied
    // via CSS so labels don't steal hover events from the circle.
    nodes.append('text')
        .attr('class', 'bubble-label')
        .text(d => d.ticker)
        .style('font-size', d => Math.max(9, Math.min(14, d.r / 2.2)) + 'px');

    const simulation = d3.forceSimulation(data)
        .force('x', d3.forceX(d => (centers[d.sector] || {x: cx}).x).strength(cfg.forceStrength))
        .force('y', d3.forceY(d => (centers[d.sector] || {y: cy}).y).strength(cfg.forceStrength))
        .force('charge', d3.forceManyBody().strength(3))
        .force('collide', d3.forceCollide(d => d.r + cfg.collidePadding).iterations(cfg.collideIterations))
        .alpha(1)
        .alphaDecay(0.03);

    simulation.on('tick', () => {
        data.forEach(d => {
            d.x = Math.max(d.r + 1, Math.min(cfg.width  - d.r - 1, d.x));
            d.y = Math.max(d.r + 1, Math.min(cfg.height - d.r - 1, d.y));
        });
        nodes.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    for (let i = 0; i < cfg.preTicks; i++) simulation.tick();
    simulation.alpha(0.3).restart();

    // --- Legend (rendered into #legend if that element exists) -----------------
    const legend = d3.select('#legend');
    if (!legend.empty()) {
        legend.selectAll('.legend-item')
            .data(sectors)
            .join('div')
            .attr('class', 'legend-item')
            .html(s => `<span class="legend-swatch" style="background:${colorOf(s)}"></span>${s}`);
    }

    function highlight(key) {
        selectedKey = key;
        bubbles.classed('selected', d => d.ticker === key);
    }

    return {
        highlight,
        onSelect(cb) { selectCallback = cb; },
        get selected() { return selectedKey; },
    };
}

// Build a stable palette by iterating a categorical D3 scheme.
function buildDefaultColors(sectors) {
    const palette = (typeof d3 !== 'undefined' && d3.schemeTableau10) || [
        '#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed',
        '#0891b2', '#be185d', '#4d7c0f', '#92400e', '#374151',
    ];
    const unique = Array.from(new Set(sectors));
    const colors = {};
    unique.forEach((s, i) => { colors[s] = palette[i % palette.length]; });
    return colors;
}

// --- Example usage ----------------------------------------------------------
//
// d3.csv('data/stock-descriptions.csv', d => ({
//     ticker:    d.ticker,
//     name:      d['full name'],
//     sector:    d.sector,
//     marketCap: d.marketCap ? +d.marketCap : null,
// })).then(data => {
//     const chart = buildClusteredBubbleChart({
//         container: '#bubble-chart',
//         tooltip:   '#tooltip',
//         data,
//         // ETFs have no marketCap/country/website — skip the tooltip for them.
//         shouldTooltip: d => d.sector !== 'ETF',
//         tooltipHtml: d => `<strong>${d.ticker}</strong><br/>${d.name}<br/>${d.sector}`,
//     });
//
//     const table = buildInteractiveTable(data);  // from interactive_table_example.js
//
//     // Linked selection: a single top-level `select` fans out to both panels.
//     const select = key => { chart.highlight(key); table.highlight(key); };
//     chart.onSelect(select);
//     table.onSelect(select);
// });

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { buildClusteredBubbleChart };
}
