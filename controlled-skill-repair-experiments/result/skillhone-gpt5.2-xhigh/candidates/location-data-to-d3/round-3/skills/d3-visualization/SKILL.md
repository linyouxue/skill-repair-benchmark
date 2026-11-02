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

Always follow the task’s **required output paths**. If the user provides an output contract (exact filenames/locations), create **those files exactly**.

Common deliverable patterns:

1) **Single-page web app (offline)**
- `index.html`
- `js/…` (your visualization logic, plus a locally vendored D3 bundle)
- `css/…`
- `data/…` (a copy of the provided input data when the task requires “offline” / “no network”)

2) **Static artifacts (when requested)**
- `chart.svg` — exported SVG (stable and diff-friendly)
- `chart.png` — rasterized (only if explicitly requested)

If the task does **not** specify a structure, default to a predictable folder like `dist/` and keep all referenced assets relative to the HTML file.

### Output-contract checklist (single-page web app)

When the user asks for an offline single-page web app with specific required paths, double-check you produced **all** required files and folders.

A common required layout looks like:

```
OUTPUT_ROOT/
  index.html
  js/
    d3.v6.min.js
    visualization.js
  css/
    style.css
  data/
    … copied input data files …
```

**Notes:**
- Use **relative URLs** in `index.html` (e.g., `js/visualization.js`, not absolute `/js/…`) unless the task explicitly requires absolute paths.
- If the task requires copying input data into `OUTPUT_ROOT/data/`, copy it **byte-for-byte** (no reformatting) and load from that location.
- If the task requires a specific D3 version, ensure the vendored file path and `<script src>` match it exactly (e.g., `js/d3.v6.min.js`).
- If your repo/skill bundle already includes a vendored D3 file, **copy it verbatim** into the required output path instead of downloading from the network (example: `skills/d3-visualization/vendor/d3.v6.min.js` → `OUTPUT_ROOT/js/d3.v6.min.js`).

### Browser file:// loading caveat

Many browsers block `fetch()`/`d3.csv()` when opening `index.html` via `file://…`.
- If the task environment serves files over HTTP, runtime loading via `d3.csv('data/…')` is fine.
- If the task must work by double-clicking `index.html`, consider **embedding parsed data** into `visualization.js` at build time (while still copying the original data files if required).

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
- Pin D3 to the version the task asks for. If unspecified, choose and document a pinned version.
- Prefer vendoring a minified D3 bundle (e.g., `vendor/d3.v6.min.js` or `js/d3.v6.min.js` under the app output) or bundling with a lockfile.

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
  d3.v6.min.js      # pinned D3 library (or the version requested by the task)
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

CSS for highlighting:
```css
.bar.selected {
    stroke: #000;
    stroke-width: 3px;
}
```

### Clickable marks with overlaid text (labels)

When you place a `<text>` label on top of a clickable shape (e.g., bubble labels inside circles), the text can **steal mouse events** and make the underlying shape feel “unclickable”. Use one (or both) of these patterns:

**Pattern A — attach handlers to a parent `<g>` node (recommended):**

```js
const node = svg.selectAll('g.node')
  .data(data, d => d.key)
  .join(enter => {
    const g = enter.append('g').attr('class', 'node');
    g.append('circle').attr('class', 'bubble');
    g.append('text')
      .attr('class', 'label')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('pointer-events', 'none'); // label never blocks hover/click
    return g;
  });

node.on('click', (event, d) => setSelected(d.key));
```

**Pattern B — keep handlers on the shape, but disable pointer events on text:**

```css
.label { pointer-events: none; user-select: none; }
```

This prevents “dead zones” where only the circle edge is clickable.

### Bidirectional linking (chart ↔ table) for selection/highlighting

For tasks that require a chart and a table to stay in sync (click a mark highlights its row, and clicking a row highlights its mark), avoid ad-hoc cross-calls like `highlightBubble()` vs `selectBubble()`.

Use a **single source of truth** for selection and update both views from it.

A simple, robust pattern is `d3.dispatch`, with a **shared dispatch instance** so separate scripts/components can communicate.

```js
// Create once (global) so chart.js and table.js can share it.
function getSelectionDispatch() {
  if (!window.__d3_selection_dispatch__) {
    window.__d3_selection_dispatch__ = d3.dispatch('select');
  }
  return window.__d3_selection_dispatch__;
}

const dispatch = getSelectionDispatch();

function setSelected(key) {
  dispatch.call('select', null, key);
}

dispatch.on('select.chart', key => {
  svg.selectAll('g.node').classed('selected', d => d.key === key);
});

dispatch.on('select.table', key => {
  d3.selectAll('#data-table tbody tr').classed('selected', d => d.key === key);
});

// Hook both UI sources into the SAME setter
nodes.on('click', (event, d) => setSelected(d.key));
rows.on('click', (event, d) => setSelected(d.key));
```

**Implementation notes:**
- Use a stable key (`ticker`, `id`, etc.) and bind it consistently in both components.
- Prefer one CSS class (`.selected`) for the synced state.
- If you render labels, ensure the label layer doesn’t break interaction (see section above).

### Acceptance checklist for interactive selection

Before finishing, manually verify:
- Clicking a mark selects/highlights **both** the mark and its table row.
- Clicking a table row selects/highlights **both** the row and its chart mark.
- Clicking directly on the **label text** still triggers the same selection.
- Selecting from either view does **not** require two clicks (no “toggle only” behavior).

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
