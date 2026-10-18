---
name: d3-visualization
description: Build deterministic, verifiable data visualizations with D3.js (v6). Generate standalone HTML/SVG (and optional PNG) from local data files without external network dependencies. Use when tasks require charts, plots, axes/scales, legends, tooltips, or data-driven SVG output.
---

# D3.js Visualization Skill

Use this skill to turn structured data (CSV/TSV/JSON) into **clean, reproducible** visualizations using **D3.js**. The goal is to produce **stable outputs** that can be verified by diffing files or hashing.

## When to use

Activate this skill when the user asks for any of the following:

- “Make a chart/plot/graph/visualization”
- bar/line/scatter/area/histogram/box/violin/heatmap
- timelines, small multiples, faceting
- axis ticks, scales, legends, tooltips
- data-driven SVG output for a report or web page
- converting data to a static SVG or HTML visualization

If the user only needs a quick table or summary, **don’t** use D3—use a spreadsheet or plain markdown instead.

---

## Inputs you should expect

- One or more local data files: `*.csv`, `*.tsv`, `*.json`
- A chart intent:
  - chart type (or you infer the best type)
  - x/y fields and aggregation rules
  - sorting/filtering rules
  - dimensions (width/height) and margins
  - color rules (categorical / sequential)
  - any labeling requirements (title, axis labels, units)
- Output constraints:
  - “static only”, “no animation”, “must be deterministic”, “offline”, etc.

If details are missing, **make reasonable defaults** and document them in comments near the top of the output file.

---

## Outputs you should produce

Prefer producing **all of** the following when feasible:

1. `dist/chart.html` — standalone HTML that renders the visualization
2. `dist/chart.svg` — exported SVG (stable and diff-friendly)
3. (Optional) `dist/chart.png` — if the task explicitly needs a raster image

Always keep outputs in a predictable folder (default: `dist/`), unless the task specifies paths.

---

## Determinism rules (non-negotiable)

To keep results stable across runs and machines:

### Data determinism
- **Sort** input rows deterministically before binding to marks (e.g., by x then by category).
- Use stable grouping order (explicit `Array.from(grouped.keys()).sort()`).
- Avoid locale-dependent formatting unless fixed (use `d3.format`, `d3.timeFormat` with explicit formats).

### Rendering determinism
- **No randomness**: do not use `Math.random()` or `d3-random`.
- **No transitions/animations** by default (transitions can introduce timing variance).
- **Fixed** `width`, `height`, `margin`, `viewBox`.
- Use **explicit tick counts** only when needed; otherwise rely on D3 defaults but keep domains fixed.
- Avoid layout algorithms with non-deterministic iteration unless you control seeds/iterations (e.g., force simulation). If a force layout is required:
  - fix the tick count,
  - fix initial positions deterministically (e.g., sorted nodes placed on a grid),
  - run exactly N ticks and stop.



### Deterministic force-layout recipe (important for automated verification)

Force-directed charts must expose stable rendered geometry by the time tests or screenshots run.

Recommended pattern:
```javascript
const width = 960;
const height = 640;

const svg = d3.select('#chart')
  .attr('width', width)
  .attr('height', height)
  .attr('viewBox', [0, 0, width, height]);

nodes.forEach((d, i) => {
  // deterministic initial positions
  d.x = 120 + (i % 10) * 70;
  d.y = 120 + Math.floor(i / 10) * 70;
});

const simulation = d3.forceSimulation(nodes)
  .force('x', d3.forceX(d => centers[d.group].x).strength(0.2))
  .force('y', d3.forceY(d => centers[d.group].y).strength(0.2))
  .force('collide', d3.forceCollide(d => d.r + 2));

for (let i = 0; i < 300; i++) {
  simulation.tick();
}

node.attr('transform', d => `translate(${d.x},${d.y})`);
simulation.stop();
```

Guidelines:
- Set explicit SVG `width` and `height` attributes (not CSS-only sizing).
- Initialize node positions deterministically before starting the simulation.
- Run a fixed number of `simulation.tick()` calls (or until a fixed alpha threshold) after nodes exist in the DOM.
- Update positions on the same rendered element automation tools measure (`transform`, `cx/cy`, or equivalent).
- Stop the simulation only after final rendered positions are written.
- Validate that node positions are not collapsed: x/y spread should be non-zero and nodes should not all share the same `transform`, `cx`, or `cy` values.
### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- Pin D3 to a specific version (default: **d3@7.9.0**).
- Prefer vendoring a minified D3 bundle (e.g., `vendor/d3.v7.9.0.min.js`) or bundling with a lockfile.

### File determinism
- Stable SVG output:
  - Avoid auto-generated IDs that may change.
  - If you must use IDs (clipPath, gradients), derive them from stable strings (e.g., `"clip-plot"`).
- Use LF line endings.
- Keep numeric precision consistent (e.g., round to 2–4 decimals if needed).

