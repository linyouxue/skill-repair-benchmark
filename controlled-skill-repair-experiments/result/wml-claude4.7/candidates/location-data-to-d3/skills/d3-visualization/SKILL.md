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

### In-shape label overlay (text drawn on top of marks)

Use this pattern when a mark (circle/rect/path) must carry an **in-situ textual identifier**
(e.g., a ticker symbol inside a bubble, a short code inside a cell). The label layer must
not interfere with click/hover on the mark beneath it.

**Mechanism:**

1. **Append a parallel `<text>` selection** bound to the same data array as the marks.
   Keep the two selections sibling layers in the SVG; draw text **after** marks so it renders on top.

2. **Center the label on the mark** with:
   - `text-anchor="middle"` (horizontal centering)
   - `dominant-baseline="central"` (vertical centering)

3. **Keep text position synchronized** with the mark. If a force simulation is used,
   update both selections inside the same `tick` handler using `d.x` / `d.y`:

```javascript
const labels = svg.selectAll('text.bubble-label')
    .data(data, d => d.ticker)   // same key as the circles
    .join('text')
    .attr('class', 'bubble-label')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'central')
    .attr('font-size', d => Math.max(8, d.radius * 0.5))  // scale with radius
    .text(d => d.radius >= MIN_LABEL_RADIUS ? d.ticker : ''); // skip when too small

simulation.on('tick', () => {
    bubbles.attr('cx', d => d.x).attr('cy', d => d.y);
    labels.attr('x', d => d.x).attr('y', d => d.y);
});
```

4. **Make the overlay pointer-transparent** so clicks/hovers continue to reach the mark below.
   Set this either in CSS or as an attribute on the text selection:

```css
.bubble-label {
    pointer-events: none;    /* clicks/hover pass through to the circle underneath */
    user-select: none;
}
```

5. **Legibility threshold**: when the underlying mark is too small to host readable text,
   emit an empty string (as shown above) rather than clipping or overflowing. Pick a
   `MIN_LABEL_RADIUS` consistent with the chosen `font-size` scaling.

**Scope note:** this pattern is for annotation layers that identify the mark they sit on.
It is **not** a substitute for axis tick labels, external legends, or tooltip content, and
should not be applied to overlays that must themselves receive events (e.g., close buttons).

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

#### Cross-view selection (bidirectional chart ↔ table linkage)

When two or more views (e.g., a chart of marks and a tabular list of rows) represent the
**same entities** and must stay in sync — a click in either view must highlight the matching
entity in both — use a shared **stable key** and a pair of symmetric handlers.

**Mechanism:**

1. **Pick one stable key** that uniquely identifies an entity across views (e.g., `ticker`).
   Both the mark selection and the row selection must be data-joined with this same key.

2. **Define two symmetric selection functions.** Each one is the single source of truth for
   its originating view, and each updates **both** views by the shared key:

```javascript
// Called when the user clicks a bubble in the chart.
function selectFromChart(key) {
    // Clear prior selection on BOTH views
    d3.selectAll('.bubble').classed('selected', false);
    d3.selectAll('#data-table tbody tr').classed('selected', false);
    // Set selection on BOTH views by shared key
    d3.selectAll('.bubble').filter(d => d.ticker === key).classed('selected', true);
    d3.selectAll('#data-table tbody tr').filter(d => d.ticker === key).classed('selected', true);
}

// Called when the user clicks a row in the table.
function selectFromTable(key) {
    // Same symmetric behavior — the two handlers are intentionally mirror images.
    d3.selectAll('.bubble').classed('selected', false);
    d3.selectAll('#data-table tbody tr').classed('selected', false);
    d3.selectAll('.bubble').filter(d => d.ticker === key).classed('selected', true);
    d3.selectAll('#data-table tbody tr').filter(d => d.ticker === key).classed('selected', true);
}
```

3. **Wire each view's click to its handler:**

```javascript
bubbles.on('click', (event, d) => selectFromChart(d.ticker));
rows.on('click',    (event, d) => selectFromTable(d.ticker));
```

4. **Style `.selected` on both views** so the highlight is visible wherever the entity appears:

```css
circle.bubble.selected {
    stroke: #000;
    stroke-width: 3px;
}
tr.selected {
    background: #e3f2fd;
    border-left: 3px solid #2196f3;
}
```

5. **If the bundled helpers are used** (`scripts/interactive_table_example.js` exposes
   `highlightTableRow(ticker)` and the bubble-chart example exposes `highlightBubble(ticker)`),
   invoke them **symmetrically** from both click handlers — not just one direction — so that
   clicking either view updates the other.

**Interaction with the in-shape label overlay:** because selection relies on `click` events
reaching the mark, any overlay drawn on top of the mark (see “In-shape label overlay”) **must**
have `pointer-events: none`. Otherwise the overlay silently intercepts clicks and the
bidirectional linkage will appear to work from table → chart but not from chart → table.

**Scope note:** this pattern applies to selection of a single shared entity. Do not reuse the
same channel to synchronize unrelated state (filters, sorts, hover-only highlights, multi-select)
unless those are explicitly required — those need their own, separately-named channels.

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
