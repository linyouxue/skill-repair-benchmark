---
name: d3-visualization
description: Build offline, deterministic D3.js **v6** web-app visualizations (HTML+CSS+JS)
  from local datasets, including force-layout bubble charts, tooltips, legends, and
  **two-way linked** chart↔table selection (with label overlays that don’t break clicking).
---

## Steps
1. **Lock requirements + acceptance checks up front (write them into code comments and re-check at the end)**
   - Confirm required **D3 version (v6)**, required output paths, and required data sources (main CSV + `indiv-stock/` folder).
   - Create an acceptance checklist that explicitly includes:
     - Required artifacts exist **on disk** and are referenced locally: `index.html`, `css/style.css`, `js/d3.v6.min.js`, `js/visualization.js`, and `data/` copies.
     - Bubble **click works even when clicking the ticker text label** (labels must not steal pointer events; click handler must be on the node container/circle).
     - Tooltip shows **ticker + name + sector**, and is **suppressed for ETFs** (ETF rows have missing `marketCap/country/website`; show nothing for them).
     - **Two-way linking**: click bubble highlights table row, click row highlights bubble using **one shared selection state** (use the same `.selected` class on both).

2. **Inspect data using only built-in tools (do not assume pandas is installed)**
   - Use Python’s built-in `csv` module (or `head`, `wc`, `ls`) to confirm:
     - `stock-descriptions.csv` columns + row count (**expect 50 rows for this dataset**) and which fields are missing for ETFs.
     - Sector domain (**expect 5 sectors including `ETF`**) and deterministic ordering (e.g., sort sectors alphabetically for stable colors/legend).
     - ETF rows (**expect ~10**; spot-check tickers like `SPY`, `VOO`, `QQQ`, `GLD`).
     - `indiv-stock/` naming convention (`TICKER.csv`) and file count (**expect 50 files**) and one sample file’s columns (e.g., `Date`, `Open/High/Low/Close`, `Volume`, `Adjusted Close`).
   - Identify ETFs deterministically (e.g., missing `marketCap/country/website`, not just a label) so tooltip suppression and sizing are correct.

3. **Create the `/root/output/` tree and required files early, and prove it with terminal output**
   - Execute filesystem-writing steps via the terminal tool (don’t just paste commands), and immediately follow them with checks that show up in the trace:
     - Create required directories: `/root/output/js`, `/root/output/css`, `/root/output/data`, then `ls -ld` them.
     - Copy input data into `/root/output/data/` (including the full `indiv-stock/` directory), then verify with:
       - `test -f /root/output/data/stock-descriptions.csv`
       - `test -d /root/output/data/indiv-stock`
       - `ls /root/output/data/indiv-stock | wc -l` (should be 50)
     - Vendor **D3 v6** to `/root/output/js/d3.v6.min.js` (local copy, not CDN at runtime). Prefer copying from an installed `d3` package if available (e.g., `node -p "require.resolve('d3/dist/d3.min.js')"`) otherwise download it; then verify:
       - `test -s /root/output/js/d3.v6.min.js` and `wc -c` shows a non-trivial size
       - The file corresponds to v6 (e.g., search for a `v6.` marker if present, or verify `d3.version` in-browser during manual check).
     - Create the three app files **right away** (even minimal placeholders first): `/root/output/index.html`, `/root/output/js/visualization.js`, `/root/output/css/style.css`, then verify they exist and are non-empty with `test -s` and `ls -l`.
   - When writing files:
     - Use quoted heredocs: `cat > file <<'EOF' ... EOF` (prevents JS template strings/backticks from breaking the shell).

4. **Create an HTML skeleton that supports the required layout and interactivity**
   - Use a two-column layout (flex/grid) for “bubble chart” (left) and “table” (right).
   - Include:
     - A chart container (SVG or a div into which the SVG is appended).
     - A legend container.
     - A table container.
     - A tooltip `<div id="tooltip" class="tooltip"></div>` (CSS toggles `.visible`).
   - Reference only local assets (no CDN): `css/style.css`, then `js/d3.v6.min.js`, then `js/visualization.js` (use `defer` on the app script if needed).

