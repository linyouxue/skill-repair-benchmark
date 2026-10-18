---
name: d3-visualization
description: Build deterministic, verifiable data visualizations with D3.js (v6). Generate standalone HTML/SVG (and optional PNG) from local data files without external network dependencies. Use when tasks require charts, plots, axes/scales, legends, tooltips, or data-driven SVG output.
---

# D3.js Visualization Skill

Use this skill to turn structured data (CSV/TSV/JSON) into **clean, reproducible** visualizations using **D3.js**. The goal is to produce **stable outputs** that can be verified by diffing files, hashing, or automated DOM queries.

## When to use

Activate this skill when the user asks for any of the following:

- "Make a chart/plot/graph/visualization"
- bar/line/scatter/area/histogram/box/violin/heatmap
- timelines, small multiples, faceting
- axis ticks, scales, legends, tooltips
- data-driven SVG output for a report or web page
- converting data to a static SVG or HTML visualization
- an interactive HTML page with a chart + accompanying table

If the user only needs a quick table or summary, **don't** use D3—use a spreadsheet or plain markdown instead.

---

## Derive the evaluator contract first

Automated evaluators query the DOM and the filesystem for exact strings, counts, class names, selectors, row indices, and file paths. "Reasonable-looking" renderings fail scoring because micro-decisions (which inputs are consumed, row order, placeholder text, class name, tooltip carrier, filename casing) silently diverge from what the evaluator asserts. Before writing any rendering code, write a numbered contract as a comment block at the top of the output file. The contract has **five passes**:

- **Pass A — input inventory.** List every file and directory the task text names as input. For each, write one sentence stating what the final deliverable does with it (load into chart, cross-reference from table, render per-item detail, copy to output path, …). An input whose only use is "copy to output and nothing else" is a red flag — re-read the task for an implied downstream use (sparkline, mini-chart, on-select detail, time-series overlay) before coding. For every pair of inputs where identifiers from one must resolve to files under another, add a cross-file lookup consistency check on a case-sensitive filesystem.
- **Pass B — output contract.** For each DOM/file claim: row order, cell text and missing-value placeholder, DOM shape (plain text vs. child elements), interactive-state class names (verbatim from task), tooltip carrier, interaction semantics on re-click, and exact output paths.
- **Pass C — provenance + external grounding.** Tag every Pass A/B item `[LITERAL]` (task text pins the value verbatim) or `[GUESS]` (you chose a default). Before locking any `[GUESS]`, scan the task directory **and its parents** for an external oracle: `evaluator*`, `test*`, `rubric*`, `expected*`, `reference*`, `*.spec.*`, `*example*`, READMEs, scoring scripts, golden-output files, jsdom/pytest harnesses. If any such artifact resolves an item, derive the value from it and re-tag `[LITERAL]`.
- **Pass D — resolve surviving `[GUESS]` items by minimal literal reading.** When the external-grounding scan returns nothing, pick the **single simplest literal reading** of the spec for each surviving `[GUESS]` and implement exactly that — nothing more. Do NOT implement both branches of a dichotomy; every added hedge is a surface a strict literal grader rejects. Concrete literalism rules when the task is silent:
  - **Click semantics.** Task says "click X highlights Y" and nothing about second clicks → `click-sets-selection`: on click, clear the class from every mark, then apply it to the clicked mark. Do NOT add toggle-off, idempotency, or any second-click behaviour.
  - **Selected class.** Task names a class → use that class alone. Task is silent → use `"selected"` alone. Do NOT apply a secondary `"active"`/`"highlighted"` class.
  - **Tooltip carrier.** Pick ONE carrier matching the task's wording. Task says "hover shows a tooltip" → shared `<div class="tooltip">` with mouseover/mouseout + opacity. Task is silent about hover UI → `<title>` child alone. Do NOT wire both.
  - **Tooltip text.** Plain unlabeled values, one field per line. Do NOT prefix with `"Field:"` labels unless the task uses labels.
  - **Missing/not-applicable cell.** Mirror any placeholder string the task mentions even once. Task is silent on a subset AND the task's example shows a non-empty format for that column → **empty cell** (not `"N/A"`, not `"-"`, not `"—"`). Use `"N/A"` only when the task text explicitly uses that string.
