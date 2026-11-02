/**
 * Complete Bubble Chart Example with Force Simulation
 *
 * This example shows how to create a clustered bubble chart with:
 * - Force-directed layout
 * - Collision detection
 * - Color coding by category
 * - Size scaling by value
 */

// Configuration
const width = 800;
const height = 600;
const margin = {top: 20, right: 20, bottom: 20, left: 20};

/**
 * Shared selection dispatch (bidirectional linking between components).
 *
 * Any component can:
 *   const dispatch = getSelectionDispatch();
 *   dispatch.call('select', null, key);
 *
 * And subscribe:
 *   dispatch.on('select.namespace', key => { ... });
 */
function getSelectionDispatch() {
    // Browser: reuse a single global dispatch so separate scripts can link.
    if (typeof window !== 'undefined') {
        if (!window.__d3_selection_dispatch__) {
            window.__d3_selection_dispatch__ = d3.dispatch('select');
        }
        return window.__d3_selection_dispatch__;
    }
    // Non-browser fallback.
    return d3.dispatch('select');
}

// Create SVG
const svg = d3.select('#chart')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

// Load and process data
d3.csv('/data/stocks.csv').then(data => {
    // Parse numbers
    data.forEach(d => {
        const v = d.marketCap === undefined || d.marketCap === null || d.marketCap === '' ? NaN : Number(d.marketCap);
        d.value = Number.isFinite(v) ? v : null;
        d.ticker = d.ticker;
        d.sector = d.sector;
    });

    createBubbleChart(data);
});

function createBubbleChart(data) {
    // Setup shared selection listener (supports table ↔ chart linking)
    const dispatch = getSelectionDispatch();
    dispatch.on('select.chart', (ticker) => {
        d3.selectAll('.bubble').classed('selected', d => d.ticker === ticker);
    });

    // Setup scales
    const radiusScale = d3.scaleSqrt()
        .domain([0, d3.max(data, d => d.value || 0)])
        .range([5, 50]);

    const colorScale = d3.scaleOrdinal()
        .domain([...new Set(data.map(d => d.sector))])
        .range(d3.schemeCategory10);

    // Calculate radius for each data point
    data.forEach(d => {
        if (d.value === null || isNaN(d.value)) {
            d.radius = 10; // Uniform size for missing data
            d.hasValue = false;
        } else {
            d.radius = radiusScale(d.value);
            d.hasValue = true;
        }
    });

    // Create force simulation
    const simulation = d3.forceSimulation(data)
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide(d => d.radius + 2))
        .force('charge', d3.forceManyBody().strength(-30));

    // Optional: Cluster by sector
    const sectors = [...new Set(data.map(d => d.sector))];
    const sectorPositions = {};
    sectors.forEach((sector, i) => {
        const angle = (i / sectors.length) * 2 * Math.PI;
        sectorPositions[sector] = {
            x: width / 2 + Math.cos(angle) * 150,
            y: height / 2 + Math.sin(angle) * 150
        };
    });

    simulation
        .force('x', d3.forceX(d => sectorPositions[d.sector].x).strength(0.5))
        .force('y', d3.forceY(d => sectorPositions[d.sector].y).strength(0.5));

    // Create nodes as <g> so text labels don't block interaction
    const nodes = svg.selectAll('g.node')
        .data(data, d => d.ticker)
        .join(enter => {
            const g = enter.append('g')
                .attr('class', 'node');

            g.append('circle')
                .attr('class', 'bubble')
                .attr('r', d => d.radius)
                .attr('fill', d => colorScale(d.sector))
                .attr('opacity', 0.7);

            g.append('text')
                .attr('class', 'label')
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .style('pointer-events', 'none') // avoid "unclickable" bubbles
                .style('font-size', '10px')
                .style('fill', '#111')
                .text(d => d.ticker);

            return g;
        });

    // Attach interaction to the group (works when clicking label text)
    nodes
        .on('mouseover', function(event, d) {
            // Only show tooltip for non-ETF entries.
            // Prefer explicit flag when present; otherwise fall back to missing-value heuristic.
            const isETF = d.isETF === true || d.hasValue === false;
            if (!isETF) {
                showTooltip(event, d);
            }
        })
        .on('mouseout', hideTooltip)
        .on('click', function(event, d) {
            selectBubble(d.ticker);
        });

    // Update positions on each tick
    simulation.on('tick', () => {
        nodes.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

function showTooltip(event, d) {
    const tooltip = d3.select('#tooltip');
    tooltip
        .classed('visible', true)
        .html(`
            <strong>${d.ticker}</strong><br/>
            ${d.name || 'N/A'}<br/>
            Sector: ${d.sector}
        `)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 10) + 'px');
}

function hideTooltip() {
    d3.select('#tooltip').classed('visible', false);
}

function selectBubble(ticker) {
    // Update local chart state
    d3.selectAll('.bubble')
        .classed('selected', d => d.ticker === ticker);

    // Broadcast selection so other components (e.g., table) can sync.
    const dispatch = getSelectionDispatch();
    dispatch.call('select', null, ticker);
}
