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

### Delivery and self-check discipline (static web deliverables)

When the contract is *“produce files at path X so a grader/browser can open them”*, the deliverable is a **static artifact**, not a running service. Once the required files exist:

- Prefer **file-level checks only**, in this order, and stop at the first sufficient level:
  1. **Existence & layout**: every required path is present with non-zero size.
  2. **Static parse**: HTML is well-formed; JS parses (e.g., `node --check visualization.js`); CSS parses. No execution required.
  3. **Optional headless render**: only if truly necessary to catch a runtime bug you cannot reason about statically.
- Do **not** launch long-lived helper services (HTTP server, websocket, headless browser bridge) in the same sandbox as the grader unless you can satisfy the *Self-verification hygiene* rules below. A grader may bind its own fixtures to fixed ports/paths; a leaked listener will cascade every downstream test into an error even though your artifact is correct.
- Treat the phrase *“I should be able to open it in a browser”* as a **statement about the artifact**, not an instruction to simulate a browser session inside the delivery sandbox.

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

### Self-verification hygiene (sandbox-shared resources)

If — after the file-level checks above — you still choose to run an auxiliary process to smoke-test the artifact (HTTP server, jsdom bridge, headless browser), treat that process as **shared sandbox state that the grader may also touch**. Follow all of the following, or skip the probe entirely:

1. **Never bind fixed ports.** Bind to port `0` (OS-assigned ephemeral port) and read the actual port back before use, e.g.:
   - Python: `httpd = HTTPServer(("127.0.0.1", 0), Handler); port = httpd.server_address[1]`.
   - Node: `server.listen(0, () => port = server.address().port)`.
   - Shell: prefer `python3 -m http.server 0` and parse the printed port, or use a helper that reports the bound port.
2. **Track by PID, not by pattern.** Capture the child PID at launch (`$!` in shell, `child.pid` in Node, `.pid` on `Popen`). Do not rely on `pkill -f <pattern>` as the sole teardown — pattern matches are fragile and often miss.
3. **Unconditional teardown before finishing.** Wrap the probe in `try/finally` (or a shell `trap`) that always runs `kill <PID>` (then `kill -9 <PID>` if still alive) *before* you emit the completion message — even on error, timeout, or early return.
4. **Verify release.** After teardown, assert the port is free (e.g., `ss -ltn | grep -q ":<port> " && echo LEAKED`) and that no child process remains. If either check fails, do not declare success.
5. **Prefer in-process alternatives.** When feasible, avoid a listener altogether: load the HTML with jsdom’s file `ResourceLoader`, read/eval the JS directly, or run `node --check` for a pure syntax pass. These leave no socket state behind.
6. **Do not install heavyweight probe dependencies in the delivery sandbox** unless the task requires them; each install increases the surface for collisions with the grader’s own environment.

Rationale: graders commonly reuse fixed ports or filesystem locations in the same sandbox. A leaked listener on a well-known port (e.g., `8000`, `8080`, `8765`) causes the grader’s fixture setup to fail with `Address already in use`, turning every downstream test into an ERROR even when the delivered artifact is fully correct.

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