- **Pass E — minimality audit.** Before writing code, list every feature the planned implementation will have. For each, ask: *does the task text literally name this feature?* If no, remove it. Audit specifically against the accumulated-cruft list below — these features have each been invented across prior rounds and failed:
  - toggle-off / idempotent / any second-click branch (unless the task names second-click behaviour)
  - secondary class alongside `"selected"` (unless the task names a second class)
  - multiple tooltip carriers wired together (`<title>` + `data-tooltip` + `div.tooltip`)
  - labeled tooltip text with `"Ticker:"/"Name:"/"Sector:"` prefixes (unless the task uses labels)
  - `"N/A"` placeholder for a subset the task is silent about
  - bespoke chart layouts (per-category clustering, hard-coded cluster-center grids) when the task names only the chart type
  - fixed non-standard viewBox dimensions (e.g., `720×640`) when the task does not pin dimensions
  - internal invariants in the harness (cluster-tightness, bubble-radius thresholds, specific node spacing)

```javascript
/* EVALUATOR CONTRACT (derived from task text; provenance tagged)
 * PASS A — inputs
 *   <input_1>:        <use>                           // [LITERAL]
 *   cross-file:       ids in <index> resolve under <data_dir>  // [LITERAL]
 * PASS B — outputs
 *   row order:        <rule>                          // [LITERAL|GUESS]
 *   missing value:    "<placeholder>"                 // [LITERAL|GUESS alts: "", "-", "N/A"]
 *   selected class:   "<name>"                        // [LITERAL|GUESS alts: "selected","highlighted"]
 *   tooltip carrier:  <per-mark selector>             // [LITERAL|GUESS alts: title, div.tooltip]
 *   click semantics:  <sets-selection|toggle|move>    // [LITERAL|GUESS]
 * PASS C — external grounding scan
 *   searched:         evaluator*, test*, rubric*, expected*, reference*, *.spec.*, README
 *   found:            <artifact or "none">
 * PASS D — literalism resolution for each surviving [GUESS]
 *   click:            sets-selection, no second-click branch (task silent on 2nd click)
 *   selected class:   "selected" alone (task silent on class name)
 *   tooltip carrier:  <title> child alone (task silent on hover UI)
 *   missing value:    "" (task example shows "1.64T"; task silent on subset)
 * PASS E — minimality audit (features removed before coding)
 *   removed:          toggle-off branch; "active" class; data-tooltip attr; cluster-grid centers
 */
```

Read `references/evaluator-contract.md` for the full five-pass algorithm, the external-grounding search procedure, the minimality-audit checklist, and the branched verification harness with corrective actions per failure label. Skip when the sole deliverable is a static image diffed against a reference PNG/SVG.

---

## Verify the contract against the rendered DOM

Element-counting is not verification. Neither is asserting agent-chosen internal invariants (force-simulation cluster-tightness, bubble-radius formulas, "idempotent click behaviour the agent chose") — a strict evaluator cannot see those; it dispatches user events and inspects the resulting DOM. The harness must do the same: for every interactive contract item, **dispatch the user event** and assert the **user-visible effect** — but constrain assertions to behaviours the task text literally names. Asserting an agent-chosen semantics (e.g., second-click toggle-off when the task names only the first click) encodes an agent guess as a test and produces false confidence.

```javascript
// Generic shape — observable-behaviour probes constrained to literally-named behaviours
const { JSDOM } = require('jsdom');
const dom = await JSDOM.fromFile(OUTPUT_PATH, { runScripts: 'dangerously' });
await new Promise(r => setTimeout(r, 300));  // let D3 render
const doc = dom.window.document;
const win = dom.window;

// Tooltip probe: dispatch mouseover, assert the single carrier the task implies
const mark = doc.querySelector(MARK_SELECTOR);
mark.dispatchEvent(new win.MouseEvent('mouseover', { bubbles: true }));
const tipText = readTooltipFromTaskCarrier(doc, mark);  // one carrier, not three
console.assert(tipText && tipText.includes(EXPECTED_ID),
    `TOOLTIP ON HOVER: expected substring "${EXPECTED_ID}"`);

// Click-selection probe: first click applies the (single) class the task names
mark.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
console.assert(mark.classList.contains(SELECTED_CLASS), 'FIRST CLICK APPLIES CLASS');
// Dispatch a SECOND click ONLY IF the task text pins second-click behaviour.

// Per-input consumption (Pass A) — every named input has a DOM/fs consumer
console.assert(doc.querySelectorAll(PER_INPUT_SELECTOR).length === IDS.length,
    'PER-INPUT CONSUMPTION');
```

