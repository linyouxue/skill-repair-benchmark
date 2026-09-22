# Deliverable enforcement for file-graded PDF tasks

Use this when success is judged by the existence/validity of output files at exact paths (not by printed text).

## Procedure

1. **Write an explicit input→output contract**: build a list (or dict) mapping each input artifact to its exact required absolute output path.
2. **Create parent directories** for all outputs (e.g., `mkdir -p` the destination directory).
3. **Run the transformation** (redaction/merge/split/etc.) writing to the exact paths (never rely on default filenames, the current working directory, or relative paths).
4. **Verify each output**: existence, non-empty bytes, openable as PDF, and basic invariants (page count, text retention when applicable).
5. **On any failure**: do not end; delete the bad/misplaced output and retry.

## Runnable check (Python)

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path

import fitz  # PyMuPDF


def ensure_parent_dirs(paths: list[str]) -> None:
    for p in paths:
        Path(p).parent.mkdir(parents=True, exist_ok=True)


def verify_pdf_openable(output_path: str) -> None:
    if not os.path.exists(output_path):
        raise FileNotFoundError(output_path)
    if os.path.getsize(output_path) == 0:
        raise ValueError(f"Empty PDF: {output_path}")

    doc = fitz.open(output_path)
    try:
        if len(doc) == 0:
            raise ValueError(f"Zero-page PDF: {output_path}")
    finally:
        doc.close()


def verify_pdf_pair(original_path: str | None, output_path: str) -> None:
    verify_pdf_openable(output_path)

    if original_path is None:
        return

    in_doc = fitz.open(original_path)
    out_doc = fitz.open(output_path)
    try:
        if len(out_doc) != len(in_doc):
            raise ValueError(f"Page count changed: {len(in_doc)} -> {len(out_doc)}")
    finally:
        out_doc.close()
        in_doc.close()


def reconcile_misplaced_outputs(required: list[str], candidates: list[str]) -> list[tuple[str, str]]:
    """Return (src,dst) moves when a required output is missing but a plausible candidate exists elsewhere."""
    planned: list[tuple[str, str]] = []
    missing = [p for p in required if not os.path.exists(p)]

    for dst in missing:
        name = Path(dst).name
        src = next((c for c in candidates if Path(c).name == name and os.path.exists(c)), None)
        if src is not None:
            planned.append((src, dst))

    return planned


def enforce_deliverables(originals: list[str] | None, outputs: list[str]) -> None:
    ensure_parent_dirs(outputs)

    # Branch: with vs without original-based checks
    if originals is None:
        for outp in outputs:
            verify_pdf_pair(None, outp)
        return

    if len(originals) != len(outputs):
        raise ValueError("originals/outputs length mismatch")

    for inp, outp in zip(originals, outputs):
        verify_pdf_pair(inp, outp)


# Example usage (fill in upstream transformation that writes outputs):
# enforce_deliverables(["in1.pdf", "in2.pdf"], ["out1.pdf", "out2.pdf"])
```

## Runtime branch: what to do when verification fails

- **If a required path is missing**: you likely wrote to the wrong location (common when you saved with a default filename or assumed `cd` controls output location).
  1) Corrective action: search for misplaced candidates (e.g., same basename in the working directory).
  2) If found, move/copy into the required destination path, then re-run the verification gate.
  3) If not found, re-run the transformation passing the exact absolute output path.

- **If the file is empty or unopenable**: the save step failed or produced a corrupt file.
  - Corrective action: delete the output and re-run the transformation; if the same method repeats failure, save to a temp path then atomically rename, or switch libraries.

- **If an invariant fails (e.g., page count changed unexpectedly)**: you likely rebuilt the document rather than editing/saving the original.
  - Corrective action: ensure you are editing in-place and saving, not creating a new PDF from extracted text.

## Verification step (gate before ending)

Run a final filesystem inventory at the **exact required paths** and re-open all deliverables:

```bash
# Replace arguments with the exact required output paths.
for p in "$@"; do
  test -s "$p" || { echo "MISSING/EMPTY: $p"; exit 1; }
done
python -c "import fitz,sys; [fitz.open(p).close() for p in sys.argv[1:]]" "$@"
```

If any command errors or any output is missing, **do not end**: fix the path/toolchain and regenerate until all outputs pass.

## Optional cleanup: remove misplaced outputs

When you accidentally wrote default-named outputs into the working directory (or any other non-required location), remove them to avoid confusing inventories.

```bash
# Use a narrow glob; verify it matches only the mistaken outputs before deleting.
ls -1 ./*.pdf 2>/dev/null || true
rm -f ./*.pdf
```
