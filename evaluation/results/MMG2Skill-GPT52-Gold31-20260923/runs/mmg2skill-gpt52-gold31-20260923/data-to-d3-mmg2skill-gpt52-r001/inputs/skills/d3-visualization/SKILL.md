---
name: d3-visualization
description: Build deterministic, offline D3.js **v6** visualizations from local CSV
  data, writing a browser-openable single-page app with vendored dependencies, stable
  force layouts, tooltips, legends, linked selections, and (when present) a small
  linked price-history view.
---

## Steps
1. **Inspect input data using only built-in tools (no pandas).**
   - Use `head`, `ls`, and/or Python stdlib `csv` to confirm columns, sector categories, which rows have missing `marketCap` (often ETFs), and the filename pattern in `indiv-stock/` for mapping ticker → price CSV.
2. **Create the required output tree and copy data exactly into it.**
   - Create `/root/output/{js,css,data}` and copy:
     - `/root/data/stock-descriptions.csv` → `/root/output/data/stock-descriptions.csv`
     - `/root/data/indiv-stock/` → `/root/output/data/indiv-stock/`
3. **Vendor D3.js v6 locally (no CDN).**
   - Place the minified bundle at: `/root/output/js/d3.v6.min.js` (pin to a v6 release, e.g. 6.7.0).
4. **Author `/root/output/index.html` as a single-page app that loads only local files.**
   - Include:
     - `<link rel="stylesheet" href="css/style.css">`
     - `<script src="js/d3.v6.min.js"></script>`
     - `<script defer src="js/visualization.js"></script>`
   - Layout scaffolding:
     - Left: bubble chart SVG + legend container + tooltip element.
     - Right: table container.
     - Add a small “details” area (inside either panel) reserved for a **sparkline/mini line chart** of the selected ticker’s price history so `indiv-stock/` is actually visualized without changing the “two main charts side-by-side” requirement.
5. **Implement `/root/output/js/visualization.js` using deterministic D3 v6 patterns.**
   - **Load metadata** from `data/stock-descriptions.csv` via `d3.csv(...)`, parsing:
     - `marketCap` as number when present; mark ETFs (or missing market cap) for uniform sizing and for conditional tooltip behavior.
   - **Bubble chart:**
     - Radius: `d3.scaleSqrt` on `marketCap`; for ETFs/missing market cap use a fixed radius.
     - Color: `d3.scaleOrdinal` by sector; render a legend mapping color → sector name.
     - Force clustering by sector using `forceX`/`forceY` toward **sector centers arranged near the overall center** (e.g., a small grid/ring around center so clusters are close together).
     - Add `forceCollide(r + padding)` to prevent overlap.
     - **Determinism:** sort nodes by ticker before binding; set deterministic initial positions (e.g., grid based on sorted index); run the simulation for a **fixed** number of ticks (e.g., `for (let i=0;i<N;i++) sim.tick(); sim.stop();`) before rendering positions.
     - Labels: ticker symbol centered inside each bubble.
     - Tooltip on hover: show ticker, name, sector **only for non-ETF entries** (skip tooltip entirely when `marketCap` is missing per requirement).
   - **Table (50 rows):**
     - Columns exactly: “Ticker symbol”, “Full company name”, “Sector”, “Market cap”.
     - Format market cap using `d3.format` (e.g., to “1.64T”, “850.20B”, etc.).
   - **Linked selection (bubble ↔ row):**
     - Maintain a single `selectedTicker`.
     - On bubble click: set selection, apply `.selected` class to bubble and matching `<tr>`, scroll row into view if needed.
     - On row click: set selection, apply `.selected` class to row and matching bubble.
   - **Price history visualization from `data/indiv-stock/`:**
     - On selection (bubble or row), load that ticker’s history CSV from `data/indiv-stock/` (based on the observed filename pattern), parse date + close/adj close, and render a small line chart/sparkline in the details area.
     - Cache loaded histories to avoid repeated reads.
     - If a history file is missing, show a small message in the details area rather than failing.
6. **Write `/root/output/css/style.css` for layout + interaction.**
   - Use flexbox to place the bubble chart and table **side-by-side horizontally**.
   - Add styles for `.tooltip` (absolute-positioned, `pointer-events:none`) and `.selected` highlights for both bubbles and table rows.
7. **Use terminal/tooling safely and verify outputs.**
   - When using the terminal tool, run **one command per call** or chain with `&&` (don’t submit multiple separate commands unchained).
   - When writing files from shell, prefer heredocs like `cat <<'EOF' > file` to avoid quoting/interpolation errors.
   - Verify:
     - All required paths exist under `/root/output/`.
     - `node --check /root/output/js/visualization.js` passes.
## Expected Result
Opening `/root/output/index.html` in a browser shows (1) a sector-clustered bubble chart sized by market cap (ETFs uniform), colored by sector with legend, collision-free, ticker labels, and tooltips only for non-ETFs; and (2) a table of all 50 stocks with the specified columns and formatted market caps. Clicking either a bubble or table row highlights the other, and a small linked line/sparkline view renders that selection’s price history from `/root/output/data/indiv-stock/`.
