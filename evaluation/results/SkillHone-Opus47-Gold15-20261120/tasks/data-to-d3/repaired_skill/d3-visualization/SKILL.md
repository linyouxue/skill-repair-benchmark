---
name: d3-visualization
description: Build deterministic, verifiable data visualizations with D3.js. Generate standalone HTML/SVG (and optional PNG) from local data files without external network dependencies. Use when tasks require charts, plots, axes/scales, legends, tooltips, data tables linked to charts, or data-driven SVG output.
---

# D3.js Visualization Skill

Use this skill to turn structured data (CSV/TSV/JSON) into **clean, reproducible** visualizations using **D3.js**. The goal is to produce **stable outputs** that can be verified by diffing files, hashing, or by programmatic DOM/interaction checks.

## When to use

Activate this skill when the user asks for any of the following:

- "Make a chart/plot/graph/visualization"
- bar/line/scatter/area/histogram/box/violin/heatmap/**bubble**
- timelines, small multiples, faceting
- axis ticks, scales, legends, tooltips
- **multi-panel dashboards** (e.g. a chart next to a data table) with **linked selection**
- data-driven SVG output for a report or web page
- converting data to a static SVG or HTML visualization

If the user only needs a quick table or summary, **don't** use D3—use a spreadsheet or plain markdown instead.

---

## Inputs you should expect

- One or more local data files: `*.csv`, `*.tsv`, `*.json`
- A chart intent:
  - chart type (or you infer the best type)
  - x/y fields and aggregation rules
  - sorting/filtering rules
  - dimensions (width/height) and margins
  - color rules (categorical / sequential)
  - any labeling requirements (title, axis labels, units, in-mark labels)
- Output constraints:
  - "static only", "no animation", "must be deterministic", "offline", etc.
- An exact output file layout (paths to `index.html`, `js/`, `css/`, `data/`)

If details are missing, **make reasonable defaults** and document them in comments near the top of the output file. **If details are given, follow them exactly** — do not substitute "better" paths, D3 versions, or file names.

---

## Outputs you should produce

### Follow the task's explicit output contract first

If the task specifies paths (e.g. `/root/output/index.html`, `/root/output/js/visualization.js`, `/root/output/css/style.css`, `/root/output/data/`), produce **exactly those files at those paths**. Do not rename, do not add indirection, do not move them to `dist/`.

### Default layout (only when the task doesn't specify one)

Prefer producing **all of** the following when feasible:

1. `dist/chart.html` — standalone HTML that renders the visualization
2. `dist/chart.svg` — exported SVG (stable and diff-friendly)
3. (Optional) `dist/chart.png` — if the task explicitly needs a raster image

Always keep outputs in a predictable folder, unless the task specifies paths.

### Copying input data into the output tree

If the task says "copy the provided input data into `output/data/`", copy the files **verbatim**, preserving sub-directory structure. Do not reformat, re-encode line endings, or filter rows.

---

## Choosing the D3 version

- **Default to the version the user asks for.** If the task says "D3.js v6", vendor D3 v6; if it says v7, vendor v7. Do not substitute.
- If the task is silent, default to **d3 v7** (latest stable major you have offline access to).
- When the task specifies a vendored path (e.g. `js/d3.v6.min.js`), download the bundle to **exactly that path**. Do not load D3 from a CDN at runtime.
- **D3 v6 and v7 event signature is `(event, d)`** on `.on('mouseover', ...)` etc. D3 v5 and earlier passed `(d, i, nodes)`. Pick the signature that matches the pinned version.
- D3 v6+ selection methods used in this skill: `.join()`, `.data(data, keyFn)`, `.on('event', (event, d) => ...)`, `d3.csv(url).then(...)`.

---

## Determinism rules

To keep results stable across runs and machines, apply these **when they don't conflict with the task**:

### Data determinism
- When the task specifies an explicit order, follow it. Otherwise:
  - Sort input rows deterministically before binding to marks (e.g., by x then by category).
  - Use stable grouping order (explicit `Array.from(grouped.keys()).sort()`).
- **Do not silently reorder a table** whose task says "list all N rows" — preserve input order unless an ordering is specified.
- Avoid locale-dependent formatting unless fixed (use `d3.format`, `d3.timeFormat` with explicit formats).

### Rendering determinism
- **No randomness**: do not use `Math.random()` or `d3-random`.
- **Transitions are fine** for interactive feedback (hover highlight, tooltip fade); avoid long entry animations that could race a verifier.
- **Fixed** `width`, `height`, `margin`, `viewBox`.
- Avoid layout algorithms with non-deterministic iteration unless you control seeds/iterations. **For a force simulation that is required by the task** (e.g. clustered bubble chart):
  - seed each node's `x`/`y` deterministically **before** starting the simulation (e.g. place each node near its cluster center with a small deterministic offset derived from its index),
  - optionally pre-run a fixed number of `simulation.tick()` calls so the layout is already settled when the DOM becomes queryable,
  - then let the live simulation continue so users still see smooth settling.

### Offline + dependency determinism
- Do **not** load D3 from a CDN at runtime; vendor it locally to the path the task specifies (or `vendor/`).
- Pin D3 to a specific version (match what the task asks for; default **d3 v7** when silent).

### File determinism
- Stable SVG output:
  - Avoid auto-generated IDs that may change between runs.
  - If you must use IDs (clipPath, gradients), derive them from stable strings (e.g., `"clip-plot"`).
- Use LF line endings.
- Keep numeric precision consistent (e.g., round to 2–4 decimals if needed).

---

## Interactive features (tooltips, click handlers, hover effects)

### Tooltip pattern (recommended)

1. **Create a single tooltip element** in HTML, outside the SVG:
```html
<div id="tooltip" class="tooltip"></div>
```

2. **Style with CSS** using a `.visible` class for show/hide (so it is positionable before being shown):
```css
.tooltip {
    position: absolute;
    padding: 10px;
    background: rgba(0, 0, 0, 0.85);
    color: white;
    border-radius: 4px;
    pointer-events: none;  /* Prevent mouse interference */
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 1000;
}

