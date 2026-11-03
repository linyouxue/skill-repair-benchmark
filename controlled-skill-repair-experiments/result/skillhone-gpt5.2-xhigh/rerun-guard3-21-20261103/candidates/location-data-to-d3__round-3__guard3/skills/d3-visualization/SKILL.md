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

### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- Pin D3 to a specific version that matches the task requirement (default: **D3 v6**, e.g. **d3@6.7.0**).
- Prefer vendoring a minified D3 bundle (e.g., `vendor/d3.v6.min.js` or `vendor/d3.v6.7.0.min.js`) or bundling with a lockfile.

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
  d3.v6.min.js      # pinned D3 v6 library (or d3.v6.x.y.min.js)
```

---

## Legends (categorical color scales)

Tasks that color marks by a categorical field (e.g., sector, category, group) should include a **legend that lists every category present in the bound data**.

### Legend rules for correctness + determinism

- Build the legend entries from the **same domain** used by your color scale (usually `colorScale.domain()`).
- Derive the categorical domain from the **full dataset** (before filtering for size/tooltip/visibility). Example pitfall: if you size bubbles only for rows with `marketCap`, you must still include rows without `marketCap` when computing the sector list so the legend stays complete.
- Ensure the domain includes **all rows**, including items that may have missing values for other fields (e.g., points without a size metric still have a category and should still be shown in the legend).
- If some rows have missing/blank category values, map them to a stable placeholder (e.g., `"Unknown"`) so they still render deterministically and are accounted for.
- Make the domain order deterministic:
  - `Array.from(new Set(values)).sort(d3.ascending)`
- If the number of categories exceeds a fixed palette (e.g., 10), use a palette generator (e.g., `d3.quantize(d3.interpolateRainbow, n)`) so the legend can still list all categories.
- Keep legend labels as the **raw category strings** (avoid adding counts or abbreviations) unless the task explicitly asks for that.

### Minimal categorical legend pattern

Use stable class names so downstream checks/tests can reliably locate the legend.

```js
// categories MUST match the color scale domain exactly.
const categories = colorScale.domain();

const legend = svg.append('g')
  .attr('class', 'legend')
  .attr('transform', 'translate(20,20)');

legend.append('text')
  .attr('class', 'legend-title')
  .attr('x', 0)
  .attr('y', 0)
  .attr('dy', '0.8em')
  .style('font-weight', '600')
  .text('Category');

const items = legend.selectAll('g.legend-item')
  .data(categories, d => d)
  .join('g')
  .attr('class', 'legend-item')
  .attr('transform', (d, i) => `translate(0, ${20 + i * 16})`);

items.append('rect')
  .attr('class', 'legend-swatch')
  .attr('width', 12)
  .attr('height', 12)
  .attr('rx', 2)
  .attr('ry', 2)
  .attr('fill', d => colorScale(d));

items.append('text')
  .attr('class', 'legend-label')
  .attr('x', 16)
  .attr('y', 6)
  .attr('dy', '0.35em')
  .style('font-size', '12px')
  .text(d => d);
```

#### Legend acceptance checklist (manual)

- The legend exists and is visible without scrolling the page.
- The legend has **one entry per unique category in the data** (no “top N” truncation).
- Categories are not accidentally dropped because other fields are missing.
- The swatch color matches the marks’ fill color.

---

## Interactive features (tooltips, click handlers, hover effects)

When the task requires interactivity (e.g., tooltips on hover, click to highlight):

### Tooltip pattern (recommended)

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

#### Composite marks (e.g., bubble + label): keep clicks/hover working

If you draw a **shape** (e.g., `<circle>`) and then a **text label** on top, the text can accidentally block mouse events.

Two safe patterns:

**Pattern A — disable pointer events on overlay text** (simple and common):
```javascript
node.append('text')
  .text(d => d.label)
  .attr('text-anchor', 'middle')
  .attr('dy', '0.35em')
  .style('pointer-events', 'none'); // critical: let the circle receive clicks
```

**Pattern B — attach handlers to the parent `<g>`** (works even if text receives events):
```javascript
const node = svg.selectAll('g.node')
  .data(data, d => d.id)
  .join('g')
  .attr('class', 'node')
  .style('cursor', 'pointer');

node.on('click', (event, d) => setSelected(d.id));
```

Tip: prefer `mouseenter`/`mouseleave` on the interactive target to avoid tooltip flicker when moving between child elements.

#### Two-way linking (chart ↔ table) with a single selection state

When a task requires **bidirectional selection** (click bubble → highlight row, click row → highlight bubble), use **one shared selection key** and update both views from one place.

Minimal pattern:
```javascript
let selectedId = null;

function setSelected(id) {
  selectedId = id;
  bubbles.classed('selected', d => d.id === selectedId);
  rows.classed('selected', d => d.id === selectedId);
}

bubbles.on('click', (event, d) => setSelected(d.id));
rows.on('click', (event, d) => setSelected(d.id));
```

Event-bus pattern (useful when chart and table live in different files):
```javascript
const SELECTION_EVENT = 'd3vis:selected'; // shared event type across files (declare with `var` in non-module scripts to avoid redeclare errors)

function emitSelect(id) {
  window.dispatchEvent(new CustomEvent(SELECTION_EVENT, { detail: { id } }));
}

window.addEventListener(SELECTION_EVENT, (e) => {
  const id = e.detail?.id;
  bubbles.classed('selected', d => d.id === id);
  rows.classed('selected', d => d.id === id);
});

bubbles.on('click', (event, d) => emitSelect(d.id));
rows.on('click', (event, d) => emitSelect(d.id));
```

#### Interactivity acceptance checklist (manual)

Before shipping, verify these behaviors in the browser:
- Clicking **the shape or its label text** selects the item (label overlay must not block clicks).
- Exactly one item is selected at a time (previous selection clears).
- Selecting in the chart highlights the corresponding table row **immediately**, and selecting in the table highlights the corresponding chart mark.
- Interactive marks use `cursor: pointer` and selection styling is visible (e.g., stroke on bubbles, background on rows).

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
