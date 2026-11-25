---
name: skilltta-task-guidance
---

# Skill: D3 v6 single-page dashboard (force bubbles + linked table)

This skill provides a reusable pattern to build a **single-page** D3.js (v6) web app that:
- loads CSV data from local `data/` paths,
- renders a **force-directed bubble cluster chart** (colored by category, sized by a metric),
- renders a **data table**,
- implements **bidirectional linking** (click bubble ⇄ click table row),
- uses a tooltip with conditional display rules,
- includes legends and collision avoidance,
- avoids common interaction bugs caused by label overlays.

## 1) Project layout and offline-friendly loading

**Required output layout** (keep paths stable so relative loading works when opened in a browser):
- `index.html`
- `js/d3.v6.min.js` (local copy)
- `js/visualization.js`
- `css/style.css`
- `data/` (copy input CSV(s) and subfolders exactly)

In `index.html`:
- include D3 via `<script src="js/d3.v6.min.js"></script>`
- include your code via `<script defer src="js/visualization.js"></script>`
- ensure data is loaded with **relative URLs** like `data/stock-descriptions.csv`.

> Note: When a browser blocks local file fetches, opening via a simple static server fixes it. Still, implement everything as relative paths and avoid absolute `/root/...` references in the web code.

## 2) Data ingestion + normalization (CSV → typed fields)

Use the “load → preprocess → render” pipeline:

- `d3.csv(url, rowParser)` to type fields.
- Create a stable ID key (e.g., ticker symbol) used across chart and table.

Recommended parsing steps:
- Parse numeric fields: market cap, etc. Convert empty strings to `null`.
- Add derived fields used by the visualization:
  - `isETF` (if market cap missing / category indicates ETF)
  - `radius` (size mapping; ETFs uniform)
  - `sector` (fallback like `"Unknown"` if missing)

Formatting helpers:
- `formatMarketCap(x)` that returns `"—"` for null and `1.64T / 820B / 35.2M` style strings.

## 3) Bubble chart: force simulation with sector clustering

### Core pattern
- Use an SVG with a `<g>` container.
- Bind nodes via `selection.data(data, d => d.id)`.
- Represent each node as a **group** `<g class="node">` containing:
  - a `<circle>`
  - a `<text>` label (ticker)

This makes it easy to move circle+label together in the simulation tick.

### Forces (cluster + center + collide)
To ensure **clusters are close together and centered**:
- `forceCenter(width/2, height/2)`
- `forceX(d => sectorX[d.sector]).strength(0.15~0.35)`
- `forceY(d => sectorY[d.sector]).strength(0.15~0.35)`
- `forceCollide(d => d.radius + padding)`

**Sector target positions**:
- Compute unique sectors.
- Place their (x,y) “cluster anchors” on a compact grid or circle around center.
- Keep anchor spread small so clusters aren’t scattered.

Example anchor strategy:
- grid with `cols = ceil(sqrt(nSectors))`
- cell size around `min(width,height)/3` total spread

### Size + color
- `radius = scaleSqrt(marketCap)` for non-ETF.
- ETFs: fixed radius (e.g., 12).
- `color = d3.scaleOrdinal().domain(sectors).range(d3.schemeTableau10 / schemeSet2 etc.)`

### Tick update
On `tick`, update node group transform:
- `node.attr("transform", d => `translate(${d.x},${d.y})`)`

## 4) Labels that do not block clicking (overlay text layer fix)

Common failure: the `<text>` label sits on top of the circle and **steals pointer events**, causing “click bubble” to be unreliable.

Reliable patterns:

**Pattern A (recommended):** attach all mouse events to the node `<g>` and disable pointer events on the text.
- `node.on("click", ...)` and `node.on("mouseover", ...)`
- `node.select("text").style("pointer-events", "none")`

**Pattern B:** attach events to the circle and also disable pointer events on text.

Either way, ensure:
- `cursor: pointer;` is applied to clickable nodes.

## 5) Tooltip with conditional display (skip ETFs)

Create a single absolutely-positioned `<div class="tooltip">`.

On hover:
- If `d.isETF` (or required fields missing): **do nothing** (no tooltip).
- Else show:
  - ticker
  - company name
  - sector

Positioning:
- use `event.pageX / pageY` with a small offset.

Hide tooltip on `mouseout`.

## 6) Legend for sector colors

Add a legend group in SVG or a separate HTML container.

Pattern:
- `sectors.forEach((s,i) => legend.append("g")...)`
- show colored swatch + sector name.

Keep legend compact and readable.

## 7) Data table next to chart

Use an HTML `<table>` with `<thead>` and `<tbody>`.

Render pattern:
- `tbody.selectAll("tr").data(data, d => d.id).join("tr")`
- create `td` for:
  - Ticker symbol
  - Full company name
  - Sector
  - Market cap (formatted)

Add row hover style (optional) and a `selected` class for highlighting.

## 8) Bidirectional linking: click bubble ⇄ click row

Maintain a single source of truth:
- `let selectedId = null;`

Create an `updateSelection(id)` function that:
- sets `selectedId`
- updates bubble styles (`.classed("selected", d => d.id===selectedId)`)
- updates row styles (`.classed("selected", d => d.id===selectedId)`)
- optionally scrolls the row into view.

Event wiring:
- bubble click: `updateSelection(d.id)`
- row click: `updateSelection(d.id)`

Styling recommendations:
- `.node.selected circle { stroke: #111; stroke-width: 3px; }`
- `tr.selected { background: #ffe9a8; }`

## 9) Robustness checklist (common verifications)

- **No overlap**: `forceCollide` uses `radius + padding`.
- **Centered clusters**: add `forceCenter` and keep sector anchors near center.
- **Ticker label inside bubble**: set text anchor middle; font size relative to radius; pointer-events none.
- **ETF tooltip suppressed**: check missing `marketCap/country/website` (or explicit ETF marker) before showing tooltip.
- **Legend present** and color mapping stable.
- **Click works even when clicking on text**: ensure pointer-events on text are disabled or events bound to parent `<g>`.

## 10) Implementation flow template

1. Load CSV.
2. Preprocess (types, sectors list, scales, radius).
3. Build SVG + legend.
4. Build simulation and nodes.
5. Build tooltip handlers.
6. Build table.
7. Implement `updateSelection` and attach click handlers.

This structure mirrors the general “load → transform → visualize” pattern used in data plotting tasks: prepare data first, then render, then add interactivity.
