---
name: d3-visualization
description: Build deterministic, verifiable data visualizations with D3.js. Generate standalone HTML/SVG (and optional PNG) from local data files without external network dependencies. Use when tasks require charts, plots, axes/scales, legends, tooltips, or data-driven SVG output.
---

# D3.js Visualization Skill

Use this skill to turn structured data (CSV/TSV/JSON) into **clean, reproducible** visualizations using **D3.js**. The goal is to produce **stable outputs** that can be verified by diffing files, hashing, or by an automated browser-based test harness (e.g., Playwright/jsdom).

## When to use

Activate this skill when the user asks for any of the following:

- "Make a chart/plot/graph/visualization"
- bar/line/scatter/bubble/area/histogram/box/violin/heatmap
- timelines, small multiples, faceting
- axis ticks, scales, legends, tooltips
- data-driven SVG output for a report or web page
- converting data to a static SVG or HTML visualization
- interactive dashboards linking multiple views (e.g., chart + table, click-to-highlight)

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
  - any labeling requirements (title, axis labels, units)
- Output constraints:
  - "static only", "no animation", "must be deterministic", "offline", exact output paths, exact D3 major version, etc.

If details are missing, **make reasonable defaults** and document them in comments near the top of the output file.

### Honor task-specified paths and versions

When the task specifies **any** of the following, they override the defaults in this skill:

- Output directory / file names (e.g., `/root/output/index.html`, `output/js/visualization.js`).
- D3 **major version** (e.g., v6 vs v7). Download the matching minified bundle to the exact filename the task requests (e.g., `js/d3.v6.min.js`). Do **not** substitute a different major version.
- Data-copy requirements ("copy input data into `output/data/`"). Copy the files exactly, preserving subdirectory structure and file names (including case) so relative paths in the HTML resolve.

A quick self-check before you finish:

- [ ] Every path listed in the task exists on disk.
- [ ] The D3 file is the requested major version (grep the file for `d3.js v6` or `d3.js v7`).
- [ ] Data files referenced by your JS exist under the copied `data/` tree with matching case.

---

## Outputs you should produce

When the task does not specify paths, prefer producing **all of** the following:

1. `dist/chart.html` — standalone HTML that renders the visualization
2. `dist/chart.svg` — exported SVG (stable and diff-friendly)
3. (Optional) `dist/chart.png` — if the task explicitly needs a raster image

When the task **does** specify paths (common for web-app tasks), follow them exactly. A typical layout requested by tasks:

```
output/
  index.html
  js/
    d3.v6.min.js         # pinned D3, exact filename from task
    visualization.js     # your code
  css/
    style.css
  data/                  # copies of input data, same structure as source
```

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
  - fix the tick count (e.g., run 300 warm-up ticks with `simulation.tick()` then let it continue for user interaction),
  - fix initial positions deterministically (e.g., sorted nodes placed on a grid or on per-cluster centers),
  - use deterministic cluster/attractor centers (e.g., points on a circle around the chart center),
  - always add `forceCollide` when circles must not overlap.

### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- Pin D3 to the **major version the task requests** (default when unspecified: **d3@7.9.0**). Common task requests: `d3.v6.min.js`, `d3.v7.min.js`.
- Vendor the minified D3 bundle at the exact path the task asks for (e.g., `js/d3.v6.min.js`, `vendor/d3.v7.9.0.min.js`).

### File determinism
- Stable SVG output:
  - Avoid auto-generated IDs that may change.
  - If you must use IDs (clipPath, gradients), derive them from stable strings (e.g., `"clip-plot"`).
- Use LF line endings.
- Keep numeric precision consistent (e.g., round to 2–4 decimals if needed).

---

## Serving the page & process hygiene (READ BEFORE FINISHING)

D3 loaders like `d3.csv`, `d3.json`, `d3.tsv` use `fetch`, which browsers block on the `file://` scheme (CORS). Automated verifiers therefore usually spin up a **static HTTP server on a fixed port** (e.g., 8000, 8080, 8765) and drive a headless browser (Playwright/jsdom) against it.

That has two consequences for you:

