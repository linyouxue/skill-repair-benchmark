---
description: Handle terminal targets like End by following dialogue_graph’s conventions; do not fabricate placeholder nodes for missing targets except when the library explicitly requires a terminal node.
---

# Terminal conventions and missing targets

## Trigger

Use this when:
- edges point to `End`/`END`/`end` (or another special terminal), or
- validation reports missing targets.

## Procedure

1. **Recognize terminals by convention** (as defined by the task/library).
2. **Do not create placeholder nodes** for missing non-terminal targets.
3. **Defer to `Graph.validate()`** to decide whether a terminal must be explicit.

```python
from dialogue_graph import Graph, Node

TERMINAL_IDS = {"End", "END", "end"}

def is_terminal(tgt: str) -> bool:
    return tgt in TERMINAL_IDS

# After building g:
errors = g.validate()

# Example handling pattern (pseudo-API for error inspection):
missing = [e for e in errors if "missing target" in str(e).lower()]
if missing:
    # Branch: only allow terminals without nodes if the library allows it.
    non_terminal = [m for m in missing if not is_terminal(m.target)]
    if non_terminal:
        raise ValueError(f"undefined non-terminal targets: {non_terminal}")

    # If errors still complain about terminal missing, add explicit terminal per library schema.
    # (Exact Node fields depend on the library; supply what the library requires.)
    g.add_node(Node(id="End", type="terminal"))
    errors2 = g.validate()
    if errors2:
        raise ValueError(f"terminal handling still invalid: {errors2}")
```

## Runtime branch

- **If the library allows terminal references without an explicit terminal node:** keep the terminal implicit and do not add a node.
- **If the library requires an explicit terminal node:** add it with the correct type/required fields, then re-run `validate()`.

## Verification

- Re-run `g.validate()`.
- Confirm you did **not** add any placeholder nodes for non-terminal missing targets.

If validation still fails: remove any auto-fabricated nodes and rebuild the graph so that only nodes present in the script (plus a library-required terminal, if any) are included.