**Do not** assert agent-chosen internal metrics (cluster-tightness, node spacing, bubble-radius thresholds) or agent-chosen semantics the task does not name (toggle-off, idempotency, dual-class application) — passing those produces false confidence. If any observable probe fails, fix the rendering (not the assertion) and re-run. If every assertion passes but scoring still fails, the surviving failure is almost certainly a feature the task did not name — re-run Pass E and remove more, do not add more. Read `references/evaluator-contract.md` for the branched verification algorithm with corrective actions per failure label.

---

## Inputs you should expect

- One or more local data files: `*.csv`, `*.tsv`, `*.json`
- A chart intent: chart type, fields, sort/filter rules, dimensions, color rules, labels.
- Output constraints: "static only", "no animation", "must be deterministic", "offline", etc.

If details are missing, apply the Pass D literalism rules above and document each resolved default in the contract comment.

---

## Outputs you should produce

Prefer producing **all of** the following when feasible:

1. `dist/chart.html` (or the exact path the task names) — standalone HTML that renders the visualization
2. `dist/chart.svg` — exported SVG (stable and diff-friendly)
3. (Optional) `dist/chart.png` — if the task explicitly needs a raster image

Always keep outputs at the paths the task specifies; otherwise default to `dist/`.

---

## Table rendering from CSV

When the task includes a tabular output alongside (or instead of) a chart, treat it as an **identity transformation plus column selection**: row order mirrors the file, cells contain plain text, missing values default to empty string.

```javascript
// Bind in file order — do NOT .sort() unless the task says so
const rows = d3.select('tbody').selectAll('tr')
    .data(parsedCsvInFileOrder)
    .join('tr');

rows.selectAll('td')
    .data(d => COLUMNS.map(c => formatCell(d, c)))
    .join('td')
    .text(s => s);        // use .text(), never .html(); no child elements

function formatCell(d, col) {
    const v = d[col];
    if (v != null && v !== '') return String(v);
    // Default: empty cell when the task is silent on this subset.
    // Only return "N/A" (or "-", "—") when the task text explicitly names that string.
    return TASK_PLACEHOLDER_FOR[col] ?? '';
}
```

**Rule:** apply visual styling (colored pills, badges) via CSS selectors on the `<td>` itself, not by appending `<span>`/`<div>` children. An evaluator that checks `td.children.length === 0` or compares `innerHTML` will fail if the cell contains child elements.

---

## Interactive features (tooltips, click handlers)

Automated evaluators cannot see hover UI; they query the DOM and dispatch user events. Pick **one** tooltip carrier that matches the task's wording and **one** click semantics that the task literally names. Wiring both branches of a dichotomy (e.g., `<title>` AND `data-tooltip` AND `div.tooltip`; or `click-sets-selection` AND `toggle-off`) adds surface area that a strict literal grader rejects.

### Tooltip pattern — single carrier matching task wording

Decide the carrier from a literal cue in the task text. Default when silent is a `<title>` child alone (minimal, DOM-queryable, no visible UI).

