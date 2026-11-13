---
name: d3-visualization
description: Build offline, deterministic D3.js **v6** web-app visualizations (HTML+CSS+JS)
  from local datasets, including force-layout bubble charts, tooltips, legends, and
  **two-way linked** chart↔table selection (with label overlays that don’t break clicking).
---

## Steps
1. **Lock requirements + acceptance checks up front (write them into code comments)**
   - Confirm required **D3 version (v6)**, required output paths, and all required data sources (e.g., a main CSV plus a per-entity folder like `indiv-stock/`).
   - Create an acceptance checklist that explicitly includes:
     - Bubble **click works even when clicking the ticker text label** (text overlay must not steal pointer events).
     - Tooltip shows **ticker + name + sector**, and is **suppressed for ETFs** (missing fields).
     - **Two-way linking**: click bubble highlights table row, click row highlights bubble (single shared selection state).
     - If the task mentions a time-series folder (e.g., `data/indiv-stock/`), **the app must render some price-history visualization** from it (lazy-loaded sparkline/mini line chart is sufficient).

2. **Inspect data using only built-in tools (do not assume pandas is installed)**
   - Use Python’s built-in `csv` module (or `head`, `wc`, `ls`) to confirm:
     - Column names, row count, missing values (e.g., missing `marketCap` for ETFs).
     - Categorical domains (e.g., sector list) and how ETFs are identified (sector label and/or missing fields).
     - `indiv-stock/` file naming convention (e.g., `AAPL.csv`), and which columns exist in price history files (e.g., date + close).
   - Sort/define domains deterministically (e.g., sectors sorted alphabetically) to keep coloring/legends stable.

3. **Generate the required on-disk web-app structure safely (avoid tool command + quoting pitfalls)**
   - Create folders and copy data exactly to the required paths (e.g., `output/css`, `output/js`, `output/data/`).
   - Vendor **D3 v6** locally (no CDN at runtime) to the required path (e.g., `js/d3.v6.min.js`).
   - When executing shell actions:
     - Run **one command per tool call**, or chain with `&&` in a single call (the runner rejects “multiple commands at once”).
     - Write files with safe heredocs: `cat > file <<'EOF' ... EOF` (quoted `EOF` prevents JS backticks/templates from breaking the shell). Prefer separate file-write steps over one giant script.

4. **Create an HTML skeleton that supports the required layout and interactivity**
   - Use a two-column layout (flex/grid) for “bubble chart” (left) and “table” (right).
   - Include:
     - A chart container (SVG or a div into which the SVG is appended).
     - A table container.
     - A tooltip `<div id="tooltip" class="tooltip"></div>` (CSS toggles `.visible`).
     - A small “details” region for price history (can be inside the tooltip or a dedicated panel) so `indiv-stock/` data is visibly charted.

5. **Load/prepare data deterministically and offline-friendly**
   - If the app must be openable without a local server, **avoid runtime `fetch()`/`d3.csv()` from `file://`**:
     - Parse CSV(s) at build time (Python `csv` is fine) and **embed**:
       - `const STOCKS = [...]` from `stock-descriptions.csv`
       - `const PRICE = {TICKER: [{date, close}, ...], ...}` from `indiv-stock/` (or lazy-load if you know the evaluator serves via HTTP).
   - Normalize fields:
     - `marketCap`: number or `null`
     - Identify ETF entries via missing `marketCap/country/website` and/or sector label
   - Keep ordering stable (e.g., sort by sector, then ticker) before binding to marks.

6. **Bubble chart: force clusters by sector, no overlaps, centered clusters, clickable even with labels**
   - Scales:
     - Radius: `d3.scaleSqrt` on `marketCap` (ETFs get a uniform radius).
     - Color: `d3.scaleOrdinal` with **sorted sector domain** and a fixed scheme.
   - Force simulation:
     - Use `forceCenter(width/2, height/2)`.
     - Compute sector target positions **near the center** (small circle or grid), then use `forceX/forceY` to cluster by sector.
     - Use `forceCollide(d => d.r + padding)` to prevent overlaps.
     - For determinism: set initial `(x,y)` deterministically; run a fixed number of ticks and stop (or set a deterministic random source if you use ongoing simulation).
   - Rendering pattern to avoid “text overlay blocks clicks”:
     - Create one `<g class="node">` per stock; append `<circle>` and `<text>` inside it.
     - Attach hover/click handlers to the **`g` or `circle`**.
     - Set the label to not capture pointer events:
       - `text.attr('pointer-events', 'none')`
     - This guarantees clicking the ticker label still triggers the bubble selection.
   - Tooltip:
     - Use the `.visible` class toggle pattern.
     - Only show for non-ETFs (those with complete fields); ETFs: return early and do nothing.

7. **Price-history visualization from `indiv-stock/` (must be visibly used)**
   - On hover or selection (non-ETF only), render a mini line chart (sparkline) using that ticker’s time series:
     - If embedding: pull from `PRICE[ticker]`.
     - If lazy-loading: `d3.csv('data/indiv-stock/' + ticker + '.csv')` and cache results.
   - Keep it lightweight (small SVG, no transitions) and fail gracefully if the file is missing.

8. **Data table + formatting + true two-way linking**
   - Render all rows with required columns: ticker, full name, sector, formatted market cap.
   - Market cap formatting: use a consistent formatter (e.g., custom `T/B/M/K` logic rather than locale).
   - Implement **one shared selection function** used by both chart and table:
     - `setSelected(ticker)` updates:
       - bubble/node class (e.g., `.selected`)
       - table row class (e.g., `.selected`)
     - Call it from bubble click and row click (do not maintain separate “highlight” vs “selected” paths that drift).
   - Optional: scroll the selected row into view to make the linkage obvious.

9. **Verification (treat as required “done” criteria)**
   - Static checks:
     - Confirm required files exist in the specified paths.
     - Run `node --check` on the generated JS to catch syntax errors early.
   - Interaction checks in a browser:
     - Clicking **the bubble OR its ticker text** selects it.
     - Bubble click highlights the matching table row; table row click highlights the matching bubble.
     - Tooltip appears only for non-ETFs and does not interfere with hover (tooltip has `pointer-events: none`).
     - Sector clusters are centered/compact; collisions prevent overlap.
     - Selecting/hovering a non-ETF shows a visible mini price-history chart sourced from `indiv-stock/`.

## Expected Result
A reproducible, offline-capable D3 **v6** single-page app whose bubble chart (with non-overlapping sector clusters, labels, legends, and conditional tooltips) and data table are **bidirectionally linked**, where label overlays do not break clicking, and where the per-stock `indiv-stock/` time-series data is **actually visualized** (e.g., via a sparkline/mini line chart on selection/hover).