5. **Load/prepare data deterministically and offline-friendly**
   - Prefer approaches that work when opened locally:
     - If `file://` loading is a concern, embed the CSV content at build time and parse via `d3.csvParse(...)`.
     - If you rely on runtime loading, use relative paths under the output tree (e.g., `data/stock-descriptions.csv`).
   - Normalize fields:
     - `marketCap`: number or `null`
     - `isETF`: derived from missing `marketCap/country/website` (drives uniform sizing + tooltip suppression).
   - Keep ordering stable (e.g., sort by sector then ticker) before binding to marks.

6. **Bubble chart: force clusters by sector, no overlaps, centered clusters, clickable even with labels**
   - Scales:
     - Radius: `d3.scaleSqrt` on `marketCap` (ETFs get a uniform radius).
     - Color: `d3.scaleOrdinal` with **sorted sector domain** and a fixed scheme.
   - Force simulation:
     - Use `forceCenter(width/2, height/2)`.
     - Compute sector target positions **near the center** (compact circle/grid), then cluster via `forceX/forceY` so sector groups don’t drift far away.
     - Use `forceCollide(d => d.r + padding)` to prevent overlaps.
     - For determinism: set initial `(x,y)` deterministically; run a fixed number of ticks and stop if you don’t need animation.
   - Rendering pattern that guarantees “clicking text still clicks bubble”:
     - Create one `<g class="node">` per stock; append `<circle>` then `<text>` inside it; on each tick, move the **group** via `transform: translate(x,y)` so circle+label stay aligned.
     - Attach hover/click handlers to the **`g.node` (or the circle)**, never to the text.
     - Ensure the label never captures clicks: `text.attr('pointer-events', 'none')` (or CSS `.node text{pointer-events:none}`).
   - Legend:
     - Build legend entries from `colorScale.domain()` so every sector appears exactly once with its color swatch + name.
   - Tooltip:
     - Tooltip element must be `pointer-events: none`.
     - On hover, if `isETF` then hide/keep hidden and do not show anything; otherwise show ticker + full name + sector.

7. **(If required by the task) visibly use `indiv-stock/` data**
   - On hover or selection (non-ETF only), optionally render a lightweight mini line chart / sparkline for that ticker using `data/indiv-stock/TICKER.csv` (embed or lazy-load + cache).
   - Keep it small and robust: if a file is missing/unparseable, fail gracefully without breaking the page.

8. **Data table + formatting + true two-way linking**
   - Render all 50 rows with required columns: **Ticker symbol**, **Full company name**, **Sector**, **Market cap** (formatted `T/B/M/K`; ETFs should display `-` or similar).
   - Implement **one shared selection function** used by both chart and table:
     - `setSelected(ticker)` stores a single `selectedTicker` and updates:
       - bubble node class (e.g., `g.node.selected`)
       - table row class (e.g., `tr.selected`)
     - Call `setSelected(d.ticker)` from both bubble click and row click (do not maintain separate “highlight” vs “selected” pathways).

9. **Verification (must be executed before considering the build “done”)**
   - Filesystem (show results in terminal):
     - `find /root/output -maxdepth 3 -type f` includes `index.html`, `js/d3.v6.min.js`, `js/visualization.js`, `css/style.css`, plus `data/stock-descriptions.csv`.
     - `find /root/output/data/indiv-stock -maxdepth 1 -type f | wc -l` is 50.
   - JS sanity:
     - Run `node --check` on generated JS files.
   - Interaction checks (manual or scripted):
     - 50 bubbles + 50 table rows render; legend includes every sector.
     - Clicking the **bubble OR its ticker label** selects it (label does not block clicks).
     - Bubble click highlights the matching table row; table row click highlights the matching bubble (single shared selection state).
     - Tooltip appears only for non-ETFs; ETFs show no tooltip.
     - Sector clusters are compact/centered; collisions prevent overlap.

## Expected Result
A reproducible, offline-capable D3 **v6** single-page app with the required `/root/output/` file tree populated, where the bubble chart (non-overlapping sector clusters, labels, legends, conditional tooltips) and the 50-row data table are **bidirectionally linked**, and the text labels do not block bubble clicking.
