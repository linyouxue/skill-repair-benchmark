# Reference loading: derive per-feature ranges and conversion candidates from the authoritative table

Use this procedure when the task provides an authoritative per-feature reference file (e.g., `reference/ckd_lab_features.md`) and you need a **non-invented**, testable way to produce `ref_ranges` and `ref_conversions`.

## Goal

Ensure unit harmonization is reference-driven: code must *parse* the reference, not re-create it with bespoke “physiological ranges” or hand-typed conversion factors.

## Procedure (runnable Python)

```python
import re
from pathlib import Path


def load_reference_markdown(md_path):
    """Parse a markdown table into dicts: ref_ranges[feature]=(lo,hi), ref_conversions[feature]=[factors].

    This is a tolerant parser: it looks for a pipe-delimited table with columns that include:
    - a feature/name column
    - min/max columns for the target unit
    - a conversion-candidates column containing numeric factors

    If your reference format differs, adapt *only the parsing*, not the values.
    """
    text = Path(md_path).read_text(encoding="utf-8")
    lines = [ln.rstrip("\n") for ln in text.splitlines()]

    # Find the first markdown table block.
    start = next((i for i, ln in enumerate(lines) if ln.strip().startswith("|") and "|" in ln[1:]), None)
    if start is None:
        raise ValueError(f"No markdown table found in {md_path}")

    # Collect contiguous table lines.
    table = []
    for ln in lines[start:]:
        if not ln.strip().startswith("|"):
            break
        table.append(ln)

    # Parse header
    header = [c.strip() for c in table[0].strip("|").split("|")]
    idx = {name.lower(): j for j, name in enumerate(header)}

    def col_like(*needles):
        for k, j in idx.items():
            if all(n in k for n in needles):
                return j
        return None

    feat_i = col_like("feature") or col_like("name")
    min_i = col_like("min")
    max_i = col_like("max")
    cand_i = col_like("conversion") or col_like("candidate") or col_like("factor")

    if feat_i is None or min_i is None or max_i is None:
        raise ValueError(
            "Reference table must include feature/name + min + max columns; "
            "inspect the reference file and adapt the parser accordingly."
        )

    ref_ranges = {}
    ref_conversions = {}

    # Data rows start after the separator line (---)
    for ln in table[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < len(header):
            continue

        feature = cells[feat_i]
        try:
            lo = float(cells[min_i])
            hi = float(cells[max_i])
        except ValueError:
            continue

        ref_ranges[feature] = (lo, hi)

        factors = []
        if cand_i is not None:
            # Extract numbers like 0.1, 10, 1e-3 from the candidates cell.
            cand_text = cells[cand_i]
            for m in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cand_text):
                try:
                    factors.append(float(m))
                except ValueError:
                    pass

        # Keep factors even if empty: explicit "no candidates" is valid.
        ref_conversions[feature] = factors

    if not ref_ranges:
        raise ValueError("Parsed zero reference ranges; verify table detection and column mapping.")

    return ref_ranges, ref_conversions


# Runtime branch: load from markdown when a file path is provided; otherwise assume already-loaded objects.
md_path = "reference/ckd_lab_features.md"
ref_ranges, ref_conversions = load_reference_markdown(md_path)
```

## Runtime branch guidance

- If parsing finds zero ranges or raises a column-mapping error: **stop** and inspect the reference file format; adjust the parser to the table’s columns. Do not replace the missing parse by inventing ranges/factors.
- If a feature exists in data but not in `ref_ranges`: mark it `no_ref` and leave values unchanged for that feature until the reference is updated.

## Verification

After loading, validate that the reference is usable before harmonization.

```python

def verify_reference(ref_ranges, ref_conversions, numeric_cols):
    missing = [c for c in numeric_cols if c not in ref_ranges]
    if missing:
        return False, {
            "missing_features": missing,
            "next_action": (
                "Do not invent ranges. Update/locate the authoritative reference to include these "
                "features (or remove them from the harmonization scope)."
            ),
        }

    bad = [f for f, (lo, hi) in ref_ranges.items() if not (lo < hi)]
    if bad:
        return False, {
            "bad_ranges": bad,
            "next_action": "Fix min/max ordering in the reference file, then re-parse and rerun.",
        }

    return True, {"next_action": "Proceed to range-triggered conversion using only these parsed values."}
```

If verification fails, follow `next_action`, then re-run the parse; do not proceed with conversion using guessed parameters.
