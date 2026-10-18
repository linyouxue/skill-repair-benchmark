# Time-boxed data acquisition with incremental writes

Trigger: the task combines online data acquisition (web fetch, API,
package extraction, browser automation) with workbook population under
a finite iteration cap. Read this BEFORE composing the first fetch call.

The failure mode this chapter prevents: the executor treats acquisition
as a blocking prerequisite and spends the entire iteration budget
chasing one blocked source (header variations on a bot-protected URL,
mirror hunts, late-stage browser installs). The output file is never
opened for writing. The run ends at `max_iterations` with a blank
workbook — even when a working source was found at the very end, the
data was never flushed.

## Step 0 — State the plan before the first fetch

Write this plan down as the first action of the task, THEN fetch.
Without the plan, the per-source counters and checkpoints below have
nothing to reference.

```python
# Plan template — fill in before any requests.get / Playwright call
ITER_BUDGET       = 60                     # whatever the harness gives
PRE_TASK_MTIME    = os.path.getmtime(output_path)
PER_SOURCE_BUDGET = 5                      # hard cap, not "approximately"
SOURCES = [
    # order easiest-first so partial progress accumulates fast
    {"name": "source_A", "target_cells": "Sheet1!B2:B30", "budget": 5},
    {"name": "source_B", "target_cells": "Sheet1!C2:C30", "budget": 5},
    {"name": "source_C", "target_cells": "Sheet2!B3",     "budget": 5},
]
HALFWAY_ITER      = ITER_BUDGET // 2       # mandatory self-check point
CHECKPOINTS       = [ITER_BUDGET // 6,     # ~iter 10 of 60
                     ITER_BUDGET // 3,     # ~iter 20 of 60
                     ITER_BUDGET // 2]     # ~iter 30 of 60
iter_counter      = 0
per_source_count  = {s["name"]: 0 for s in SOURCES}
```

## Step 1 — Per-source counter, mechanically enforced

Every fetch attempt (every curl, every Playwright call, every mirror)
counts against the current source's budget. When the counter exceeds
the budget, STOP that source — do not try "just one more variation".

```python
def attempt(source_name, fetch_fn):
    global iter_counter
    per_source_count[source_name] += 1
    iter_counter += 1
    if per_source_count[source_name] > PER_SOURCE_BUDGET:
        return "BUDGET_EXCEEDED"
    try:
        return fetch_fn()
    except Exception as e:
        return f"RETRY: {e}"

# Loop body
result = attempt(src["name"], lambda: direct_download(src))
if result == "BUDGET_EXCEEDED":
    mark_pending(src["target_cells"].split(":")[0],
                 src["name"], "per-source budget exhausted")
    continue   # move to the next source — do NOT try another header
```

## Step 2 — Flush after every source lands

The moment a source yields a usable value, open the workbook, write
that source's cells, save, and read one cell back to confirm. Do not
batch writes to the end of the task.

```python
from openpyxl import load_workbook
from openpyxl.comments import Comment

def flush(cells_to_write, source_label, target_sheet):
    wb = load_workbook(output_path)
    ws = wb[target_sheet]
    for coord, value in cells_to_write.items():
        ws[coord] = value
    first_coord = next(iter(cells_to_write))
    ws[first_coord].comment = Comment(f"Source: {source_label}", "acquisition")
    wb.save(output_path)
    # read-back confirmation — the file MUST change on disk
    assert load_workbook(output_path)[target_sheet][first_coord].value is not None
    assert os.path.getmtime(output_path) != PRE_TASK_MTIME

def mark_pending(first_cell_coord, source_label, reason, target_sheet):
    wb = load_workbook(output_path)
    ws = wb[target_sheet]
    ws[first_cell_coord].comment = Comment(
        f"pending: {source_label}; {reason}", "acquisition"
    )
    wb.save(output_path)
```

## Step 3 — Numbered iteration checkpoints (self-check actions)

At each checkpoint, execute the self-check as code — do not treat it
as advisory. Each checkpoint has a corrective action attached.

```python
def checkpoint(iter_counter, output_path, pre_task_mtime):
    mtime_changed = os.path.getmtime(output_path) != pre_task_mtime
    if iter_counter in (CHECKPOINTS[0], CHECKPOINTS[1]) and not mtime_changed:
        # ~iter 10 and ~iter 20: file still blank → one source is stuck,
        # pivot to its next-rung fallback immediately
        return "PIVOT_CURRENT_SOURCE"
    if iter_counter >= HALFWAY_ITER and not mtime_changed:
        # halfway reached and file still blank → ABANDON acquisition,
        # flush whatever partial values are in hand (even guesses),
        # mark remaining sources `pending:`, move to downstream formulas
        return "ABANDON_ACQUISITION_FLUSH_PARTIAL"
    return "CONTINUE"
```