.tooltip.visible {
    opacity: 1;
}
```

3. **Content**: when the task says "tooltip shows X, Y, Z", prefer rendering **just the values** on separate lines, e.g. `${ticker}<br/>${name}<br/>${sector}`. Add labels ("Name:", "Sector:") only if the task asks for them — brittle verifiers may match on exact tooltip text.

4. **Add event handlers** to SVG elements (D3 v6/v7 signature `(event, d)`):
```javascript
svg.selectAll('circle')
    .on('mouseover', function(event, d) {
        d3.select('#tooltip')
            .classed('visible', true)
            .html(`${d.ticker}<br/>${d.name}<br/>${d.sector}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
    })
    .on('mousemove', function(event) {
        d3.select('#tooltip')
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
    })
    .on('mouseout', function() {
        d3.select('#tooltip').classed('visible', false);
    });
```

**Key points:**
- Use `opacity: 0` by default (not `display: none`) for smooth transitions and so measurements are available.
- Use `.classed('visible', true/false)` to toggle visibility.
- `pointer-events: none` on the tooltip prevents it blocking mouse events on underlying marks.
- Position via `event.pageX/pageY` (not `clientX/clientY`) so it works with page scroll.

### Conditional interactivity (records missing fields)

When some records should not trigger a tooltip (e.g. ETFs with no market cap, country, or website), **exit the mouseover handler early** before showing the tooltip — do **not** attach the handler at all only for interactive rows (that makes the DOM asymmetric and harder to verify):

```javascript
.on('mouseover', function(event, d) {
    // Example: no tooltip for records missing the fields the tooltip shows.
    if (!d.marketCap || d.sector === 'ETF') {
        return;
    }
    showTooltip(event, d);
})
```

### Click selection and highlighting

Prefer **idempotent selection** (click always sets selection; it does not toggle), unless the task explicitly asks for click-to-deselect behavior. Verifiers often click a bubble, then click the matching row, and expect both to remain highlighted.

```javascript
let selectedKey = null;
svg.selectAll('.bubble')
    .on('click', function(event, d) {
        selectedKey = d.ticker;
        applySelection(selectedKey);
    });

function applySelection(key) {
    d3.selectAll('.bubble').classed('selected', d => d.ticker === key);
    d3.selectAll('#data-table tbody tr').classed('selected', d => d && d.ticker === key);
}
```

CSS for highlighting:
```css
.bubble.selected { stroke: #000; stroke-width: 3px; }
tr.selected { background: #fff7d6; }
```

Use **one** selected class name across chart and table (e.g. `.selected`) so the two sides stay in sync. Do not mix `.selected` on one panel with `.highlighted` on the other.

---

## Multi-panel dashboards (chart + table, side-by-side)

Many tasks ask for "A chart on the left and a data table on the right." Use plain CSS flex on a shared wrapper:

```html
<main class="dashboard">
  <section class="chart-panel"><div id="chart"></div></section>
  <section class="table-panel"><table id="data-table">…</table></section>
</main>
```
```css
.dashboard { display: flex; gap: 24px; align-items: flex-start; }
.chart-panel { flex: 0 0 auto; }
.table-panel { flex: 1 1 auto; }
```

### Linked selection between chart and table

Keep a single source of truth (`selectedKey`) and two renderers. Each panel exposes `highlight(key)` and `onSelect(cb)`; one top-level `select()` function calls `highlight` on both and is itself the callback registered with each panel's `onSelect`. Do **not** keep separate selection states per panel.

### Table rendering

When the task lists specific column headers ("Ticker symbol", "Full company name", "Sector", "Market cap"), use **those exact strings** in `<th>` elements. Preserve input row order unless the task specifies a sort. For numeric columns with large values, format with suffix style (e.g. `1.64T`, `358.11B`, `12.80M`); fall back to a visible placeholder (e.g. `—`, `-`, or blank) for missing/zero values.

```javascript
function formatMarketCap(v) {
    if (v == null || isNaN(v) || v === 0) return '—';
    const abs = Math.abs(v);
    if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T';
    if (abs >= 1e9)  return (v / 1e9).toFixed(2)  + 'B';
    if (abs >= 1e6)  return (v / 1e6).toFixed(2)  + 'M';
    if (abs >= 1e3) return (v / 1e3).toFixed(2) + 'K';
    return String(v);
}
```

---

## Bubble chart with sector clusters

When the task asks for a bubble chart clustered by a categorical field (e.g. sector) with force simulation:

1. **Radius scale**: use `d3.scaleSqrt()` on the numeric field so the **area** encodes the value (not the radius directly).
2. **Missing values**: items with no numeric field get a fixed uniform radius (document the value in a comment).
3. **Color scale**: categorical (`d3.scaleOrdinal` with an explicit palette per category so colors are stable).
4. **Clusters close to center**: place each category's attractor on a small circle around the chart center (radius ~20–25% of the shorter side), not on the chart's edges. The prompt phrasing "clusters … close together and centered reasonably" means short attractor radius and moderate `forceX`/`forceY` strength (~0.1–0.2).
5. **Collision**: `d3.forceCollide(d => d.r + 1)` with 2–3 iterations.
6. **In-mark labels**: append a `<text>` inside each node `<g>` with the ticker/short-name; font size can scale with radius; `pointer-events: none` on labels so they don't steal hover events.
7. **Legend**: render one swatch per category with the category name (either as an HTML flex row below/beside the SVG, or as an SVG `<g class="legend">` inside the chart). When a prompt says "Add legends to show the sector name of each color", just ensure every used category appears with its colored swatch and name — placement is flexible.
8. **Tooltip**: conditional (see above). For excluded records (e.g. ETFs), return early.

See `scripts/bubble_chart_example.js` for a reference implementation.

---

## Testing locally (optional but encouraged)

- Serve the output over HTTP, not `file://`, because `d3.csv` uses `fetch` and browsers block it on `file://`:
  ```
  cd /path/to/output && python3 -m http.server 8000
  ```
- For a headless DOM check on Node 18 with jsdom, D3 v6+ needs a `fetch` polyfill because `window.fetch` is missing in jsdom; add `dom.window.fetch = (url, opts) => fetch(new URL(url, serverOrigin).toString(), opts);` after creating the JSDOM instance.
- A verifier that opens the page in a real browser will have native `fetch` and will **not** need the polyfill — don't carry workaround code into the deliverables.

---

## Resources in this skill

- `scripts/bubble_chart_example.js` — reference force-clustered bubble chart with sector colors, in-bubble ticker labels, legend hook, and linked selection.
- `scripts/interactive_table_example.js` — reference data table with linked row highlighting and a number formatter that returns a placeholder for missing values.
- `scripts/tooltip_handler.js` — reusable tooltip class with conditional display.
- `scripts/check_tooltip.js` — small helper to sanity-check a tooltip implementation in the browser console.

Use them as **patterns to adapt**, not as drop-in modules. Rename fields and sector names to match the current task's data.
