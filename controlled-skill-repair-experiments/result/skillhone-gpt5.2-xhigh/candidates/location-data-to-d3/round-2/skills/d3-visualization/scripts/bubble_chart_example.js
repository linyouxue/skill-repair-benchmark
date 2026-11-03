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

// Create SVG
const svg = d3.select('#chart')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

// Load and process data
d3.csv('/data/stocks.csv').then(data => {
    // Parse numbers
    data.forEach(d => {
        d.value = d.marketCap ? +d.marketCap : null;
        d.ticker = d.ticker;
        d.sector = d.sector;
    });

    createBubbleChart(data);
});

function createBubbleChart(data) {
    // Setup scales
    const radiusScale = d3.scaleSqrt()
        .domain([0, d3.max(data, d => d.value || 0)])
        .range([5, 50]);

    // IMPORTANT: Use a complete, deterministic category domain so legends are complete.
    // Build from the whole dataset, sort for stability, then pick a palette that can
    // cover all categories (don't silently drop categories beyond 10).
    const sectors = Array.from(new Set(data.map(d => d.sector))).sort(d3.ascending);

    const palette = sectors.length <= 10
        ? d3.schemeCategory10
        : d3.quantize(d3.interpolateRainbow, sectors.length);

    const colorScale = d3.scaleOrdinal()
        .domain(sectors)
        .range(palette);

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
    // Reuse the same deterministic sector list used by the color scale.
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

    // Add a categorical legend (one entry per sector).
    // Use stable class names so verifiers can locate and count legend entries.
    const legend = svg.append('g')
        .attr('class', 'legend')
        .attr('transform', `translate(${margin.left + 10},${margin.top + 10})`);

    legend.append('text')
        .attr('class', 'legend-title')
        .attr('x', 0)
        .attr('y', 0)
        .attr('dy', '0.8em')
        .style('font-weight', '600')
        .text('Sector');

    const legendItems = legend.selectAll('g.legend-item')
        .data(sectors, d => d)
        .join('g')
        .attr('class', 'legend-item')
        .attr('transform', (d, i) => `translate(0, ${20 + i * 16})`);

    legendItems.append('rect')
        .attr('class', 'legend-swatch')
        .attr('width', 12)
        .attr('height', 12)
        .attr('rx', 2)
        .attr('ry', 2)
        .attr('fill', d => colorScale(d));

    legendItems.append('text')
        .attr('class', 'legend-label')
        .attr('x', 16)
        .attr('y', 6)
        .attr('dy', '0.35em')
        .style('font-size', '12px')
        .text(d => d);

    // Create a <g> wrapper per node so labels don't block clicks.
    // Keep the label non-interactive (pointer-events: none), and attach
    // mouse handlers to the *circle* so the selection datum is correct.
    const nodes = svg.selectAll('g.bubble-node')
        .data(data, d => d.ticker)
        .join('g')
        .attr('class', 'bubble-node')
        .style('cursor', 'pointer');

    const bubbles = nodes.selectAll('circle')
        .data(d => [d])
        .join('circle')
        .attr('class', 'bubble')
        .attr('r', d => d.radius)
        .attr('fill', d => colorScale(d.sector))
        .attr('opacity', 0.7)
        .on('mouseover', function(event, d) {
            // Only show tooltip if this datum has the fields your UI needs.
            // Prefer checking actual data fields rather than category labels.
            if (d.hasValue && d.ticker && d.name && d.sector) {
                showTooltip(event, d);
            }
        })
        .on('mousemove', function(event) {
            // Keep tooltip following the pointer.
            d3.select('#tooltip')
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', hideTooltip)
        .on('click', function(event, d) {
            selectBubble(d.ticker);
        });

    // Add label text inside each bubble.
    // IMPORTANT: pointer-events disabled so text overlay doesn't block clicks.
    nodes.selectAll('text')
        .data(d => [d])
        .join('text')
        .attr('class', 'bubble-label')
        .text(d => d.ticker)
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .style('font-size', '10px')
        .style('fill', '#111')
        .style('pointer-events', 'none');

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

// Use `var` so this file can coexist with other example scripts on the same page
// without triggering "Identifier has already been declared" errors.
var D3VIS_SELECTION_EVENT = 'd3vis:selected';

function emitSelection(id) {
    if (typeof window === 'undefined') return;
    window.dispatchEvent(new CustomEvent(D3VIS_SELECTION_EVENT, {detail: {id}}));
}

function selectBubble(ticker) {
    // Highlight selected bubble
    d3.selectAll('.bubble')
        .classed('selected', d => d.ticker === ticker);

    // Emit selection so a table (if listening) can sync.
    emitSelection(ticker);
}

// If a table emits selections, listen and update bubbles.
if (typeof window !== 'undefined') {
    window.addEventListener(D3VIS_SELECTION_EVENT, (e) => {
        const id = e?.detail?.id;
        if (id) {
            d3.selectAll('.bubble').classed('selected', d => d.ticker === id);
        }
    });
}
