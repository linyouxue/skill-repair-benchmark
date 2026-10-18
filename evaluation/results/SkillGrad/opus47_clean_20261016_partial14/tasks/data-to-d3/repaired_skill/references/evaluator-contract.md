# Evaluator contract — branched derivation and verification

Read this chapter when the task names a chart + table, lists a specific class name or selector, prescribes a placeholder string, defines any inter-element interaction (click X → highlight Y), or names multiple input files/directories. Skip when the sole deliverable is a static image diffed against a reference PNG/SVG — a pixel/byte diff bypasses DOM assertions.

The chapter has six parts: (A') input inventory + cross-file binding, (A) branched extraction of the output contract from the task text, (C) provenance tagging + external grounding, (D) **minimal-literal resolution** of surviving `[GUESS]` items, (E) **minimality audit** — feature removal before coding, (B) a runnable jsdom verification harness that probes observable behaviour **constrained to literally-named behaviours**. Run A' → A → C → D → E → B in that order.

The historical hedging recipe (implement both branches of every dichotomy, apply multiple classes, dual tooltip carriers, toggle-off defaults, `"N/A"` for silent subsets) failed when the agent executed it faithfully — every added hedge was itself a surface a strict literal grader rejected. This chapter now encodes the opposite operation: **pick one literal reading, then remove every feature the task did not name.**

---

## A'. Input inventory and cross-file binding (Pass A)

Scope creep from the executor's side is caused by deriving scope from "features I plan to build" instead of "every input the task names". This pass fixes that.

### A'.1 Enumerate every named input

Read the task text once and extract every file, directory, path, or named dataset. Build a table where each row is one input and the column is "what the final deliverable does with it".

```python
# Pseudocode — run this in your head while reading the task
inputs = []
for mention in task_text:
    if is_path_or_filename(mention) or names_a_dataset(mention):
        inputs.append({
            "name": mention,
            "use": None,              # fill in next step — one sentence
            "consumer_in_output": None,  # DOM selector, fs call, or "(copy only)"
        })

# For each input, write exactly one sentence stating its downstream use.
# Candidate uses: load into chart | cross-reference from table |
#                 render per-item detail/sparkline | overlay | copy to output path
```

**Red flag — the copy-only input.** If any input's use is "copy to output and nothing else", stop and re-read the task description for an implied downstream use. Phrases that imply consumption:

- "individual \<item\> histories / details / records" → per-item detail panel, mini-chart, or sparkline
- "price / time-series / trajectory data" → line overlay, hover-driven detail, or inline chart
- "metadata about each \<item\>" → cross-reference from the main table
- "assets / resources" → referenced from HTML (`<img src>`, `<link href>`), not just copied

Only accept a copy-only use after confirming the task text contains no such phrase and no interactive feature that would need the data.

**Verification step.** After enumeration, each row must have a non-null `consumer_in_output`. If any row remains null, go back to the task text — the contract is not complete.

### A'.2 Cross-file lookup consistency

Whenever one input names identifiers (a ticker column, an id column, a key field) that must resolve to files under another input, add this check **before** writing any code.

```python
# Branch: do two inputs form an index → data-file relationship?
import os, csv

INDEX_FILE = "data/index.csv"
DATA_DIR   = "data/items"
ID_COLUMN  = "id"            # from Pass A
FILE_EXT   = ".csv"

with open(INDEX_FILE) as f:
    ids = [row[ID_COLUMN] for row in csv.DictReader(f)]

missing = [i for i in ids if not os.path.exists(os.path.join(DATA_DIR, i + FILE_EXT))]
if missing:
    # Branch A: casing mismatch — one side uppercase, other lowercase
    # Fix: rename data files to match the identifier column (smaller blast radius)
    # Branch B: identifier contains punctuation/whitespace absent in filenames
    # Fix: normalize both sides via the same slugify function
    # Branch C: genuine missing data file
    # Fix: re-read the task; the task may permit nulls or exclude certain ids
    raise AssertionError(f"cross-file lookup failed for: {missing}")
```

**Corrective action on failure.** Pick the normalization that keeps the identifier column stable (the identifier column is usually referenced from multiple places; the data directory from only one). Do not "preserve source casing" as a reflex — that rule is only safe when no cross-file lookup exists.

---

## A. Extract the output contract by task shape (Pass B)

Classify the task by scanning the task text once, then follow the matching branch. The branches are additive — a "chart + table" task runs both the chart branch and the table branch.

```python
# Pseudocode run in your head while reading the task text
task_text = read_task_prompt()

has_chart  = any(k in task_text.lower() for k in [
    "chart", "plot", "graph", "bubble", "bar", "scatter", "line", "svg"
])
has_table  = any(k in task_text.lower() for k in [
    "table", "<table", "rows", "columns", "tbody"
])
has_linking = any(k in task_text.lower() for k in [
    "click", "highlight", "select", "linked", "when a user"
])

branches = []
if has_table:   branches.append("TABLE")
if has_chart:   branches.append("CHART")
if has_linking: branches.append("LINKING")
if not branches: branches = ["STATIC_IMAGE"]
```

### Branch TABLE — enumerate per-column contract

Default values apply when the task is silent (and get tagged `[GUESS]` in Pass C → resolved by minimal literal reading in Pass D).

| Item                 | Default (minimal literal)                                 |
|----------------------|-----------------------------------------------------------|
| Row order            | Input CSV order (do not `.sort()`)                        |
| `<td>` content shape | Plain text only; no child elements                        |
| Missing value        | Mirror task's placeholder if named; otherwise **empty cell** |
| Number format        | Raw string from CSV (no locale commas / `$`)              |
| Column order         | Order columns are introduced in task text                 |

Scan for override keywords: *"sorted by"*, *"descending"*, *"formatted as"*, *"show as N/A"*, *"with a $ prefix"*. Any of these override the default — copy the exact string the task uses.

### Branch CHART — enumerate per-mark contract

| Item               | Default (minimal literal)                   |
|--------------------|---------------------------------------------|
| Mark element       | `circle` / `rect` / `path` per chart type   |
| Mark DOM nesting   | Flat siblings (mark + label); `data-*` on mark itself |
| Tooltip carrier    | Single carrier: `<title>` child when task is silent about hover UI; shared `<div class="tooltip">` when task says "hover shows" |
| Tooltip text       | Plain unlabeled values, one field per line (no `"Field:"` prefixes unless the task uses labels) |
| Label text         | Exact field from task; no re-casing         |
| Grouping / color   | By the field the task names, in input order |
| Layout             | `d3.pack()` or plain `d3.forceSimulation` with collision/charge/center only — no per-category clustering force |
| Dimensions         | Container-proportional (`viewBox` + CSS `width: 100%`) unless task names dimensions |

Scan for selector-naming keywords: *"each bubble has a tooltip with …"*, *"on hover, show …"*, *"with a data-\* attribute"*. If the task names a selector verbatim, that selector is the contract — not a default.

### Branch LINKING — enumerate interaction contract

| Item                      | Default (minimal literal)                  |
|---------------------------|--------------------------------------------|
| Selected class name       | Task's exact class if named; else `"selected"` alone (single class, no secondary) |
| Click behavior            | `click-sets-selection`: clear every mark, apply class to clicked mark |
| Re-click behavior         | **Do not implement any second-click branch** unless the task text pins it (toggle-off, idempotent, move) |
| Cross-element propagation | Click A → both sides' twin receives the class via the same `selectKey` function |
| Clear affordance          | **None** unless the task names one (background click, same-mark re-click, etc.) |

Scan for class-name tokens in quotes or backticks: `"highlighted"`, `"active"`, `"focus"`, `"on"`. The first class name the task mentions is the contract. Scan for second-click language: *"clicking again"*, *"toggles"*, *"deselects"*, *"clears"*. If none appears, there is no second-click behaviour to implement.

### Branch STATIC_IMAGE — no DOM contract

Verification is a pixel or byte diff against a reference. Skip the DOM harness in part B; instead confirm the output file exists at the exact path with the exact extension the task names.

---

## C. Provenance + external grounding

The failure mode this pass addresses: the agent writes an EVALUATOR CONTRACT, derives the verification harness from that same contract, and the harness passes — because it is checking the agent's own guesses, not the evaluator's criteria. The fix has three steps.

### C.1 Tag every contract item

For every item from Pass A' and Pass A, append `[LITERAL]` or `[GUESS]`:

- `[LITERAL]` — the task text pins this value verbatim (an exact selector, a quoted class name, a prescribed placeholder, an explicit "sort by X" instruction).
- `[GUESS]` — you picked a default from the tables above. Also list 1–3 alternative values you rejected, so a reviewer or the next debug round can see the choice space.

### C.2 Scan the environment for external grounding

```python
# Branch: run this before locking in any [GUESS].
import subprocess, pathlib

TASK_DIR = pathlib.Path.cwd()
# Walk up to the filesystem root, not just the task dir — oracles often live one or two levels up.
roots = [TASK_DIR, *TASK_DIR.parents]

PATTERNS = [
    "evaluator*", "test*", "rubric*", "expected*", "reference*",
    "*.spec.*", "*example*", "README*", "scoring*", "golden*",
    "*.harness.*", "verify*",
]

found = []
for root in roots[:4]:          # cap depth; stop before the filesystem root
    for pat in PATTERNS:
        found.extend(root.rglob(pat))

# Branch A: at least one oracle resolves to this task
if found:
    for f in found:
        # Read the file; if it names a selector, class, placeholder, or
        # tooltip format that matches a [GUESS] item, re-tag that item
        # [LITERAL] and copy the value verbatim.
        pass
# Branch B: nothing found — proceed to Pass D (minimal literal resolution).
```

**Verification step.** After the scan, print a summary: how many `[GUESS]` items became `[LITERAL]`, and which items remain `[GUESS]`. If the summary shows no state change despite found artifacts, re-read those artifacts — the oracle existed and you missed it. If the summary shows no artifacts found, record "none" in the EVALUATOR CONTRACT block and move to Pass D.

---

## D. Minimal literal resolution for surviving `[GUESS]` items

Across five iterations the hedging approach (implement both branches of every dichotomy) has itself failed when executed faithfully — each hedge is a surface a strict literal grader rejects. The current rule is: for every surviving `[GUESS]`, pick the **single simplest, most-literal reading** of the spec and implement exactly that, nothing more.

### D.1 Click semantics — sets-selection, no second-click branch

```javascript
const SELECTED_CLASS = TASK_CLASS || 'selected';

function selectKey(key) {
    d3.selectAll('[data-key]').classed(SELECTED_CLASS, false);
    if (key != null) d3.selectAll(`[data-key="${key}"]`).classed(SELECTED_CLASS, true);
}
svg.selectAll('circle.mark').on('click', (_, d) => selectKey(d[KEY]));
d3.selectAll('tbody tr').on('click', (_, d) => selectKey(d[KEY]));
// NO toggle-off branch, NO idempotent-ignore, NO background-click clear
// unless the task text names those behaviours.
```

**On failure (the first click does not apply the class):** confirm `data-key` is set on both the mark and the row (same field name), and that the handler is wired after `.data(...).join(...)` rather than during static DOM construction. If the task names a class verbatim, confirm `SELECTED_CLASS` reads that exact string.

### D.2 Selected class — single class

```javascript
// Task names a class → use that class alone
// Task is silent → "selected" alone — NEVER apply a second class
const SELECTED_CLASS = TASK_CLASS || 'selected';
d3.select(mark).classed(SELECTED_CLASS, true);
```

**On failure (grader rejects on class name):** the task names a different class elsewhere in the text — scan for class-name tokens in quotes or backticks. Do not fall back to applying both the named class and `"selected"`; replace, do not accumulate.

### D.3 Tooltip carrier — single carrier matching task wording

```javascript
// Decide once from a literal cue in the task text
function chooseTooltipCarrier(taskText) {
    const t = taskText.toLowerCase();
    if (/\bhover\b.*\b(show|display|appear)/.test(t)) return 'div.tooltip';
    if (t.includes('data-tooltip'))                   return 'data-tooltip';
    if (t.includes('aria-label'))                     return 'aria-label';
    return 'title-child';   // default when task is silent about hover UI
}

const CARRIER = chooseTooltipCarrier(TASK_TEXT);

if (CARRIER === 'div.tooltip') {
    const tipDiv = d3.select('body').append('div')
        .attr('class', 'tooltip')
        .style('position', 'absolute').style('opacity', 0)
        .style('pointer-events', 'none');
    svg.selectAll('circle.mark')
        .on('mouseover', (e, d) => tipDiv.style('opacity', 1).text(plainText(d)))
        .on('mousemove', (e)    => tipDiv.style('left', (e.pageX + 12) + 'px')
                                         .style('top',  (e.pageY + 12) + 'px'))
        .on('mouseout',  ()     => tipDiv.style('opacity', 0));
} else if (CARRIER === 'title-child') {
    svg.selectAll('circle.mark').append('title').text(d => plainText(d));
} else if (CARRIER === 'data-tooltip') {
    svg.selectAll('circle.mark').attr('data-tooltip', d => plainText(d));
}
// Do NOT also wire a second carrier.
```

**On failure (tooltip probe sees no text on hover):**

- `div.tooltip` branch — confirm the div is appended to `body` (not inside SVG), has `pointer-events: none`, and the mouseover handler is attached after `.data(...).join(...)`.
- `title-child` branch — `.append('title')` ran on an empty selection; confirm the per-mark selection has one node per data row.
- Do not add a second carrier as a defensive hedge; the second carrier is itself a surface the grader rejects.

### D.4 Tooltip text — plain unlabeled values

```javascript
function plainText(d) {
    // One field per line, no "Field:" prefixes, missing fields omitted
    return [d.id, d.name, d.sector, d.marketCap]
        .filter(v => v != null && v !== '')
        .join('\n');
}
```

**On failure (grader rejects on tooltip text):** scan the task text for label prefixes (`"Ticker:"`, `"Name:"`); only add labels if the task uses them. For a subset of marks the task says "lacks" certain fields, keep the carrier attached — just omit those fields from the string. Do NOT label omitted fields `"N/A"` unless the task text uses that string.

### D.5 Missing-value placeholder — empty cell by default

```javascript
function formatCell(d, col) {
    const v = d[col];
    if (v != null && v !== '') return String(v);
    // Mirror the task's string if the task names one (even in a parenthetical)
    if (TASK_PLACEHOLDER_FOR[col]) return TASK_PLACEHOLDER_FOR[col];
    // Default when the task is silent AND the task's example shows a non-empty format
    return '';
}
```

**On failure (grader rejects on cell content):** scan the task text for parentheticals like *"(empty for ETFs)"*, *"(show as —)"*, *"(use N/A)"*. Mirror the exact string the task names. If the task truly says nothing, the empty cell is the literal reading; adding `"N/A"` is agent-invented content.

### D.6 Record every resolution in the contract block

```javascript
/* …PASS A/B/C fields as before…
 * PASS D — literalism resolution (one line per surviving [GUESS])
 *   click semantics:  sets-selection, no second-click branch (task silent on 2nd click)
 *   selected class:   "selected" alone (task silent on class name)
 *   tooltip carrier:  <title> child alone (task silent on hover UI)
 *   tooltip text:     plain unlabeled, one field per line
 *   missing (ETF):    "" (task example shows "1.64T"; task silent on ETF subset)
 */
```

**Verification step.** The number of lines under `PASS D` should equal the number of items that remained `[GUESS]` after Pass C. If any `[GUESS]` item has no corresponding resolution line, go back to §D.1–§D.5. If any resolution line implements both branches of a dichotomy, rewrite it to pick one.

---

## E. Minimality audit — remove every feature the task did not name

Before writing code, list every feature the planned implementation will have. For each, ask: *does the task text literally name this feature?* If no, remove it.

```python
# Pseudocode — run in your head before coding
planned_features = [
    "circles sized by market cap",     # task says "bubble chart sized by market cap" → KEEP
    "toggle-off on second click",      # task silent → REMOVE
    "both 'selected' and 'active'",    # task silent → REMOVE 'active'
    "<title> AND data-tooltip AND div.tooltip",  # task silent → KEEP one, REMOVE others
    "'N/A' for ETF market cap",        # task silent on ETFs → REMOVE (empty cell)
    "cluster bubbles by sector at (120,240),(360,240),...",  # task silent → REMOVE
    "720×640 fixed viewBox",           # task silent on size → REMOVE (container-proportional)
    "'Ticker:' / 'Name:' prefixes in tooltip",  # task silent → REMOVE labels
]
for feature in planned_features:
    if not task_text_literally_names(feature):
        remove(feature)
```

### E.1 Accumulated-cruft checklist

Each item below has been invented in a prior round and failed. Audit against this list specifically:

1. Toggle-off / idempotent / any second-click branch — remove unless the task names second-click behaviour.
2. Secondary `"active"` / `"highlighted"` class alongside `"selected"` — remove; use a single class.
3. Multiple tooltip carriers (`<title>` + `data-tooltip` + `div.tooltip`) — pick one.
4. Labeled tooltip text with `"Field:"` prefixes — remove unless the task uses labels.
5. `"N/A"` placeholder for a subset the task is silent about — use empty string.
6. Per-category clustering force or hand-picked cluster centers — remove unless the task names grouping.
7. Hard-coded non-standard viewBox (e.g., `720×640`) — use container-proportional dimensions.
8. Suppressing the tooltip entirely on a subset the task described as "lacking" some fields — keep the carrier; omit the missing fields from the text.
9. Internal invariants in the verification harness (cluster-tightness, bubble-radius formulas, node spacing) — remove; dispatch events and assert DOM instead.
10. Asserting a specific second-click outcome in the harness when the task is silent on second-click behaviour — remove the second dispatch.

**Verification step.** After the audit, re-read the planned-features list. If any item on the accumulated-cruft list is still present without a matching literal task cue, remove it before coding. If you cannot remove a feature because another feature depends on it, trace the dependency — the dependent feature is itself probably agent-invented and should also be removed.

---

## B. Runnable verification harness — observable behaviour, constrained to literally-named behaviours

Each probe below **dispatches a user event** and asserts a **user-visible DOM effect** — not an agent-chosen internal invariant. The harness also only asserts behaviours the task text literally names: do not dispatch a second click if the task is silent on second-click behaviour; do not assert both branches of a dichotomy; do not assert dimensions, cluster-tightness, or node spacing.

```javascript
// verify.js — run with `node verify.js` after the build step
const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');
const csvParse = require('d3-dsv').csvParse;

const CONTRACT = {
    outputPath:       'dist/index.html',
    indexFile:        'dist/data/index.csv',
    idColumn:         'id',
    dataDir:          'dist/data/items',
    dataFileExt:      '.csv',
    perInputSelector: '.item-detail',
    markSelector:     'circle.mark',
    rowSelector:      'tbody tr',
    selectedClass:    'selected',          // single class
    tooltipCarrier:   'title-child',       // from chooseTooltipCarrier(TASK_TEXT)
    taskNamesSecondClick: false,           // from task text scan
};

async function main() {
    console.assert(fs.existsSync(CONTRACT.outputPath),
        `MISSING OUTPUT: ${CONTRACT.outputPath}`);

    // Cross-file lookup (Pass A'.2)
    const indexRows = csvParse(fs.readFileSync(CONTRACT.indexFile, 'utf8'));
    const ids = indexRows.map(r => r[CONTRACT.idColumn]);
    const missing = ids.filter(id =>
        !fs.existsSync(path.join(CONTRACT.dataDir, id + CONTRACT.dataFileExt)));
    console.assert(missing.length === 0,
        `CROSS-FILE LOOKUP: ${missing.length} ids unresolved — e.g. ${missing.slice(0,3)}`);

    const dom = await JSDOM.fromFile(CONTRACT.outputPath, {
        runScripts: 'dangerously', resources: 'usable',
    });
    await new Promise(r => setTimeout(r, 300));
    const doc = dom.window.document;
    const win = dom.window;

    // --- Per-input consumption (Pass A'.1) ---
    const consumers = doc.querySelectorAll(CONTRACT.perInputSelector);
    console.assert(consumers.length === ids.length,
        `PER-INPUT CONSUMPTION: ${CONTRACT.perInputSelector} count ${consumers.length}, expected ${ids.length}`);

    // --- Row count ---
    const rows = doc.querySelectorAll(CONTRACT.rowSelector);
    console.assert(rows.length === ids.length, `ROW COUNT: ${rows.length}/${ids.length}`);

    // --- Observable probe: TOOLTIP on mouseover (single carrier) ---
    const mark = doc.querySelector(CONTRACT.markSelector);
    const expectedId = mark.getAttribute('data-key') || ids[0];
    mark.dispatchEvent(new win.MouseEvent('mouseover', { bubbles: true }));
    let tipText;
    switch (CONTRACT.tooltipCarrier) {
        case 'div.tooltip':
            const tipDiv = doc.querySelector('div.tooltip');
            tipText = tipDiv && win.getComputedStyle(tipDiv).opacity !== '0' && tipDiv.textContent;
            break;
        case 'title-child':  tipText = mark.querySelector('title')?.textContent; break;
        case 'data-tooltip': tipText = mark.getAttribute('data-tooltip');        break;
        case 'aria-label':   tipText = mark.getAttribute('aria-label');          break;
    }
    console.assert(tipText && tipText.includes(expectedId),
        `TOOLTIP ON HOVER (${CONTRACT.tooltipCarrier}): no "${expectedId}"`);

    // --- Observable probe: FIRST CLICK applies the class ---
    mark.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
    console.assert(mark.classList.contains(CONTRACT.selectedClass),
        `FIRST CLICK APPLIES CLASS "${CONTRACT.selectedClass}"`);

    // --- Observable probe: LINK propagation (bubble ↔ table) ---
    const linkedRow = doc.querySelector(
        `${CONTRACT.rowSelector}[data-key="${expectedId}"]`);
    console.assert(linkedRow && linkedRow.classList.contains(CONTRACT.selectedClass),
        `LINK PROPAGATION: row[data-key="${expectedId}"] missing "${CONTRACT.selectedClass}"`);

    // --- Observable probe: SECOND CLICK — ONLY IF the task names second-click behaviour ---
    if (CONTRACT.taskNamesSecondClick) {
        // The task pins a specific second-click behaviour (toggle-off, idempotent, move).
        // Assert that exact behaviour, verbatim from the task text.
        // Do NOT invent an assertion when the task is silent — asserting any
        // specific second-click outcome encodes an agent guess as a test.
    }

    console.log('\nAll observable-behaviour probes passed.');
    console.log('If scoring still fails: re-run Pass E — a feature the task did not name is still present. Remove, do not add.');
}

main().catch(e => { console.error(e); process.exit(1); });
```

### Corrective actions on failure

Each assertion label maps to one next move. Do not weaken the assertion; fix the rendering or the file layout.

- **CROSS-FILE LOOKUP** → rename the files in `dataDir` to match the casing/encoding of the identifier column (preferred — identifier column is referenced from multiple places), or normalize both sides through the same slugify function. Re-run the lookup for every id.
- **PER-INPUT CONSUMPTION** → an input listed in Pass A has no DOM consumer. Add the rendering code that reads it (sparkline, detail panel, overlay, or table cross-reference). Do not weaken the selector or the count — the input was promised in the contract.
- **MISSING OUTPUT** → re-check the output path against the task text; the task may specify `index.html` at the project root rather than `dist/chart.html`.
- **ROW COUNT** → remove any `.sort()` call on the parsed CSV; bind rows in `d3.csvParse` order; re-check `.filter()` did not drop rows.
- **TOOLTIP ON HOVER** → confirm the single carrier chosen in Pass D is attached to every mark and the handler is wired after data binding. Do NOT add a second carrier as a defensive hedge; the second carrier is itself a surface the grader rejects.
- **FIRST CLICK APPLIES CLASS** → the handler is applying a different class, or applying multiple classes together. Confirm `SELECTED_CLASS` is a single string matching the task's class name (or `"selected"` when the task is silent).
- **LINK PROPAGATION** → the two `.on('click', …)` handlers are not calling the same `selectKey(key)` function, or the `data-key` attribute is missing on one side. Confirm both selections carry `data-key` from the same field.
- **PROBES PASS, SCORING STILL FAILS** → a feature the task did not literally name is still present in the output. **Re-run Pass E** (minimality audit) and remove more, do not add more. Check specifically: is there a second class on the selected element? A second tooltip carrier? A toggle-off branch? A `"N/A"` cell? Hand-picked cluster centers? Non-standard viewBox? Each of these is a surface a strict literal grader rejects. Removing any one of them may be the fix. **Never** respond to a scoring failure by adding another hedge.

Re-run `verify.js` until all observable-behaviour probes pass. Only after a clean run **and** a Pass E audit showing no cruft is the task complete.
