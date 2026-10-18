# Handbook retrieval — reader retry queue and null-fallback

Use this reference when the task cites a handbook / spec / standards PDF and
*any* numeric threshold, region, window, margin, or feasibility rule in the
downstream computations depends on it. Skip when every needed parameter is
already supplied inline in the task prompt or in a non-PDF structured file
(CSV / JSON / YAML).

## Why this matters

Downstream rules (threshold compliance, representative-TC selection,
feasibility derivation, best-run ranking, pre-ship anomaly scans) all operate
on handbook-grounded parameters. If handbook text is never retrieved and the
agent falls back to a memory-prior ("typical reflow TAL is 30–60 s", "ramp
limit is 2 °C/s", "margin is +20 °C"), every downstream verdict is operating
on fabricated inputs — the anomaly scan then cannot distinguish "wrong
constant" from "wrong rule" and will mis-attribute mass-fails as "systemic
production patterns". Handbook retrieval sits upstream of every other pattern
in this skill.

## Reader retry queue

Try readers in this order. Each one is a fresh attempt; do not stop on the
first failure.

1. `pypdf` (modern, pip-installable)
2. `PyPDF2` (legacy; still common)
3. `pdfplumber` (table-friendly, handles mixed layouts)
4. `pdfminer.six` (robust low-level extractor)
5. Shell `pdftotext` from poppler-utils (`subprocess.run(["pdftotext", path, "-"])`)
6. Claude's native PDF ingestion — read the PDF file directly into the model
   as a document attachment rather than extracting text
7. OCR fallback — rasterise with `pdf2image` and run `pytesseract` on each
   page (only for scanned or encrypted-with-images PDFs)

**Minimum effort before escalating:** at least 3 readers must have been
attempted (with distinct failure modes recorded) before the agent is allowed
to conclude "handbook unreadable".

## Branched algorithm

```python
import importlib, subprocess, shutil

READERS = ["pypdf", "PyPDF2", "pdfplumber", "pdfminer.six", "pdftotext_shell",
           "claude_native", "ocr"]

def try_read_handbook(pdf_path: str) -> tuple[str | None, list[str]]:
    """Return (text, attempts_log). text is None if all readers failed."""
    attempts = []

    for reader in READERS:
        try:
            if reader == "pypdf":
                mod = importlib.import_module("pypdf")
                r = mod.PdfReader(pdf_path)
                text = "\n".join(p.extract_text() or "" for p in r.pages)
            elif reader == "PyPDF2":
                mod = importlib.import_module("PyPDF2")
                r = mod.PdfReader(pdf_path)
                text = "\n".join(p.extract_text() or "" for p in r.pages)
            elif reader == "pdfplumber":
                mod = importlib.import_module("pdfplumber")
                with mod.open(pdf_path) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            elif reader == "pdfminer.six":
                mod = importlib.import_module("pdfminer.high_level")
                text = mod.extract_text(pdf_path)
            elif reader == "pdftotext_shell":
                if shutil.which("pdftotext") is None:
                    raise FileNotFoundError("pdftotext binary not on PATH")
                res = subprocess.run(["pdftotext", pdf_path, "-"],
                                     capture_output=True, text=True, check=True)
                text = res.stdout
            elif reader == "claude_native":
                # Branch: hand the raw PDF to the model as a file attachment
                # and continue reasoning on that content. In code, this means
                # pausing the extraction loop and switching tool: read the file
                # bytes and attach them to the next model turn.
                raise RuntimeError("claude_native: switch to native PDF tool")
            elif reader == "ocr":
                from pdf2image import convert_from_path
                import pytesseract
                images = convert_from_path(pdf_path)
                text = "\n".join(pytesseract.image_to_string(im) for im in images)
            else:
                raise RuntimeError(f"unknown reader {reader}")

            # Empty-text branch — some readers succeed import-wise but return
            # whitespace on encrypted or image-only PDFs.
            if text is None or len(text.strip()) < 50:
                attempts.append(f"{reader}: empty_text ({len(text or '')} chars)")
                continue

            attempts.append(f"{reader}: ok ({len(text)} chars)")
            return text, attempts

        except ImportError as e:
            attempts.append(f"{reader}: ImportError ({e})")
            # Optional intermediate: pip install the missing reader once per
            # session, then re-try this reader before moving on.
        except FileNotFoundError as e:
            attempts.append(f"{reader}: FileNotFoundError ({e})")
        except Exception as e:
            # encrypted / malformed / parser-specific errors land here
            attempts.append(f"{reader}: {type(e).__name__} ({e})")

    return None, attempts
```

## All-readers-fail branch — null, not memory-prior

If every reader failed (empty text, encryption, broken PDF), the correct
response is to emit `null` for every threshold that depended on the handbook
and mark the downstream metric as unanswerable. Do **not** fall back to a
memory-prior, even one that looks "directionally reasonable".

```python
text, attempts = try_read_handbook("/app/data/handbook.pdf")

if text is None:
    print("[handbook] unreadable. attempts:")
    for line in attempts:
        print(" -", line)
    cfg = {
        "preheat_region":       None,
        "ramp_limit_c_per_s":   None,
        "tal_min_s":            None,
        "tal_max_s":            None,
        "peak_margin_c":        None,
        "ramp_rep_location":    None,
        "peak_rep_location":    None,
        "tal_rep_location":     None,
        "conveyor_rule":        None,
        "_handbook_status":     "unreadable",
    }
else:
    cfg = extract_cfg_from_handbook_text(text)
    cfg["_handbook_status"] = "ok"
```

## Parameter-grounding comment discipline

Even when the handbook *is* readable, every numeric value in `cfg` must have
an adjacent code comment with the verbatim handbook sentence that supports
it. If no sentence can be quoted, that specific key is `None` — not a
fabricated value.

```python
cfg = {
    # Handbook §3.2: "the preheat zone shall ramp from 100 °C to 150 °C"
    "preheat_region": {"type": "temp_band", "tmin": 100.0, "tmax": 150.0},

    # Handbook §3.2: "ramp rate shall not exceed 3 °C/s in the preheat band"
    "ramp_limit_c_per_s": 3.0,

    # No handbook sentence found for TAL lower bound — leave as None and
    # emit null for the TAL lower-bound verdict.
    "tal_min_s": None,
    # Handbook §4.1: "time above liquidus shall not exceed 90 s"
    "tal_max_s": 90.0,
}
```

The signature of a ungrounded config entry is a numeric value with no
adjacent handbook quote. Treat the comment as a hard requirement, not a
nicety: if the review ever shows a bare number, the entry is suspect.

## Verification

Three post-retrieval checks:

```python
# 1. Attempts audit — at least 3 reader attempts if any failed.
if cfg["_handbook_status"] == "unreadable":
    assert len(attempts) >= 3, (
        f"handbook declared unreadable after only {len(attempts)} attempt(s); "
        f"try more readers (see queue) before falling back to null"
    )

# 2. Grounding audit — every non-None cfg entry must have an adjacent
#    comment with a handbook quote. In code review this is a visual check;
#    programmatically, keep a parallel dict of handbook quotes.
cfg_quotes = {
    "preheat_region":     "Handbook §3.2: the preheat zone shall ramp ...",
    "ramp_limit_c_per_s": "Handbook §3.2: ramp rate shall not exceed ...",
    "tal_max_s":          "Handbook §4.1: time above liquidus shall not ...",
    # tal_min_s intentionally absent — cfg["tal_min_s"] must be None
}
for key, val in cfg.items():
    if key.startswith("_") or key == "conveyor_rule":
        continue
    if val is not None:
        assert key in cfg_quotes and cfg_quotes[key].strip(), (
            f"cfg[{key}]={val} has no handbook quote — set to None instead "
            f"of shipping a memory-prior"
        )

# 3. Downstream-null propagation — any metric whose threshold is None must
#    emit null in its per-run output, not a pass/fail verdict.
for run in run_outputs:
    if cfg["tal_max_s"] is None and run.get("tal_ok") is not None:
        raise AssertionError(
            f"run {run['run_id']}: tal_max_s is None but tal_ok={run['tal_ok']}; "
            f"ungrounded threshold must emit null, not a verdict"
        )
```

**If check 1 fails:** go back and try more readers. The retry queue above
lists seven options; three attempts is the floor, not the ceiling.

**If check 2 fails:** either (a) add a handbook quote for that key, or (b)
set the key to `None`. Do not ship a bare numeric value.

**If check 3 fails:** rewrite the per-run output so the metric emits `null`
when its threshold is `None`. A verdict based on a `None` threshold is a
fabrication.

## Rationalisation hedges

If after a failed handbook read the agent writes "typical reflow TAL is
30–60 s", "I'll assume the standard ramp limit of 2 °C/s", "the margin is
usually +20 °C", or similar — that is a memory-prior substituting for the
handbook. Treat it as a hard stop: delete the assumed constants, run the
retry queue again, and if it still fails, emit `null`.
