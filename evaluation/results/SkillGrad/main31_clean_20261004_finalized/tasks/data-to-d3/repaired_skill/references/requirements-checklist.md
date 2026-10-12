# Requirements → checklist → end-to-end verification (D3 apps)

## Trigger
Use this when the spec includes **conditional UI behavior** (e.g., “no tooltip for ETFs”), **linked interactions**, or **multiple declared input sources**.

## Procedure

1. **Extract requirements into a checklist**. Turn each MUST/SHOULD into an observable behavior.
   - Include: inputs used, encodings, labels, tooltip fields, suppression conditions, selection linking, default state.
2. **Map inputs to UI elements**.
   - For each file/folder, record: (a) where it is loaded, (b) which view uses it, (c) when it is fetched (startup vs on-demand).
3. **Implement in a testable way**.
   - Write small pure functions for business rules (e.g., `isCategoryX(d)` and `tooltipHTML(d)`), so you can test them without a browser.
4. **Run an end-to-end pass**.
   - Manual: open the HTML and perform 3–5 interactions that cover each branch.
   - Scripted (optional): add a `window.__debug` object with accessors for critical rules and derived state.

## Runnable Python helper: build a checklist skeleton

```python
import re

spec = """PASTE SPEC HERE"""

req_lines = []
for line in spec.splitlines():
    if re.search(r"\b(must|should|require|do not|don't)\b", line, re.I):
        req_lines.append(line.strip())

for i, r in enumerate(req_lines, 1):
    print(f"[{i:02d}] {r}")
```

## Runtime branch: multiple input sources

- **If** the spec names 2+ data locations (e.g., a summary file + per-entity folder):
  - implement a minimal secondary view (details panel, sparkline, or “loaded N points” readout) that *actually loads* the second source.
- **Else**: keep the app single-source and document that in comments.

## Verification (and corrective action on failure)

Pick at least one example per branch and verify the observable output.

- Tooltip rules:
  - Hover a category that should show tooltip and confirm required fields are present.
  - Hover a category that should suppress tooltip and confirm it does not appear.
  - **If wrong**: locate the classification function and rewrite it to use the explicit label/flag; then re-test both branches.

- Multi-source rules:
  - Trigger the UI action that should load the secondary data and confirm there is a network/file fetch and a visible update.
  - **If the secondary source is unused**: either add a minimal on-select load + view, or add an explicit in-app note stating why it’s not used (only when the spec allows omission).
