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
  - sort nodes by a stable key such as normalized ticker and assign deterministic initial positions;
  - define fixed chart bounds and sector anchor coordinates near the chart center;
  - use `forceX`/`forceY` for sector clustering and `forceCollide` with each node's measured radius plus padding;
  - run a bounded, explicit number of ticks, stop the simulation, and clamp or validate final coordinates so circles and labels remain inside the SVG;
  - render only after the simulation has settled, rather than depending on a timing-sensitive animation or an arbitrary browser timeout.

### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- Pin D3 to the task-required **v6** release and verify the vendored bundle is actually D3 v6 (for example, `output/js/d3.v6.min.js`). Never substitute D3 v7 APIs or load D3 from a CDN.
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



## Integrated local stock-visualization workflow

For an integrated local web-app task, follow this sequence instead of coding from assumptions:

1. **Inventory and inspect inputs.** List every supplied file, including all files under the individual-stock directory. Read the actual bytes and inspect encoding, delimiter, header spelling/case, BOMs, quoting, line endings, and record counts. Do not infer field names from the prompt or from one sample file. Identify which file supplies the 50 company records and which files supply price histories, and record any ticker variants, duplicate rows, missing columns, ETF markers, malformed numbers, or missing metadata.
2. **Create one canonical model before rendering.** Normalize headers and values into a single stock object per required record, including a stable ticker key, display ticker, full company name, sector, ETF status, market-cap number or explicit null, and any history reference. Normalize ticker keys consistently for joins but preserve display text. Assert that the required 50 records survive parsing, that every canonical ticker key is nonempty and unique, and that every record has a corresponding bubble and table row. Fail loudly or diagnose the source data when an assertion fails; do not silently drop rows during per-file joins.
3. **Build the exact offline output tree.** For the stock-app task, produce `/root/output/index.html`, `/root/output/js/d3.v6.min.js`, `/root/output/js/visualization.js`, `/root/output/css/style.css`, and `/root/output/data/` containing copies of the supplied input data. Reference only local assets. Since browsers generally block `fetch()` of local files opened with `file://`, either embed a generated canonical data payload in the local JavaScript/HTML while retaining the copied source files, or explicitly run and test through a local HTTP server; never depend on a network URL. Confirm the local bundle is D3 v6 before implementation.
4. **Render from the canonical model only.** Bind both bubbles and rows to the same canonical array and stable ticker key. Compute market-cap radii with a readable area/radius scale; give ETFs and missing/invalid market caps a documented uniform fallback. Use stable sector colors and include every represented sector in the legend. Place sector anchors within the chart, use bounded deterministic force clustering and collision handling, and keep ticker labels inside bubbles. Format market caps with stable K/M/B/T notation. For a non-ETF, show a safely constructed tooltip containing ticker, full name, and sector; for an ETF, do not show a tooltip or fabricate unavailable metadata.
5. **Use one shared selection state.** Implement a single selected-ticker value or equivalent keyed state. Bubble clicks must update the matching row and bubble together; row clicks must update the matching bubble and row together; selecting a new item must clear stale highlights. Use keyed joins, explicit selected classes, and keyboard/focus handling where practical so the behavior is testable without relying on visual inspection.
6. **Verify with browser-level checks before delivery.** Check the exact file tree, copied data, D3 v6 script, and absence of external requests. Load the page through the relevant `file://` or local-server mode and inspect console and network errors. Programmatically or with a headless browser assert 50 table rows, 50 bubbles, unique one-to-one ticker correspondence, the four required table columns, complete sector legend coverage, ETF tooltip exceptions, valid formatted market-cap cells, bounded non-overlapping bubble geometry, and settled ticker labels. Exercise both selection directions with representative normal, ETF, missing-field, and unusual-ticker records; diagnose and fix any failure before returning the app.
