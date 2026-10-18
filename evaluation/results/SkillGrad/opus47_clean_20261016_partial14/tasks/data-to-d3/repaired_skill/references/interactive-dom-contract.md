# Interactive DOM patterns under a strict evaluator

Read this chapter when the task names a specific tooltip selector verbatim (`[data-tooltip]`, `title`, `aria-label`), when only some marks should be interactive, or when the task text explicitly names second-click behaviour (toggle-off, idempotent, move). Skip when the task describes only "click X highlights Y" with no further interactive detail — the SKILL.md defaults (single `<title>` carrier or single `div.tooltip` per task wording; `click-sets-selection` with no second-click branch; single `"selected"` class) are the minimal literal reading and need no refinement.

The chapter covers: (A) choosing a single tooltip carrier from a literal task cue, (B) conditional interactivity (some marks interactive, others not), (C) linked-selection with the specific second-click behaviour the task names, each with an observable-behaviour verification snippet.

Prior rounds hedged these decisions (dual carriers, dual classes, toggle-off default) and the hedges themselves were rejected by a strict literal grader. The patterns below each implement **one** reading, chosen from a literal task cue.

---

## A. Choose a single tooltip carrier from a literal task cue

When Pass C upgraded the carrier to `[LITERAL]` because the task text names a specific selector, bind that carrier only — a stray extra carrier is itself a surface a strict evaluator can reject.

```javascript
// Decide once from a literal task cue
function chooseTooltipCarrier(taskText) {
    const t = taskText.toLowerCase();
    if (t.includes('data-tooltip'))                       return 'data-tooltip';
    if (t.includes('aria-label') || t.includes('accessib'))return 'aria-label';
    if (t.includes('<title>') || t.includes('title element')) return 'title-child';
    if (/\bhover\b.*\b(show|display|appear)/.test(t))     return 'div.tooltip';
    return 'title-child';   // silent-task default: minimal, DOM-queryable, no visible UI
}

function attachLiteralTooltip(selection, carrier, textFn) {
    switch (carrier) {
        case 'title-child':  selection.append('title').text(textFn); break;
        case 'data-tooltip': selection.attr('data-tooltip', textFn);  break;
        case 'aria-label':   selection.attr('aria-label', textFn);    break;
        case 'div.tooltip': {
            const tipDiv = d3.select('body').append('div')
                .attr('class', 'tooltip')
                .style('position', 'absolute').style('opacity', 0)
                .style('pointer-events', 'none');
            selection
                .on('mouseover', (e, d) => tipDiv.style('opacity', 1).text(textFn(d)))
                .on('mousemove', (e)    => tipDiv.style('left', (e.pageX + 12) + 'px')
                                                 .style('top',  (e.pageY + 12) + 'px'))
                .on('mouseout',  ()     => tipDiv.style('opacity', 0));
            break;
        }
    }
    // Do NOT also attach a second carrier as a defensive hedge.
}
```

**Verification:**

```javascript
const marks = doc.querySelectorAll('circle, rect.bar, path.area');
const probe = (m) =>
    (CARRIER === 'title-child'  && m.querySelector('title')) ||
    (CARRIER === 'data-tooltip' && m.hasAttribute('data-tooltip')) ||
    (CARRIER === 'aria-label'   && m.hasAttribute('aria-label')) ||
    (CARRIER === 'div.tooltip'  && /* dispatch mouseover then check tipDiv */ true);
const covered = Array.from(marks).filter(probe).length;
console.assert(covered === marks.length,
    `LITERAL TOOLTIP COVERAGE: ${covered}/${marks.length} marks carry ${CARRIER}`);
// Also assert no stray second carrier is present
if (CARRIER !== 'title-child') {
    console.assert(doc.querySelectorAll('circle > title').length === 0,
        `STRAY CARRIER: <title> children present despite CARRIER=${CARRIER}`);
}
```

**On failure:**

- **COVERAGE < marks.length** — the carrier was bound to a filtered subset or a shared overlay. Rebind over the full selection.
- **STRAY CARRIER present** — a defensive hedge (`<title>` + `data-tooltip` wired together) is still in the code. Remove the extra `.append('title')` or `.attr('data-tooltip', ...)`. The hedge is the failure mode, not the fix.

---

## B. Conditional interactivity

When the task says "tooltips for stocks but not ETFs" (or similar explicit exclusion), filter the selection — do NOT branch inside the handler and return early. Branching inside the handler leaves the mark looking interactive while silently refusing to render content.

```javascript
const marks = svg.selectAll('circle').data(nodes).join('circle');

// Attach the carrier only to the subset that should be interactive
marks.filter(d => d.category !== 'excluded')
     .append('title')
     .text(d => `${d.name}: ${d.value}`);

// Mark the non-interactive ones so CSS can suppress hover styling
marks.filter(d => d.category === 'excluded')
     .classed('no-tooltip', true);
```

**Verification:**

