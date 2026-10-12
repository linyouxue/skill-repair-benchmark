---
name: d3-visualization
description: Build deterministic, verifiable D3.js visualizations from local data by translating requirements into testable behaviors, typing data explicitly, and producing standalone offline HTML/SVG.
---

# D3.js Visualization Skill

Use this skill to turn structured data (CSV/TSV/JSON) into **clean, reproducible** visualizations using **D3.js**. The goal is to produce **stable outputs** that can be verified by diffing files or hashing.

## Plan from evidence (not just prompt keywords)

1. Inventory provided inputs (files/folders) and note what each should drive in the UI (or explicitly justify why it is unused).
2. Convert every MUST/SHOULD/DO-NOT requirement into an observable behavior you can test (a checklist).
3. Identify conditional branches (e.g., “category A has no tooltip”, selected vs unselected states) and commit to testing at least one positive and one negative example for each branch.
4. Choose the chart type/encodings from the data types (categorical vs numeric vs time), then commit to fixed dimensions and scales.
5. Spec-lock before declaring done: confirm the rendered UI contains **only** the requested views/layout (no extra panels), and each conditional interaction uses the **exact predicate stated in the spec**.
6. After implementation, run an end-to-end verification pass that checks each checklist item in the rendered artifact (not just syntax).

Read references/requirements-checklist.md when the spec has conditional UI rules, linked interactions, strict layout constraints, or multiple declared input sources. Skip when the task is purely “render this static SVG from one file with no conditions.”

---

## When to use

Activate this skill when the user asks for any of the following:

- “Make a chart/plot/graph/visualization”
- bar/line/scatter/area/histogram/box/violin/heatmap
- timelines, small multiples, faceting
- axis ticks, scales, legends, tooltips
- data-driven SVG output for a report or web page

If the user only needs a quick table or summary, **don’t** use D3—use a spreadsheet or plain markdown instead.

---

## Determinism rules (non-negotiable)

To keep results stable across runs and machines:

### Data determinism
- **Sort** input rows deterministically before binding to marks (e.g., by x then by category).
- Use stable grouping order (explicit `Array.from(grouped.keys()).sort()`).
- For conditional UI behavior, implement the **literal predicate from the spec** as a named function, and test it with at least one example on each side of the predicate.

```js
// Deterministic order + spec-literal predicates + missingness fallbacks
const rows = data
  .map(d => ({ ...d, key: String(d.key) }))
  .sort((a, b) => d3.ascending(a.key, b.key));

// Spec-literal predicates should be named and used directly by event handlers.
// Example: the spec defines tooltip suppression via missing fields (not a label).
const isMissing = v => v == null || String(v).trim() === "";
const suppressTooltip = d => isMissing(d.a) && isMissing(d.b) && isMissing(d.c);

// Labels/flags can still exist for encodings (color/legend), but should not replace
// the spec predicate for rubric-checked behavior.
const categoryForColor = d => String(d.category || "");

const valueOr = (v, fallback) => (v == null || Number.isNaN(v)) ? fallback : v;
```

Decision rule: If the spec says “no tooltip because fields F are missing”, do **not** implement it as “category == label”; implement `missing(F)` and verify one suppressed row + one non-suppressed row by hovering.

Read references/spec-literal-predicates.md when the spec defines a conditional via missingness, thresholds, or composite logic and you are tempted to substitute a label/proxy. Skip when the conditional is purely presentational (e.g., a color palette choice) and not rubric-checked.

### Rendering determinism
- **No randomness**: do not use `Math.random()` or `d3-random`.
- **No transitions/animations** by default (transitions can introduce timing variance).
- **Fixed** `width`, `height`, `margin`, `viewBox`.
- Avoid layout algorithms with non-deterministic iteration unless you control seeds/iterations (e.g., force simulation). If a force layout is required:
  - fix the tick count,
  - fix initial positions deterministically (e.g., sorted nodes placed on a grid),
  - run exactly N ticks and stop.

```js
// Deterministic force layout initialization
nodes.sort((a, b) => d3.ascending(a.key, b.key));
nodes.forEach((d, i) => { d.x = (i % 20) * 10; d.y = Math.floor(i / 20) * 10; });

const sim = d3.forceSimulation(nodes)
  .force("charge", d3.forceManyBody().strength(-20))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .stop();

for (let i = 0; i < 200; i++) sim.tick();
```

### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- Pin D3 to a specific version.

### File determinism
- Stable SVG output:
  - Avoid auto-generated IDs that may change.
  - If you must use IDs (clipPath, gradients), derive them from stable strings.

---

## Interactive features (tooltips, click handlers, hover effects)

When the task requires interactivity (e.g., tooltips on hover, click to highlight):

```js
// Tooltip pattern: deterministic, conditional, and testable
const tooltip = d3.select("body").append("div").attr("id", "tooltip");

function showTooltip(event, d) {
  tooltip
    .style("position", "absolute")
    .style("pointer-events", "none")
    .style("opacity", 1)
    .html(`<strong>${d.label}</strong><br/>${d.detail}`)
    .style("left", `${event.pageX + 8}px`)
    .style("top", `${event.pageY - 8}px`);
}

function hideTooltip() { tooltip.style("opacity", 0); }
```

Decision rule: If the spec includes a conditional interaction, verify both branches in the rendered page; do not treat `node --check` as acceptance.

---

## Outputs you should produce

Prefer producing **all of** the following when feasible:

1. `dist/chart.html` — standalone HTML that renders the visualization
2. `dist/chart.svg` — exported SVG (stable and diff-friendly)
3. (Optional) `dist/chart.png` — if the task explicitly needs a raster image

Always keep outputs in a predictable folder (default: `dist/`), unless the task specifies paths.

---

## Common Pitfalls

- Treating a syntax check (e.g., `node --check`) or casual visual inspection as proof that UI requirements are met; you must verify behaviors (tooltip content/conditions, interactions, layout constraints, data coverage) in the rendered artifact.
- Implementing conditional behavior with a “reasonable proxy” predicate when the spec defines a different literal condition; match the spec’s predicate exactly, then spot-check both branches using rows chosen by that predicate.
- Using only one of multiple provided input sources without acknowledging it; either integrate each source into the UI or explicitly justify why it is unused.
