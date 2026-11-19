---
name: d3-visualization
description: Build deterministic, verifiable data visualizations with D3.js (v6+). Generate standalone HTML/SVG (and optional PNG) from local data files without external network dependencies; this bundle includes a vendored D3 v6 build for offline tasks.
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

Always keep outputs in a predictable folder (default: `dist/`), **unless the task specifies exact paths** (follow user-specified paths verbatim).

---

## Determinism rules (non-negotiable)

To keep results stable across runs and machines:

### Data determinism
- **Sort** input rows deterministically before binding to marks (e.g., by id/ticker then by category).
- Use stable grouping order (explicit `Array.from(grouped.keys()).sort()`).
- Avoid locale-dependent formatting unless fixed (use `d3.format`, `d3.timeFormat` with explicit formats).

### Rendering determinism
- **No randomness**: do not use `Math.random()` or `d3-random`.
- **No transitions/animations** by default (transitions can introduce timing variance).
- **Fixed** `width`, `height`, `margin`, `viewBox`.
- Use **explicit tick counts** only when needed; otherwise rely on D3 defaults but keep domains fixed.
- Avoid layout algorithms with non-deterministic iteration unless you control seeds/iterations (e.g., force simulation). If a force layout is required:
  - set initial `x/y` deterministically (so D3 does not randomize them),
  - run exactly **N ticks** and stop (or stop after N ticks for a deterministic final layout),
  - keep your category ordering stable (sorted).

### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- **Pin to the version the task requests.**
  - If the task requires **D3 v6**, prefer copying the vendored file shipped with this bundle:
    - `skills/d3-visualization/vendor/d3.v6.min.js` (currently **v6.7.0**)
  - If the task requires a different version, vendor it locally in-repo (avoid network at runtime).

**Why this matters:** some environments have no `curl`, no outbound network, or both.

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
  d3.v6.min.js      # pinned D3 library (offline)
```

If the user specifies an output layout (common for “single-page web app” tasks), follow it exactly. Example:

```
output/
  index.html
  js/
    d3.v6.min.js
    visualization.js
  css/
    style.css
  data/
    ...copied input data...
```

## Web-app output contract checklist (single-page app)

When the user specifies an output tree (common for “single-page web app” tasks), treat it like a **contract** and verify it before finishing:

1. **Create directories exactly** as requested (typically `js/`, `css/`, `data/`).
2. **Vendor D3 locally (no CDN):**
   - If D3 v6 is required, copy `skills/d3-visualization/vendor/d3.v6.min.js` to the requested `js/d3.v6.min.js` path.
3. **Copy input data into the output `data/` folder verbatim** (filenames unchanged). If the input includes a directory, copy it recursively.
4. **Use relative URLs** from `index.html`:
   - `css/style.css`, `js/d3.v6.min.js`, `js/visualization.js`, `data/...`
5. **Make data loading work offline:**
   - Many browsers block `fetch()` from `file://` pages. If the user expects “double-click to open”, prefer embedding the dataset into `visualization.js` (or inline in `index.html`) and parsing with `d3.csvParse` / `JSON.parse`.
   - If you choose `fetch()`, add a comment noting that the page must be served (e.g. `python3 -m http.server`) and test that workflow.
6. **Verify the file tree exists** (and is non-empty) as a last step (`ls -R <output-root>` or equivalent).

### Included template scaffold (copy/paste)

This bundle includes a minimal, offline-friendly single-page scaffold you can copy into the task’s required output root:

- `skills/d3-visualization/templates/single-page-app/index.html`
- `skills/d3-visualization/templates/single-page-app/css/style.css`
- `skills/d3-visualization/templates/single-page-app/js/visualization.js`

It is intentionally **data-agnostic** (you must map your fields and embed/serve your data as needed), but it already contains:
- a side-by-side layout,
- a tooltip + legend pattern,
- a deterministic clustered-bubble + linked-table wiring.

### Command-execution tool gotcha (common in agent runtimes)

Some agent “terminal” tools reject multiple separate commands in one call. If you need multiple steps, either:

- run separate tool calls, **or**
- chain commands with `&&` / `;` (example: `cmd1 && cmd2 && cmd3`).

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
      .classed('visible', true)
      .html(`<strong>${d.name}</strong><br/>${d.value}`)
      .style('left', (event.pageX + 10) + 'px')
      .style('top', (event.pageY - 10) + 'px');
  })
  .on('mouseout', function() {
    d3.select('#tooltip').classed('visible', false);
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
svg.selectAll('.mark')
  .on('click', function(event, d) {
    d3.selectAll('.mark').classed('selected', false);
    d3.select(this).classed('selected', true);
  });
```

CSS for highlighting:
```css
.mark.selected {
  stroke: #000;
  stroke-width: 3px;
}
```

### Linked selection (chart ↔ table)

For tasks that require clicking either a chart mark or a table row to highlight both:

- Pick **one shared id** (e.g., ticker, ISO code, primary key)
- Use that id as the `.data(..., keyFn)` key **and** as the selection state
- Expose two small, consistent APIs:
  - `highlightBubble(id)` updates the chart selection only
  - `highlightTableRow(id)` updates the table selection only

Then:
- chart click calls `highlightTableRow(id)`
- table click calls `highlightBubble(id)`

This avoids name mismatches and prevents recursive “click loops”.

### Deterministic force-simulation bubble clusters (sector clustering)

If a task asks for a clustered bubble chart using `forceX/forceY` + `forceCollide`:

- Sort sectors and assign **fixed cluster centers** (e.g., grid layout) so clusters stay close and centered.
- Set initial `x/y` to the sector center to avoid D3’s randomized initialization.
- Stop after a fixed number of ticks.

See `skills/d3-visualization/scripts/bubble_chart_example.js` for a reusable template.

---

## Local-file (file://) loading note

Many browsers block `fetch()` from `file://` URLs. If the user expects “double-click to open” behavior:

- Prefer embedding **minimal** preprocessed data into `visualization.js` at build time, **or**
- In instructions/comments, mention serving via a local web server:
  - `python3 -m http.server` and open `http://localhost:8000/`

Keep the web app offline-capable (no external network dependencies).
