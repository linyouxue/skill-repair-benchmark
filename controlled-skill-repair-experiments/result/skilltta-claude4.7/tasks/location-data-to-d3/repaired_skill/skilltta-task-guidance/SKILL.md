---
name: skilltta-task-guidance
description: Task-specific guidance for building a D3.js v6 bubble chart + linked data table visualization
---

# Task Guidance: D3 Bubble Chart + Linked Table

## Deliverable Structure
Produce exactly these files:
- `/root/output/index.html` — single page, loads CSS + JS by relative paths
- `/root/output/js/d3.v6.min.js` — the actual D3 v6 library source (not a stub). If offline, fetch from CDN once or copy a bundled copy. Verify with `head -c 200` that it contains real D3 code, not placeholder text.
- `/root/output/js/visualization.js` — all chart logic
- `/root/output/css/style.css` — layout + highlight styles
- `/root/output/data/stock-descriptions.csv` and `/root/output/data/indiv-stock/*.csv` — copied from `/root/data/`

Use `cp -r /root/data/* /root/output/data/` and have JS load from `data/stock-descriptions.csv` (relative).

## Layout (side-by-side)
```css
.container { display: flex; flex-direction: row; gap: 20px; }
#bubble-chart { flex: 0 0 60%; }
#table-container { flex: 1; overflow-y: auto; max-height: 90vh; }
```

## Mandatory CSS Rules (copy verbatim into style.css)
These rules are **required** for the acceptance tests to pass. Do not omit any of them.
```css
/* Prevent SVG text labels from swallowing click/hover events on the bubble beneath. */
svg text { pointer-events: none; }
.bubble-label { pointer-events: none; }

/* Selection highlight — must match the class names used by selectTicker(). */
circle.bubble.selected { stroke: #000; stroke-width: 3px; }
tr.stock-row.selected { background: #ffe08a; }
```
If you forget `pointer-events: none` on the label text, clicks on the center of each bubble (where the ticker label sits) will be absorbed by the `<text>` and the row will never highlight. This is the single most common failure mode.

## Bubble Chart Requirements (verify every one)
1. **Size by marketCap**: use `d3.scaleSqrt().domain([minCap, maxCap]).range([15, 55])`. For ETFs (no marketCap), assign a fixed radius (e.g., 20).
2. **Color by sector**: `d3.scaleOrdinal(d3.schemeTableau10)` on unique sectors. Include ETFs as their own "sector" if the CSV marks them so, or treat missing sector as 'ETF'.
3. **Clustering via force simulation**:
   - Compute a target (cx, cy) per sector arranged on a grid or circle **inside** the chart area (not scattered). E.g., place sector centers on a circle of radius = min(width,height)*0.25 around chart center.
   - Forces: `forceX(d => sectorCenter[d.sector].x).strength(0.15)`, `forceY(...).strength(0.15)`, `forceCollide(d => d.r + 2)`, and a weak `forceCenter(width/2, height/2)` to keep everything centered.
