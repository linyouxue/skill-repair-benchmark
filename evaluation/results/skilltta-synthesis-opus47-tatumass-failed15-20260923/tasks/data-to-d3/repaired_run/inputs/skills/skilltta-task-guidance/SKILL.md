---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the target task asks you to build a static, browser-openable **D3.js v6 single-page web app** that visualizes CSV/JSON input data from a local path and must produce a specific directory layout (HTML, JS, CSS, data copy). Before acting, gather:
- The exact required output paths and filenames the prompt lists (index.html, js/, css/, data/).
- The exact input data locations, their schema (columns, whether some rows lack fields, ETF vs. stock distinctions, etc.).
- Every visual/interactive requirement enumerated in the prompt (chart types, layout, sizing rules, coloring rules, legends, labels, tooltips, tables, cross-highlight interactions, number formatting).
- The D3 version pinned by the prompt — you must vendor that exact minified file locally (no CDN).

Note that the retrieved examples are Python/matplotlib data-plot tasks; they are **not** relevant as code templates. Use them only as a reminder to (a) read input files carefully, (b) respect column/field names exactly, and (c) handle missing/edge-case rows explicitly.

## Possible Failure Modes
- **Loading D3 from a CDN** instead of writing a real `js/d3.v6.min.js` file. The grader opens the page offline; remote scripts silently fail.
- **Wrong D3 major version** (e.g., using v7 APIs like `d3.scaleOrdinal(d3.schemeCategory10)` differences, or v3/v4 `.enter()` patterns). Match the version the prompt names.
- **Not copying input data** into `output/data/` and instead referencing the original `/root/data/...` path — the app must be self-contained under `/root/output/`.
- **Loading CSVs via `file://`** — some `d3.csv` fetches fail on `file://`. Prefer a structure that works when the file is opened directly, or make the grader-visible behavior robust (e.g., embed data or use relative fetches that work in headless Chromium).
- **Treating ETFs like stocks**: applying market-cap sizing, tooltips, country/website fields to rows that lack them. Detect ETF rows (missing `marketCap`, `country`, `website`, or an explicit type/sector flag) and branch behavior.
- **Overlapping bubbles or bubbles flying off-canvas**: forgetting `forceCollide`, or using `forceCenter` alone without per-cluster `forceX`/`forceY` anchors, or setting anchors far outside the SVG viewport.
- **Sectors not clustering visibly**: computing cluster centers randomly or without a stable sector→(x,y) map; or letting `forceCenter` dominate `forceX/Y`.
- **Missing sector legend** or legend not color-synced with the bubble fill scale (must reuse the same ordinal color scale instance).
- **Market cap formatting**: raw scientific notation or unformatted digits. Requirement is human-readable suffixes (K/M/B/T). Implement a formatter (`d3.format` alone won't produce a "T" suffix — write a small function).
- **No bidirectional linking**: highlighting only one direction (bubble→row or row→bubble). Both must work, and clicking again or clicking another item should clear/replace the previous highlight.
- **Tooltips shown for ETFs** despite the prompt forbidding it.
- **Labels outside bubbles or unreadable**: not scaling font to bubble radius, or not centering text with `text-anchor: middle` and `dominant-baseline: central`.
- **Charts stacked vertically** instead of side-by-side (missing flex/grid layout in CSS).
- **Non-deterministic layout that fails automated inspection**: e.g., simulation not stopped or ticks not run before screenshot; consider running the simulation synchronously for N ticks or letting it settle.

## Possible procedures
1. **Scaffold files first** in the exact required tree. Create empty `index.html`, `js/visualization.js`, `js/d3.v6.min.js`, `css/style.css`, and `data/` (copy the input CSV and per-stock directory verbatim).
2. **Vendor D3 v6** by downloading the actual minified source into `js/d3.v6.min.js`. Reference it in `index.html` with a relative path. Do not use a `<script src="https://...">` tag.
3. **HTML shell**: two side-by-side containers (flexbox or CSS grid) — left for the SVG bubble chart, right for a scrollable table. Include a tooltip `div` hidden by default.
4. **Data load**: in `visualization.js`, use `d3.csv("data/<file>.csv", d3.autoType)` (or manual coercion for `marketCap`). Parse numeric fields; leave ETF numeric fields as `null`/`NaN` and branch on that.
5. **Scales**:
   - Radius: `d3.scaleSqrt().domain([min, max]).range([rMin, rMax])` over non-null market caps; ETFs get a fixed radius.
   - Color: `d3.scaleOrdinal().domain(uniqueSectors).range(d3.schemeTableau10 or similar)`.
6. **Cluster centers**: build a map `sector -> {x, y}` by laying sectors out on a grid or circle inside the SVG bounds. Feed these into `forceX(d => centers[d.sector].x)` and `forceY(d => centers[d.sector].y)` with a moderate strength (~0.1–0.3). Add `forceCollide(d => r(d) + padding)` and optionally a weak `forceCenter` at the SVG middle.
7. **Rendering bubbles**: bind data to `<g>` groups so each bubble has a `<circle>` and a `<text>` (ticker) that move together on `tick`. Set `text-anchor: middle`, `dominant-baseline: central`, and font-size proportional to radius (with a minimum for readability).
8. **Legend**: iterate the color scale's domain, rendering a small swatch + sector label in a corner group.
9. **Tooltip**: `mouseover`/`mousemove`/`mouseout` handlers on circles. Guard: `if (isETF(d)) return;` before showing tooltip.
10. **Table**: build `<table>` with header row and one `<tr data-ticker="...">` per stock. Format market cap with a helper like:
    ```
    function fmtCap(n){ if(!n) return "—";
      const units=[["T",1e12],["B",1e9],["M",1e6],["K",1e3]];
      for(const [s,v] of units) if(n>=v) return (n/v).toFixed(2)+s;
      return n.toString(); }
    ```
11. **Linking**: keep a single `selectedTicker` state. On bubble click, set it, then apply a `.selected` class to the matching `<circle>` and `<tr>`; remove it from all others. On row click, do the same in reverse. Style `.selected` in CSS (stroke, background).
12. **CSS**: flex layout for side-by-side; tooltip absolute-positioned; `.selected` styling; table with sticky header and scroll.
13. **Verify locally** by opening `index.html` in a browser (and/or a headless run). Confirm all 50 rows appear, clusters visibly separate, no overlap, legend present, cap format readable, and click-linking works both ways.

## Verification Checklist
- [ ] All required files exist at exactly the paths named in the prompt, and `data/` contains a copy of the input CSV plus the per-stock directory.
- [ ] `js/d3.v6.min.js` is a real local D3 v6 build; `index.html` references it via a relative path and no external CDN URLs are used.
- [ ] Opening `index.html` directly in a browser renders both charts without console errors.
- [ ] Bubble chart: bubble area scales with market cap for stocks; ETFs are a uniform size; every bubble shows its ticker centered inside; no overlapping circles.
- [ ] Sector clusters are visibly grouped (via `forceX`/`forceY` per-sector centers) and the overall cluster arrangement is centered within the SVG, not clipped.
- [ ] A legend maps each sector color to its sector name, using the same color scale as the bubbles.
- [ ] Hover on a stock bubble shows a tooltip with ticker, name, and sector; hover on an ETF bubble shows **no** tooltip.
- [ ] Table has exactly the required columns in the required order, lists all rows, and market cap is formatted with K/M/B/T suffixes (or an equivalent easy-to-read format); ETFs show a sensible placeholder.
- [ ] Clicking a bubble highlights its table row; clicking a row highlights its bubble; selecting a new item clears the previous selection.
- [ ] Layout is horizontally side-by-side (chart left, table right or vice versa), not stacked vertically.
- [ ] No code, identifiers, paths, or values were copied verbatim from retrieved examples (which were unrelated Python tasks); the skill's guidance was adapted, not transplanted.
- [ ] Recovery check: if data fails to load via `file://`, confirm the fetch path is relative to `output/` and matches the copied data location; if the simulation never settles or bubbles drift off-screen, reduce `forceX/Y` targets to lie within the viewBox and verify `forceCollide` is added.