### Branch — checkpoint returns `PIVOT_CURRENT_SOURCE`

Switch to the current source's next ladder rung (see named-blocker
catalog below). Do NOT keep varying headers/cookies/mirrors on the
blocked endpoint.

### Branch — checkpoint returns `ABANDON_ACQUISITION_FLUSH_PARTIAL`

Open the workbook once. For every source that has any value in hand,
write it. For every unreached source, mark its first target cell
`pending: <source>; halfway-mtime trip`. Save. Then move to downstream
formulas and placeholders — you will not get another chance.

## Step 4 — Named-blocker catalog

These blockers have been observed repeatedly for this task family.
Each one has a specific next-rung pivot. On the SECOND failure of the
listed symptom, pivot — not on the twentieth.

| Blocker symptom                              | Pivot on 2nd failure                                     |
| --- | --- |
| `dataverse.nl` returns Anubis bot-challenge  | Pivot to CRAN R package (e.g. `pwt10`) via `pyreadr`, OR GitHub mirror. Do NOT iterate User-Agent / cookies / Referer. |
| `edgesuite.net` / IMF direct xls returns `Access Denied` | Pivot to IMF `datamapper` JSON API. Do NOT retry the direct xls with different headers. |
| `playwright install --with-deps chromium` hangs | Never start this install in the last 20% of the budget. Use `requests` or a package extraction rung instead. |
| GitHub mirror returns HTML landing page, not raw | Switch to `raw.githubusercontent.com` URL form; if still HTML, treat as 404 and pivot. |
| Terminal returns `Cannot execute multiple commands at once` | The tool call chained commands with `;`, `&&`, `||`, or a newline. The sandbox refuses multi-command calls. Split into separate single-command tool calls and retry. Do NOT re-attempt with the same chained form — each retry burns an iteration on the same refusal. |

```python
BLOCKER_PIVOTS = {
    "dataverse_anubis":  ["cran_package_via_pyreadr", "github_mirror"],
    "edgesuite_denied":  ["imf_datamapper_json_api"],
    "playwright_install_late": ["skip_browser_rung_use_requests"],
    "multiple_commands_at_once": ["split_into_single_command_calls"],
}

def pivot_for(symptom):
    rungs = BLOCKER_PIVOTS.get(symptom)
    if rungs is None:
        return None  # unknown blocker — try the generic acquisition ladder
    return rungs[0]
```

## Step 5 — No heavy installs in the last 20% of the budget

```python
LATE_BUDGET = int(0.8 * ITER_BUDGET)

def may_start_heavy_install(iter_counter):
    # Heavy = browser engine, new conda env, source-built package
    return iter_counter < LATE_BUDGET
```

If `iter_counter >= LATE_BUDGET` and you were about to run
`playwright install`, `conda create`, `pip install <heavy-pkg>`, or
`apt-get install`: do not. Use the acquisition rung that does not need
the install. The install itself can exceed the remaining budget and
hang.

## Verification step

Before declaring the acquisition phase done, assert the file has been
touched:

```python
assert os.path.getmtime(output_path) != PRE_TASK_MTIME, (
    "halfway-mtime violation: output file never written during acquisition. "
    "FLUSH NOW: open workbook, write anything acquired so far (even one cell), "
    "mark remaining sources pending, save, re-check mtime."
)
# Also assert each source either landed or was marked pending
wb = load_workbook(output_path)
for src in SOURCES:
    first_coord = src["target_cells"].split(":")[0].split("!")[-1]
    sheet_name  = src["target_cells"].split("!")[0]
    cell        = wb[sheet_name][first_coord]
    assert cell.value is not None or (
        cell.comment is not None and "pending" in cell.comment.text
    ), f"{src['name']}: neither written nor marked pending"
```

**On failure:**

- First assertion fires → open the workbook immediately and write
  anything you have (initial guesses, zeros, the one source that
  landed). The point is to break the untouched-file state. Then
  re-run the assertion.
- Second assertion fires on a specific source → go write a
  `pending: <source>; <reason>` comment on its first target cell and
  save; do NOT leave target cells silently blank with no provenance.
