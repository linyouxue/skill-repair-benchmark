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



#### Clickable bubbles + overlaid labels (avoid common pitfalls)
When bubbles need **both** (a) a clickable/hoverable mark and (b) a text label drawn on top, use a **node container** pattern and keep the label from intercepting pointer events.

**Deterministic node structure (recommended):**
- One `<g class="node">` per datum.
- Attach interaction handlers to the **`g.node`** (or the `circle`), not the `text`.
- Append the `circle` first and `text` second so the label is visually on top.
- Set `pointer-events: none` on the `text` so it does not block hover/click.
- Add `cursor: pointer` on interactive nodes.

```js
const keyFn = d => d.ticker; // stable unique id

const node = nodesLayer.selectAll('g.node')
  .data(dataSorted, keyFn)
  .join(enter => {
    const g = enter.append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer');

    g.append('circle')
      .attr('r', d => r(d))
      .attr('fill', d => color(d.sector));

    g.append('text')
      .attr('class', 'label')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .style('pointer-events', 'none') // critical: label must not block interactions
      .text(d => d.ticker);

    return g;
  });

// attach handlers to g.node (so clicks work even when mouse is over text)
node.on('mouseenter', (event, d) => showTooltipIfAllowed(event, d))
    .on('mouseleave', hideTooltip)
    .on('click', (event, d) => setSelected(d.ticker));
```

**Layering option for clarity:** use separate layers to control z-order.
```js
const bubblesLayer = svg.append('g').attr('class', 'bubbles');
const labelsLayer  = svg.append('g').attr('class', 'labels');
// render circles in bubblesLayer; render text in labelsLayer.
// Still set labelsLayer text { pointer-events:none }.
```

**CSS snippet:**
```css
.label { font: 12px sans-serif; fill: #111; }
.node.selected circle { stroke: #000; stroke-width: 2px; }
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



### Deterministic joins for updates (always use a stable key)
For any chart/table that can update, re-render, or synchronize selection state, **always** use keyed data joins:

```js
const keyFn = d => d.ticker; // or another stable unique id
selection = selection.data(dataSorted, keyFn).join('...');
```

Avoid index-based joins (`.data(data)`) because filtering/sorting will cause DOM/data mismatches and break highlighting and tooltips.

### Chart ↔ Table two-way linking (single shared selection state)
For linked interactions (click a bubble highlights a table row, and click a row highlights a bubble), implement:
1) **One shared state variable** (e.g., `selectedTicker`) and
2) **Centralized update functions** (`setSelected`, `clearSelection`, `renderSelection`).

**Pattern (recommended):**
```js
let selectedTicker = null;

function setSelected(ticker) {
  selectedTicker = ticker;
  renderSelection();
}

function clearSelection() {
  selectedTicker = null;
  renderSelection();
}

function renderSelection() {
  // bubbles
  nodesLayer.selectAll('g.node')
    .classed('selected', d => d.ticker === selectedTicker)
    .classed('dimmed', d => selectedTicker && d.ticker !== selectedTicker);

  // table rows
  d3.select('#table').selectAll('tr.data-row')
    .classed('selected', d => d.ticker === selectedTicker);

  // optional: scroll selected row into view
  const row = d3.select('#table').selectAll('tr.data-row')
    .filter(d => d.ticker === selectedTicker).node();
  if (row) row.scrollIntoView({ block: 'nearest' });
}

// bubble -> state
nodesLayer.selectAll('g.node')
  .on('click', (event, d) => {
    // allow toggling off if clicking the already-selected item
    if (selectedTicker === d.ticker) clearSelection();
    else setSelected(d.ticker);
    event.stopPropagation();
  });

// row -> state
rows.on('click', (event, d) => {
  if (selectedTicker === d.ticker) clearSelection();
  else setSelected(d.ticker);
  event.stopPropagation();
});

// click background to clear
svg.on('click', clearSelection);
```

**Notes that prevent common bugs:**
- Apply CSS classes (`.selected`, `.dimmed`) to **both** bubbles and rows from the same `renderSelection()`.
- If labels are separate elements, ensure labels do not block events (`pointer-events:none`).
- Keep all data joins keyed by the same stable key (e.g., ticker) in both chart and table.
---



## Acceptance checklist (interactive bubble chart + linked table)
Use this to verify implementations are correct and robust:

- **Bubble hover**: tooltip appears on hover for eligible items and does **not** flicker when crossing label text (label must not intercept pointer events).
- **Bubble click → row highlight**: clicking a bubble highlights the corresponding table row deterministically.
- **Row click → bubble highlight**: clicking a row highlights the corresponding bubble deterministically.
- **Single source of truth**: selection state is stored once (e.g., `selectedTicker`) and all views update via one `renderSelection()`.
- **Stable keyed joins**: all `.data(..., keyFn)` use a stable unique key (e.g., ticker) for both bubbles and table rows; re-sorting/filtering does not break selection mapping.
- **Z-order correctness**: circles render below labels (either via append order or separate layers) and labels remain visible.
- **Pointer event correctness**: label elements use `pointer-events: none`; interactive marks or containers use `cursor: pointer`.
- **Repeated selection behavior**: clicking the same bubble/row again either (a) toggles off (if specified) or (b) remains selected, but behavior is consistent.
- **Optional clear**: clicking the background clears selection (if implemented) without leaving stale highlights.
- **Optional scroll-into-view**: selecting a bubble can scroll its row into view without changing selection state.