```javascript
const interactiveMarks  = doc.querySelectorAll('circle:not(.no-tooltip)');
const titledInteractive = Array.from(interactiveMarks)
    .filter(m => m.querySelector('title'));
console.assert(titledInteractive.length === interactiveMarks.length,
    `CONDITIONAL TOOLTIP: ${titledInteractive.length}/${interactiveMarks.length} interactive marks titled`);

const excluded = doc.querySelectorAll('circle.no-tooltip title');
console.assert(excluded.length === 0,
    `EXCLUSION LEAK: ${excluded.length} excluded marks still carry a title child`);
```

**On failure:** both counts can fail — if interactive marks miss their title, your filter inverted (interactive branch did not get `.append('title')`); if excluded marks have titles, you appended before filtering.

**Important distinction:** when the task says a subset "lacks" certain fields (rather than "is not interactive"), the subset is **still interactive** — attach the same single carrier chosen for the rest and omit the missing fields from the text. Only remove the carrier when the task text explicitly says the subset should have no tooltip. Suppressing the tooltip entirely on a "lacks fields" subset deletes a DOM feature the grader expects on every mark.

---

## C. Linked selection — click-sets-selection (default) or the specific second-click behaviour the task names

The default when the task names only "clicking a bubble highlights the matching row" is `click-sets-selection` with **no second-click branch**. Only implement a second-click branch when the task text explicitly names it.

### C.1 Default — click-sets-selection, no second-click branch

```javascript
const KEY = 'ticker';                           // from task's identifier field
const SELECTED_CLASS = TASK_CLASS || 'selected'; // single class

function select(key) {
    d3.selectAll('[data-key]').classed(SELECTED_CLASS, false);
    if (key != null) d3.selectAll(`[data-key="${key}"]`).classed(SELECTED_CLASS, true);
}

svg.selectAll('circle').attr('data-key', d => d[KEY]).on('click', (_, d) => select(d[KEY]));
d3.selectAll('tbody tr').attr('data-key', d => d[KEY]).on('click', (_, d) => select(d[KEY]));
```

**Verification — observable behaviour, constrained to literally-named behaviours:**

```javascript
const sampleKey = doc.querySelector('circle').getAttribute('data-key');
const click = (sel) => sel.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));

// First click: both sides carry the single class
click(doc.querySelector(`circle[data-key="${sampleKey}"]`));
const marks = doc.querySelectorAll(`circle.${SELECTED_CLASS}`);
const rows  = doc.querySelectorAll(`tbody tr.${SELECTED_CLASS}`);
console.assert(marks.length === 1 && rows.length === 1,
    `FIRST CLICK: ${marks.length} marks + ${rows.length} rows (expected 1 each)`);

// Do NOT dispatch a second click here. The task is silent on second-click
// behaviour; asserting any specific second-click outcome encodes an agent
// guess as a test and produces false confidence.
```

### C.2 Task explicitly names a second-click behaviour

Only reach this branch when the task text contains an unambiguous cue: *"clicking again clears"*, *"toggles"*, *"deselects on second click"*, *"persists until another is clicked"* (idempotent), or similar. Implement exactly the behaviour named.

```javascript
// Example: task says "clicking again clears the selection" — toggle-off
function selectToggle(key) {
    const alreadyAll = key && d3.selectAll(`[data-key="${key}"]`).nodes()
        .every(n => n.classList.contains(SELECTED_CLASS));
    d3.selectAll('[data-key]').classed(SELECTED_CLASS, false);
    if (key && !alreadyAll) d3.selectAll(`[data-key="${key}"]`).classed(SELECTED_CLASS, true);
}
```

**Verification (only when the task names second-click behaviour):**

```javascript
click(doc.querySelector(`circle[data-key="${sampleKey}"]`));  // first click
click(doc.querySelector(`circle[data-key="${sampleKey}"]`));  // second click
const stillSelected = doc.querySelectorAll(`circle.${SELECTED_CLASS}`).length;
console.assert(stillSelected === 0,
    `SECOND CLICK CLEARS (task-named): expected 0 selected marks, got ${stillSelected}`);
```

**On failure:**

- **FIRST CLICK count ≠ 1** → the two `.on('click', …)` handlers are not calling the same `select(key)` function, or the `data-key` attribute is missing on one side. Confirm both selections carry `data-key` from the same field, and that `SELECTED_CLASS` is a single string (not an array of classes applied together).
- **SECOND CLICK outcome wrong (when task names it)** → the `alreadyAll` check reads classes after the clear step rather than before. Reorder: compute `alreadyAll`, then clear, then re-apply only when `!alreadyAll`.
- **PROBES PASS, GRADER STILL FAILS** → a feature the task did not literally name is still present. Common culprits: a second class alongside `SELECTED_CLASS`; a toggle-off branch when the task is silent on second clicks; a `data-tooltip` attribute alongside `<title>`. Re-run Pass E (minimality audit) and remove — do not add another hedge.
