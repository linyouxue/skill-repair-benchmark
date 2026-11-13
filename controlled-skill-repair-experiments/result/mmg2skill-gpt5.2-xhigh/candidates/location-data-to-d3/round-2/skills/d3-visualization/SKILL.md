---
name: d3-visualization
description: Build offline, deterministic D3.js **v6** web-app visualizations (HTML+CSS+JS)
  from local datasets, including force-layout bubble charts, tooltips, legends, and
  **two-way linked** chart↔table selection (with label overlays that don’t break clicking).
---

## Steps
1. **Lock requirements + acceptance checks up front (write them into code comments)**
   - Confirm required **D3 version (v6)**, required output paths, and required data sources (main CSV + `indiv-stock/` folder).
   - Create an acceptance checklist that explicitly includes:
     - Required artifacts exist and are referenced locally: `index.html`, `css/style.css`, `js/d3.v6.min.js`, `js/visualization.js`, and `data/` copies.
     - Bubble **click works even when clicking the ticker text label** (text overlay must not steal pointer events).
     - Tooltip shows **ticker + name + sector**, and is **suppressed for ETFs** (ETF rows have missing `marketCap/country/website`; show nothing for them).
     - **Two-way linking**: click bubble highlights table row, click row highlights bubble (single shared selection state).

2. **Inspect data using only built-in tools (do not assume pandas is installed)**
   - Use Python’s built-in `csv` module (or `head`, `wc`, `ls`) to confirm:
     - `stock-descriptions.csv` columns + row count (expect ~50) and which fields are missing for ETFs.
     - Sector domain (unique sector names) and deterministic ordering (e.g., sort sectors alphabetically for stable colors/legend).
     - `indiv-stock/` naming convention (`TICKER.csv`) and one sample file’s columns (e.g., `Date`, `Open/High/Low/Close`, `Volume`).
   - Identify ETFs deterministically (e.g., missing `marketCap/country/website`, not just a label) so tooltip suppression and sizing are correct.

3. **Create the `/root/output/` tree and required files early (scaffold first, then iterate)**
   - Immediately create required directories: `/root/output/js`, `/root/output/css`, `/root/output/data`.
   - Copy input data into `/root/output/data/` (including the full `indiv-stock/` directory).
   - Vendor **D3 v6** to `/root/output/js/d3.v6.min.js` (local copy, not CDN at runtime) and verify it’s v6 (e.g., `d3.version` starts with `6.`).
   - Create the three app files **right away** (even as minimal placeholders first): `/root/output/index.html`, `/root/output/js/visualization.js`, `/root/output/css/style.css`.
   - When executing shell actions:
     - Run **one command per tool call**, or chain with `&&` in a single call.
     - Write files with quoted heredocs: `cat > file <<'EOF' ... EOF` (prevents JS template strings/backticks from breaking the shell).

4. **Create an HTML skeleton that supports the required layout and interactivity**
   - Use a two-column layout (flex/grid) for “bubble chart” (left) and “table” (right).
   - Include:
     - A chart container (SVG or a div into which the SVG is appended).
     - A legend container.
     - A table container.
     - A tooltip `<div id="tooltip" class="tooltip"></div>` (CSS toggles `.visible`).

5. **Load/prepare data deterministically and offline-friendly**
   - Prefer approaches that work when opened locally:
     - If `file://` loading is a concern, embed the CSV content at build time and parse via `d3.csvParse(...)`.
     - If you rely on runtime loading, use relative paths under the output tree (e.g., `data/stock-descriptions.csv`).
   - Normalize fields:
     - `marketCap`: number or `null`
     - ETF flag from missing fields (`marketCap/country/website`) to drive uniform sizing + tooltip suppression.
   - Keep ordering stable (e.g., sort by sector then ticker) before binding to marks.

6. **Bubble chart: force clusters by sector, no overlaps, centered clusters, clickable even with labels**
   - Scales:
     - Radius: `d3.scaleSqrt` on `marketCap` (ETFs get a uniform radius).
     - Color: `d3.scaleOrdinal` with **sorted sector domain** and a fixed scheme.
   - Force simulation:
     - Use `forceCenter(width/2, height/2)`.
     - Compute sector target positions **near the center** (small circle or compact grid), then cluster via `forceX/forceY`.
     - Use `forceCollide(d => d.r + padding)` to prevent overlaps.
     - For determinism: set initial `(x,y)` deterministically; run a fixed number of ticks and stop if you don’t need animation.
   - Rendering pattern that guarantees “clicking text still clicks bubble”:
     - Create one `<g class="node">` per stock; append `<circle>` and `<text>` inside it.
     - Attach hover/click handlers to the **parent `g.node`** (or the circle), never to the text.
     - Set label not to capture pointer events: `text.attr('pointer-events', 'none')` (or CSS `.node text{pointer-events:none}`).
   - Tooltip:
     - Use `.visible` class toggle; tooltip itself should be `pointer-events: none`.
     - On hover, **return early for ETFs** so no tooltip appears at all.

7. **(If required by the task) visibly use `indiv-stock/` data**
   - On hover or selection (non-ETF only), render a lightweight mini line chart / sparkline for that ticker using its `indiv-stock/TICKER.csv` data (embed or lazy-load + cache).
   - Keep it small and robust: if a file is missing/unparseable, fail gracefully without breaking the page.

8. **Data table + formatting + true two-way linking**
   - Render all rows with required columns: ticker, full name, sector, formatted market cap.
   - Market cap formatting: consistent `T/B/M/K` formatter (not locale-only).
   - Implement **one shared selection function** used by both chart and table:
     - `setSelected(ticker)` updates:
       - bubble/node class (e.g., `.selected`)
       - table row class (e.g., `.selected`)
     - Call it from bubble click and row click (avoid separate “highlight” vs “selected” pathways).

9. **Verification (must be executed before considering the build “done”)**
   - Filesystem: confirm `/root/output/` contains `index.html`, `js/d3.v6.min.js`, `js/visualization.js`, `css/style.css`, and `data/stock-descriptions.csv` + `data/indiv-stock/`.
   - JS sanity: run `node --check` on generated JS files.
   - Browser interaction checks:
     - 50 bubbles + 50 table rows render; legend includes every sector.
     - Clicking the **bubble OR its ticker label** selects it.
     - Bubble click highlights the matching table row; table row click highlights the matching bubble (same selection state).
     - Tooltip appears only for non-ETFs; ETFs show no tooltip.
     - Sector clusters are compact/centered; collisions prevent overlap.

## Expected Result
A reproducible, offline-capable D3 **v6** single-page app with the required `/root/output/` file tree populated, where the bubble chart (non-overlapping sector clusters, labels, legends, conditional tooltips) and the 50-row data table are **bidirectionally linked**, and the text labels do not block bubble clicking.