4. **Bubble DOM structure (critical for clickability)**:
   - For each datum append a `<circle>` with `.classed('bubble', true).attr('data-ticker', d.ticker)`. The circle is the clickable/hoverable element — attach `.on('click', ...)` and `.on('mouseover', ...)` to **circles**, not to a wrapping `<g>` (empty space in a `<g>` doesn't receive pointer events).
   - Append the `<text>` label **after** the circle so it renders on top, with class `bubble-label`, `text-anchor: middle`, `dominant-baseline: central`, font-size scaled to radius (e.g., `Math.min(d.r/2, 14)`). The label MUST be non-interactive — enforced by the mandatory CSS above and optionally also by inline `.attr('pointer-events','none')`.
   - Example:
     ```js
     const circles = svg.selectAll('circle.bubble')
       .data(data).enter()
       .append('circle')
         .classed('bubble', true)
         .attr('data-ticker', d => d.ticker)
         .attr('r', d => d.r)
         .attr('fill', d => color(d.sector));
     svg.selectAll('text.bubble-label')
       .data(data).enter()
       .append('text')
         .classed('bubble-label', true)
         .attr('pointer-events', 'none')
         .attr('text-anchor', 'middle')
         .attr('dominant-baseline', 'central')
         .text(d => d.ticker);
     ```
5. **Legend**: render a `<g>` with one swatch+label per sector in a corner of the SVG.
6. **Tooltip on hover**: a single absolutely-positioned `<div class="tooltip">` toggled via mouseover/mousemove/mouseout. **For ETFs, hide any existing tooltip and return early**:
   ```js
   .on('mouseover', function(event, d){
     if(!d.marketCap){ // ETF
       d3.select('#tooltip').classed('visible', false); // hide stale tooltip
       return;
     }
     d3.select('#tooltip').classed('visible', true)
       .html(`<b>${d.ticker}</b><br>${d.name}<br>${d.sector}`)
       .style('left',(event.pageX+10)+'px').style('top',(event.pageY-10)+'px');
   })
   .on('mouseout', () => d3.select('#tooltip').classed('visible', false));
   ```

## Data Table
- Columns: Ticker | Full name | Sector | Market cap
- Format market cap: write a helper
```js
function fmtCap(v){
  if(!v || isNaN(v)) return 'N/A';
  const n = +v;
  if(n >= 1e12) return (n/1e12).toFixed(2)+'T';
  if(n >= 1e9)  return (n/1e9).toFixed(2)+'B';
  if(n >= 1e6)  return (n/1e6).toFixed(2)+'M';
  return n.toString();
}
```
- **Each `<tr>` MUST be created with `.classed('stock-row', true).attr('data-ticker', d.ticker)`** — the linking code below relies on both the class and the data attribute. Example row-binding:
```js
const rows = d3.select('#stock-table tbody')
  .selectAll('tr.stock-row')
  .data(data).enter()
  .append('tr')
    .classed('stock-row', true)
    .attr('data-ticker', d => d.ticker);
rows.append('td').text(d => d.ticker);
rows.append('td').text(d => d.name);
rows.append('td').text(d => d.sector);
rows.append('td').text(d => fmtCap(d.marketCap));
```
Without the `stock-row` class or the `data-ticker` attribute, `selectTicker` silently matches nothing and bidirectional linking fails without errors.

## Bidirectional Linking (critical acceptance criterion)
Use a single shared selection function that both the circle click handler and the row click handler call. Both selections must use the same class names referenced in the mandatory CSS (`circle.bubble.selected`, `tr.stock-row.selected`).
```js
let selectedTicker = null;
function selectTicker(ticker){
  selectedTicker = ticker;
  d3.selectAll('circle.bubble').classed('selected', d => d.ticker === ticker);
  d3.selectAll('tr.stock-row').classed('selected', function(){
    return this.dataset.ticker === ticker;
  });
  // Scroll table row into view
  const row = document.querySelector(`tr.stock-row[data-ticker="${ticker}"]`);
  if(row) row.scrollIntoView({block:'nearest', behavior:'smooth'});
}
circles.on('click', (event, d) => selectTicker(d.ticker));
rows.on('click', function(){ selectTicker(this.dataset.ticker); });
```

### Clickability Pitfall (from location hint — do not skip)
- The `<text>` label on top of each bubble will **swallow click events** unless `pointer-events: none` is set. The mandatory CSS block above enforces this; also set `.attr('pointer-events','none')` inline as belt-and-suspenders.
- Attach handlers to the `<circle>` element itself, not to a parent `<g>` only (empty space in a `<g>` does not receive pointer events).
- Verify both directions manually by clicking **the exact center of the bubble (where the ticker letters are)** — not just the edge. If the row doesn't highlight, your label is still eating the click.

## Loading Pattern (from retrieved CSV-plotting examples)
Those examples (BigCodeBench/68, /1011, /640) all follow: load CSV → compute derived values → render chart. Apply same discipline here:
```js
d3.csv('data/stock-descriptions.csv', d3.autoType).then(data => {
  // normalize fields: ticker, name, sector, marketCap, country, website
  // detect ETFs by missing marketCap
  renderBubble(data);
  renderTable(data);
});
```
Use `d3.autoType` so marketCap is numeric for the scale and formatter.

## Self-Verification Checklist Before Finishing
- [ ] `index.html` opens standalone (file://) without CORS by using relative data paths and a locally saved `d3.v6.min.js`.
- [ ] All 50 rows appear in the table, every `<tr>` has class `stock-row` and attribute `data-ticker`.
- [ ] Every `<circle>` has class `bubble` and attribute `data-ticker`; every label `<text>` has class `bubble-label`.
- [ ] `style.css` contains both `svg text { pointer-events: none; }` and `.bubble-label { pointer-events: none; }`.
- [ ] Each bubble has a visible ticker label; no overlap after simulation settles.
- [ ] Clusters are visibly grouped and centered within the SVG viewport.
- [ ] Hovering a non-ETF bubble shows ticker/name/sector tooltip.
- [ ] Hovering an ETF bubble shows **no** tooltip — and any previously visible tooltip is hidden on entering the ETF.
- [ ] **Click directly on the center of a bubble (over the ticker letters)** → the matching row gets `.selected` background and scrolls into view.
- [ ] Click a table row → the matching circle gets the `.selected` black stroke.
- [ ] Repeat both click directions for at least 2 different tickers (one large-cap, one ETF-or-small) to confirm linking is not accidental.
- [ ] Legend lists every sector color present.