```javascript
// Task says "hover shows a tooltip" (visible UI) — use a shared div
const tipDiv = d3.select('body').append('div')
    .attr('class', 'tooltip')
    .style('position', 'absolute').style('opacity', 0)
    .style('pointer-events', 'none');

svg.selectAll('circle.mark')
    .on('mouseover', (e, d) => tipDiv.style('opacity', 1).text(plainText(d)))
    .on('mousemove', (e)    => tipDiv.style('left', (e.pageX + 12) + 'px')
                                     .style('top',  (e.pageY + 12) + 'px'))
    .on('mouseout',  ()     => tipDiv.style('opacity', 0));

// --- OR --- task is silent about hover UI — <title> child alone
svg.selectAll('circle.mark')
    .append('title').text(d => plainText(d));

// Plain unlabeled text, one field per line; no "Field:" prefixes unless the task uses them
function plainText(d) { return [d.id, d.name, d.sector, d.marketCap].filter(v => v != null && v !== '').join('\n'); }
```

**Subset-lacks-fields rule:** when the task says some marks "lack" certain fields, do NOT suppress the tooltip for those marks. Attach the same single carrier to every mark; simply omit the missing fields from the text (do not label them `"N/A"` unless the task uses that string).

### Click handlers — click-sets-selection (no toggle-off branch)

```javascript
const SELECTED_CLASS = TASK_CLASS || 'selected';   // single class; use task's exact name if given

function selectKey(key) {
    // Clear the class from every mark on both sides
    d3.selectAll('[data-key]').classed(SELECTED_CLASS, false);
    // Apply the class to the clicked key on both sides
    if (key != null) d3.selectAll(`[data-key="${key}"]`).classed(SELECTED_CLASS, true);
}
svg.selectAll('circle.mark')
    .attr('data-key', d => d[KEY])
    .on('click', (_, d) => selectKey(d[KEY]));
d3.selectAll('tbody tr')
    .attr('data-key', d => d[KEY])
    .on('click', (_, d) => selectKey(d[KEY]));
```

**Rule:** the handler has **no second-click branch** — a click sets the selection, period. Do not add toggle-off, idempotent-ignore, or background-click-clear unless the task text pins that behaviour. For bubble↔table linking, both sides call the same `selectKey` with the same `data-key`; a single class propagates to both.

Read `references/interactive-dom-contract.md` when the task names a specific tooltip selector verbatim (`[data-tooltip]`, `aria-label`, `title`), when some marks should be interactive and others not, or when the task text explicitly names second-click behaviour (toggle-off, idempotent, move). Skip when the task describes only "click X highlights Y" with no further interactive detail.

---

## Chart layout defaults

When the task names only a chart type (e.g., "bubble chart") and does not name a layout, grouping force, or dimensions, use the standard layout primitive and nothing more. Inventing a per-category clustering force, a hard-coded grid of cluster centers, or a non-standard viewBox is agent-added structure the task did not name.

```javascript
// Bubble layout — standard pack or plain forceSimulation (no clustering force)
const simulation = d3.forceSimulation(nodes)
    .force('charge',    d3.forceManyBody().strength(-30))
    .force('collide',   d3.forceCollide(d => d.r + 1))
    .force('center',    d3.forceCenter(width / 2, height / 2))
    // NO per-category cluster force unless the task names grouping
    .stop();

// Seed initial positions deterministically; run a fixed tick count
nodes.forEach((n, i) => { n.x = (i % 10) * 10; n.y = Math.floor(i / 10) * 10; });
for (let i = 0; i < 300; i++) simulation.tick();
```

**Dimension rule:** use container-proportional dimensions (`viewBox="0 0 960 600"` + CSS `width: 100%; height: auto`) or the exact dimensions the task names. Do not hard-code bespoke non-standard values (e.g., `720×640`) when the task is silent on size. Do not place marks at hand-picked cluster centers (`(120, 240)`, `(360, 240)`, …) — let the layout primitive determine positions.

---

## Determinism rules (non-negotiable)

To keep results stable across runs and machines:

### Rendering determinism
- **No randomness**: do not use `Math.random()` or `d3-random`.
- **No transitions/animations** by default. Opacity transitions on the shared tooltip div are allowed because they do not affect static DOM assertions.
- **Fixed** `width`, `height`, `margin`, `viewBox` — but prefer container-proportional dimensions when the task is silent on size (see Chart layout defaults).
- Force layouts must be seeded and run a fixed number of ticks: fix initial positions deterministically (e.g., sorted nodes on a grid), fix the tick count, stop.

