# Consistency checks and reconciliation (prevent assembly drift)

Use this when you compute candidate/qualifying sets during exploration and need to ensure the final written artifact matches the intended definition.

## Procedure

1. **Write down the definition you will score against** (one sentence): what counts as a match, and what evidence is required.
2. **Build a `qualifying` set from evidence**, keeping a pointer for each item (artifact ID + location/snippet).
3. **Build the `to_write` set from your final serialization logic** (what will actually be rendered).
4. **Diff and branch**: if the diff is non-empty, you must either (a) broaden/narrow the logic to match the definition, or (b) state an explicit exclusion rule and apply it consistently.
5. **Verify pointers**: every written item has at least one pointer; otherwise drop it or go find evidence.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Pointer:
    artifact_id: str
    where: str  # e.g., "message_ts=...", "turn=...", "section=..."


def reconcile_sets(qualifying: set, to_write: set):
    missing = sorted(qualifying - to_write)
    extra = sorted(to_write - qualifying)
    return missing, extra


def verify_pointers(to_write, pointers_by_item: dict):
    no_ptr = [x for x in to_write if not pointers_by_item.get(x)]
    return no_ptr
```

## Runtime branch

- **Branch A — missing items (`qualifying - to_write` non-empty):**
  - Action: inspect the missing items; identify which filter/requirement dropped them; remove/relax any requirement not stated in the question; then regenerate `to_write` from the updated logic.
- **Branch B — extra items (`to_write - qualifying` non-empty):**
  - Action: either add evidence pointers (if they actually qualify) or tighten the qualifying definition/logic; do not leave unsupported extras.
- **Branch C — no pointers for written items:**
  - Action: for each item lacking a pointer, search for at least one supporting snippet tied via the correct linking key; if none exists, remove the item.

## Verification (with corrective next step)

After applying the chosen branch actions, re-run the diff until both are true:
- `missing == []` and `extra == []`
- `verify_pointers(to_write, pointers_by_item) == []`

If either check still fails, **do not write the final artifact**. Go back to step (2) and rebuild `qualifying` from the evidence with a clearer definition (avoid narrow token gates), then repeat reconciliation.