---

## Recommended project layout

If the task doesn't specify an existing structure, use:

```
dist/
  chart.html        # standalone HTML with inline or linked JS/CSS
  chart.svg         # exported SVG (optional but nice)
  chart.png         # rasterized (optional)
vendor/
  d3.v7.9.0.min.js  # pinned D3 library
```

---

## Interactive features (tooltips, click handlers, hover effects)

When the task requires interactivity (e.g., tooltips on hover, click to highlight):

### Tooltip pattern (recommended)



### Automation-proof interactivity & layering

Interactive SVG charts often fail automated click/hover tests because labels or overlays intercept pointer events.

Recommended node structure:
```javascript
const node = svg.selectAll('g.node')
  .data(data)
  .join('g')
  .attr('class', 'node')
  .attr('data-ticker', d => d.ticker);

node.append('circle')
  .attr('class', 'bubble');

node.append('text')
  .attr('class', 'bubble-label')
  .style('pointer-events', 'none')
  .text(d => d.ticker);

node.on('click', handleClick);
node.on('mouseenter', handleEnter);
```

Equivalent CSS:
```css
svg text,
svg .bubble-label,
svg .annotation {
  pointer-events: none;
}
```

Guidelines:
- Apply `pointer-events: none` to non-interactive overlay labels, annotations, and decorative layers.
- Attach click/hover handlers to the intended hit target (`circle`) or a wrapping `g.node`, not to labels.
- Keep interactive marks unobstructed by transparent overlays or neighboring panels.
- Use stable selectors/classes/data attributes (`.node`, `.bubble`, `[data-ticker]`) for browser automation and linked-view interactions.
1. **Create a tooltip element** in HTML:
```html
<div id="tooltip" class="tooltip"></div>
```

2. **Style with CSS** using `.visible` class for show/hide:
```css
.tooltip {
    position: absolute;
    padding: 10px;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    border-radius: 4px;
    pointer-events: none;  /* Prevent mouse interference */
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 1000;
}

.tooltip.visible {
    opacity: 1;  /* Show when .visible class is added */
}
```

3. **Add event handlers** to SVG elements:
```javascript
svg.selectAll('circle')
    .on('mouseover', function(event, d) {
        d3.select('#tooltip')
            .classed('visible', true)  // Add .visible class
            .html(`<strong>${d.name}</strong><br/>${d.value}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
    })
    .on('mouseout', function() {
        d3.select('#tooltip').classed('visible', false);  // Remove .visible class
    });
```

**Key points:**
- Use `opacity: 0` by default (not `display: none`) for smooth transitions
- Use `.classed('visible', true/false)` to toggle visibility
- `pointer-events: none` prevents tooltip from blocking mouse events
- Position tooltip relative to mouse with `event.pageX/pageY`



Additional tooltip robustness guidance:
- Prefer `mouseenter`, `mousemove`, and `mouseleave` (or pointer-event equivalents) on the interactive node container (`g.node`).
- Standardize tooltip positioning on `event.pageX/pageY` or `clientX/clientY` plus scroll offsets. Avoid coordinate systems tied to nested SVG transforms unless necessary.
- Keep tooltip visibility controlled via explicit classes or opacity state so tests can verify visible/hidden status.
- Ensure the tooltip has a sufficiently high `z-index` and `pointer-events: none` so it never blocks hover/click behavior.
- When conditionally suppressing tooltips (for excluded categories or ETFs), verify the filtering logic does not accidentally disable all tooltips.
### Click handlers for selection/highlighting

```javascript
// Add 'selected' class on click
svg.selectAll('.bar')
    .on('click', function(event, d) {
        // Remove previous selection
        d3.selectAll('.bar').classed('selected', false);
        // Add to clicked element
        d3.select(this).classed('selected', true);
    });
```

CSS for highlighting:
```css
.bar.selected {
    stroke: #000;
    stroke-width: 3px;
}
```

### Conditional interactivity

Sometimes only certain elements should be interactive:
```javascript
.on('mouseover', function(event, d) {
    // Example: Don't show tooltip for certain categories
    if (d.category === 'excluded') {
        return;  // Exit early, no tooltip
    }
    // Show tooltip for others
    showTooltip(event, d);
})
```

---


## Playwright-oriented interaction checklist

Before finalizing an interactive D3 visualization, verify:
- Bubbles/nodes are directly clickable and not occluded by labels or overlays.
- Non-interactive SVG text and annotations use `pointer-events: none`.
- Tooltip appears on hover for intended nodes and hides cleanly on mouse leave.
- Interactive elements expose stable selectors/classes/data attributes.
- Linked selections are reflected via deterministic classes or attributes such as `.selected`, `.active`, or `aria-selected`.
- Force-layout charts show non-zero spatial spread and stable rendered positions before screenshots or assertions run.