### Offline + dependency determinism
- Do **not** load D3 from a CDN.
- Pin D3 to a specific version (default: **d3@7.9.0**).
- Prefer vendoring a minified D3 bundle (e.g., `vendor/d3.v7.9.0.min.js`).

### File determinism
- Avoid auto-generated IDs; derive IDs from stable strings (e.g., `"clip-plot"`).
- Use LF line endings; keep numeric precision consistent (round to 2–4 decimals).
- **Filename casing must satisfy every cross-file lookup.** When one input file's identifier column (e.g., a `ticker` column) is used to resolve files in a sibling data directory, assert `fs.existsSync(path.join(dataDir, id + ext))` for every id on a case-sensitive filesystem. If the two sides disagree, normalize one side — prefer renaming the data files to match the identifier column, since the identifier column is typically referenced from multiple places and renaming data files has a smaller blast radius. "Preserve source casing" is **not** a safe default when a cross-file lookup exists.

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

## Common Pitfalls

- **Hedging adds surface area a literal grader rejects — pick one literal reading and stop.** Implementing both branches of a dichotomy (`<title>` AND `data-tooltip` AND `div.tooltip`; `"selected"` AND `"active"`; `click-sets-selection` AND `toggle-off`; `"N/A"` for silent subsets) multiplies the ways a strict evaluator can reject: `className === "selected"` fails on `"selected active"`; `cell.textContent === ""` fails on `"N/A"`; a class-persists assertion fails on toggle-off. Fix: Pass D picks the single simplest literal reading per `[GUESS]`; Pass E removes every feature the task does not literally name.
- **Bespoke layouts and non-standard dimensions when the task names only the chart type.** A `720×640` fixed viewBox with hand-picked cluster-center coordinates for each category is agent-invented structure, not a task requirement. Fix: use `d3.pack()` or plain `d3.forceSimulation` with only collision/many-body/center forces; use container-proportional dimensions (`viewBox` + CSS `width: 100%`); do not add per-category clustering forces unless the task text names grouping or clustering.
- **Tautological verification — the harness asserts the agent's own guesses.** Writing an EVALUATOR CONTRACT, deriving the harness from that contract, and asserting agent-chosen semantics (toggle-off on second click, dual-class application, cluster-tightness thresholds) means the harness confirms the code matches the agent, not the evaluator. Fix: tag every item `[LITERAL]`/`[GUESS]`; scan parents for an oracle; and in the harness, assert only behaviours the task text literally names — do not dispatch a second click if the task is silent on second-click behaviour; do not assert internal metrics the agent chose.
- **An input is copied but never consumed.** A directory or file named in the task appears in the deliverable solely as a copy step. Fix: Pass A — list every named input and bind each to a downstream use; add a verification assertion per input.
- **Cross-file lookup fails on case-sensitive filesystem.** Identifier casing in one artifact (e.g., ticker column `SPY`) does not match filename casing in a sibling data directory (e.g., `spy.csv`). The same mechanism breaks any lookup across whitespace, punctuation, or encoding drift between artifacts. Fix: normalize one side so every identifier resolves; assert the lookup for every id before writing.
- **Table re-sorted, decorated, or placeholder-invented.** Calling `.sort()`, wrapping cells in `<span>`/`<div>`, or formatting missing values as `"—"` / `"N/A"` / `"-"` when the task is silent on the subset — all break strict evaluators. Fix: identity transformation — file order, plain text, empty cell when the task is silent and its example shows a non-empty format for the column; mirror the task's placeholder string only when it names one.
- **Tooltip suppressed on a subset the task said "lacks" some fields.** Removing mouse handlers or the carrier entirely for ETFs/indexes/etc. deletes a DOM feature the task expected on every mark. Fix: attach the same single carrier to every mark; omit missing fields from the text, do not label them `"N/A"` unless the task uses that string.
- **Invented wrapper DOM nesting.** Wrapping each mark in a `<g class="…-group">` and moving `data-*` identifiers onto the wrapper rather than the mark itself fails evaluators that query `circle[data-ticker]`. Fix: keep mark + label as flat siblings; put `data-*` on the mark.