### 1. Design for HTTP serving, not file://

- Use **relative** URLs in your HTML/JS (`js/d3.v6.min.js`, `data/stock-descriptions.csv`), never absolute filesystem paths.
- Do not hard-code `http://localhost:PORT`.
- Preserve the case of data file names exactly as they appear on disk (case-sensitive on Linux).

### 2. Do NOT leave background servers or browsers running

If you start a local HTTP server, jsdom instance, Playwright browser, or any long-lived process to self-verify your work, you **must fully tear it down before you finish**. A verifier that tries to `bind()` the same port will fail all browser-based tests with `OSError: [Errno 98] Address already in use`.

Safe pattern:

```bash
# start
python3 -m http.server 8000 --bind 127.0.0.1 > /tmp/httpd.log 2>&1 &
SERVER_PID=$!

# ... run your check ...

# stop — always run this before you finish, even on failure
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
# belt-and-suspenders: kill any stragglers on that port
fuser -k 8000/tcp 2>/dev/null || true
```

Before your final message, run a check equivalent to:

```bash
ss -ltn 2>/dev/null | awk '{print $4}' | grep -E ':(8000|8080|8765|3000|5000)$' && echo "PORT STILL BOUND — kill it" || echo "ports clear"
pgrep -af 'http.server|node .*jsdom|playwright|chromium' || echo "no stray processes"
```

If anything is still bound, kill it. **Leaving a server bound to a common port is one of the most frequent causes of a 0.0 reward on browser-based verifiers even when the artifacts themselves are correct.**

### 3. Prefer non-networked self-checks when possible

If you just want to sanity-check the JS, you can often skip the server entirely:

- Parse the CSV in Node and re-run the transformation logic directly.
- Or use jsdom with `runScripts: 'dangerously'` and inject the CSV text via `d3.csvParse` instead of `d3.csv` (no fetch needed).

This avoids opening any port at all.

---

## Recommended project layout (when task does not specify)

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

When the task requires interactivity (e.g., tooltips on hover, click to highlight, linked views):

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
- Use `opacity: 0` by default (not `display: none`) for smooth transitions.
- Use `.classed('visible', true/false)` to toggle visibility.
- `pointer-events: none` prevents tooltip from blocking mouse events.
- Position tooltip relative to mouse with `event.pageX/pageY`.

### Click handlers for selection/highlighting

```javascript
svg.selectAll('.bar')
    .on('click', function(event, d) {
        d3.selectAll('.bar').classed('selected', false);
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

### Linked views (chart ↔ table)

When the task asks that clicking a mark highlights a row and vice versa, use a single **selection state** shared by both renderers:

```javascript
let selectedKey = null;
function select(key) {
    selectedKey = (key === selectedKey) ? null : key;
    updateChartHighlight(selectedKey);
    updateTableHighlight(selectedKey);
}
// both bubble click and row click call select(d.ticker)
```

Expose a stable class name (e.g., `.selected`) on both the SVG element and the `<tr>` so the verifier can detect the linkage.

### Conditional interactivity

Some marks should not be interactive (e.g., ETFs in a stock task have no tooltip data):
```javascript
.on('mouseover', function(event, d) {
    if (d.sector === 'ETF' || d.marketCap == null) return;  // no tooltip
    showTooltip(event, d);
});
```
Read the task carefully for these "do not show for X" carve-outs and implement the early return explicitly.

---

## Pre-finish checklist

Before returning to the user, verify each item:

- [ ] All files listed in the task exist at the exact paths.
- [ ] D3 file is the requested major version.
- [ ] HTML uses **relative** paths; opening via a static HTTP server works.
- [ ] Data files copied with original names and directory structure.
- [ ] Required interactions implemented (tooltips, click-linking, legend, etc.).
- [ ] Conditional carve-outs (e.g., no tooltip for ETFs) implemented as early returns.
- [ ] **No background HTTP server, jsdom, Playwright, or headless browser is still running.** Common ports (8000/8080/8765/3000/5000) are free.
- [ ] No stray processes: `pgrep -af 'http.server|playwright|chromium|node'` shows nothing you started.
