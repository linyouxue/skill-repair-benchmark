---
name: pdf
description: Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms. When Claude needs to fill in a PDF form or programmatically process, generate, or analyze PDF documents at scale.
license: Proprietary. LICENSE.txt has complete terms
---

# PDF Processing Guide

## Overview

This guide covers essential PDF processing operations using Python libraries and command-line tools. For advanced features, JavaScript libraries, and detailed examples, see reference.md. If you need to fill out a PDF form, read forms.md and follow its instructions.

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

# Read a PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python Libraries

### pypdf - Basic Operations

#### Merge PDFs
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### Split PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### Extract Metadata
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"Title: {meta.title}")
print(f"Author: {meta.author}")
print(f"Subject: {meta.subject}")
print(f"Creator: {meta.creator}")
```

#### Rotate Pages
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # Rotate 90 degrees clockwise
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber - Text and Table Extraction

#### Extract Text with Layout
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### Extract Tables
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)
```

#### Advanced Table Extraction
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # Check if table is not empty
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# Combine all tables
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### reportlab - Create PDFs

#### Basic PDF Creation
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

# Add text
c.drawString(100, height - 100, "Hello World!")
c.drawString(100, height - 120, "This is a PDF created with reportlab")

# Add a line
c.line(100, height - 140, 400, height - 140)

# Save
c.save()
```

#### Create PDF with Multiple Pages
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# Add content
title = Paragraph("Report Title", styles['Title'])
story.append(title)
story.append(Spacer(1, 12))

body = Paragraph("This is the body of the report. " * 20, styles['Normal'])
story.append(body)
story.append(PageBreak())

# Page 2
story.append(Paragraph("Page 2", styles['Heading1']))
story.append(Paragraph("Content for page 2", styles['Normal']))

# Build PDF
doc.build(story)
```

## Command-Line Tools

### pdftotext (poppler-utils)
```bash
# Extract text
pdftotext input.pdf output.txt

# Extract text preserving layout
pdftotext -layout input.pdf output.txt

# Extract specific pages
pdftotext -f 1 -l 5 input.pdf output.txt  # Pages 1-5
```

### qpdf
```bash
# Merge PDFs
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# Split pages
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# Rotate pages
qpdf input.pdf output.pdf --rotate=+90:1  # Rotate page 1 by 90 degrees

# Remove password
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

### pdftk (if available)
```bash
# Merge
pdftk file1.pdf file2.pdf cat output merged.pdf

# Split
pdftk input.pdf burst

# Rotate
pdftk input.pdf rotate 1east output rotated.pdf
```

## Common Tasks



### PDF Semantic Classification for Organizing Research Papers (batch workflow)

Goal: classify many academic PDFs into a small fixed taxonomy (e.g., `LLM`, `trapped_ion_and_qc`, `black_hole`, `DNA`, `music_history`) **without modifying PDFs**. Use a two-pass approach: (A) extract structured signals into a machine-readable index, (B) classify + flag ambiguous cases, then (C) move files in a separate step.

#### A) Batch extraction: title, authors, abstract-ish block, and first-page text
Use multiple extractors and keep provenance. For papers, the most reliable signals are:
- PDF metadata (`/Title`, `/Author`) when present
- first page text (often contains title/authors/abstract)
- explicit “Abstract” section (when detectable)

```python
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

WS_RE = re.compile(r"\s+")

@dataclass
class PaperSignals:
    file: str
    meta_title: str = ""
    meta_author: str = ""
    meta_subject: str = ""
    first_page_text: str = ""
    first_2_pages_text: str = ""
    abstract_snippet: str = ""
    extractor: str = "pypdf+pdfplumber"
    ocr_used: bool = False


def _clean(t: str) -> str:
    t = (t or "").replace("\x00", " ")
    t = WS_RE.sub(" ", t).strip()
    return t


def _extract_with_pypdf(pdf_path: Path, max_pages: int = 2) -> tuple[dict, str]:
    reader = PdfReader(str(pdf_path))
    meta = reader.metadata or {}
    chunks = []
    for p in reader.pages[:max_pages]:
        chunks.append(_clean(p.extract_text() or ""))
    return {
        "title": getattr(meta, "title", "") or "",
        "author": getattr(meta, "author", "") or "",
        "subject": getattr(meta, "subject", "") or "",
    }, "\n\n".join([c for c in chunks if c]).strip()


def _extract_first_page_with_pdfplumber(pdf_path: Path) -> str:
    # pdfplumber can outperform pypdf on some encodings and preserves layout options.
    with pdfplumber.open(str(pdf_path)) as pdf:
        if not pdf.pages:
            return ""
        return _clean(pdf.pages[0].extract_text() or "")


def _extract_first_pages_with_pdftotext(pdf_path: Path, max_pages: int = 2) -> str:
    # poppler's pdftotext is often more robust than Python libraries.
    cmd = ["pdftotext", "-f", "1", "-l", str(max_pages), "-layout", str(pdf_path), "-"]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return _clean(out.decode("utf-8", errors="replace"))
    except Exception:
        return ""


def extract_abstract_snippet(text: str) -> str:
    # Heuristic: find 'Abstract' then take the next ~1200 chars.
    t = text or ""
    m = re.search(r"\babstract\b\s*[:\-]?\s*(.{200,2000})", t, flags=re.IGNORECASE)
    if not m:
        return ""
    return _clean(m.group(1))[:1200]


def extract_signals(pdf_path: Path) -> PaperSignals:
    meta, t12 = _extract_with_pypdf(pdf_path, max_pages=2)
    t1_plumber = _extract_first_page_with_pdfplumber(pdf_path)

    # Choose best first-page text among sources.
    first_page = t1_plumber or (t12.split("\n\n", 1)[0] if t12 else "")

    # If still empty, fall back to pdftotext for a read-only preview.
    if not first_page and not t12:
        t12 = _extract_first_pages_with_pdftotext(pdf_path, max_pages=2)
        first_page = (t12.split("\n\n", 1)[0] if t12 else "")

    abs_snip = extract_abstract_snippet(first_page + "\n" + (t12 or ""))

    return PaperSignals(
        file=pdf_path.name,
        meta_title=_clean(meta.get("title", "")),
        meta_author=_clean(meta.get("author", "")),
        meta_subject=_clean(meta.get("subject", "")),
        first_page_text=first_page,
        first_2_pages_text=t12,
        abstract_snippet=abs_snip,
    )


def build_signals_index(pdf_dir: Path, out_jsonl: Path) -> None:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for pdf_path in sorted(pdf_dir.glob("*.pdf")):
            sig = extract_signals(pdf_path)
            f.write(json.dumps(asdict(sig), ensure_ascii=False) + "\n")

# Example:
# build_signals_index(Path("/root/papers/all"), Path("previews/signals.jsonl"))
```

#### B) Topic inference: stronger heuristics + multi-signal scoring
Misclassifications usually come from generic keywords and weak tie-breaking. Improve reliability by:
- weighting title/abstract higher than body text
- requiring **≥2 anchor hits** before auto-assigning to non-catch-all folders
- adding negative/contrast cues (e.g., “Kerr”, “Schwarzschild” strongly indicate black_hole; “qubit”, “ion trap” indicate trapped_ion_and_qc)

```python
import json
from pathlib import Path

SUBJECTS = ["LLM", "trapped_ion_and_qc", "black_hole", "DNA", "music_history"]

ANCHORS = {
    "LLM": ["transformer", "attention", "pretrain", "prompt", "rlhf", "token", "in-context", "instruction tuning", "large language model"],
    "trapped_ion_and_qc": ["trapped ion", "ion trap", "paul trap", "qubit", "gate fidelity", "quantum error correction", "surface code", "entanglement"],
    "black_hole": ["black hole", "event horizon", "hawking", "kerr", "schwarzschild", "accretion", "general relativity", "ads/cft"],
    "DNA": ["genome", "chromatin", "nucleosome", "transcription", "crispr", "polymerase", "base pair", "replication"],
    "music_history": ["composer", "symphony", "opera", "sonata", "baroque", "romantic", "musicology", "jazz", "blues"],
}

WEIGHTS = {
    "title": 3,
    "abstract": 3,
    "meta_subject": 2,
    "first_page": 1,
}


def score(sig: dict) -> dict[str, int]:
    title = (sig.get("meta_title", "") + " " + sig.get("first_page_text", "")[:400]).lower()
    abstract = (sig.get("abstract_snippet", "") or "").lower()
    meta_subj = (sig.get("meta_subject", "") or "").lower()
    first_page = (sig.get("first_page_text", "") or "").lower()

    scores = {s: 0 for s in SUBJECTS}
    hits = {s: 0 for s in SUBJECTS}

    for subj, kws in ANCHORS.items():
        for kw in kws:
            kw_l = kw.lower()
            if kw_l in title:
                scores[subj] += WEIGHTS["title"]; hits[subj] += 1
            if kw_l in abstract:
                scores[subj] += WEIGHTS["abstract"]; hits[subj] += 1
            if kw_l in meta_subj:
                scores[subj] += WEIGHTS["meta_subject"]; hits[subj] += 1
            if kw_l in first_page:
                scores[subj] += WEIGHTS["first_page"]; hits[subj] += 1

    # Decision rule: require at least 2 anchor hits for non-catch-all.
    best = max(scores, key=scores.get)
    if hits[best] < 2 or scores[best] == 0:
        best = "music_history"  # catch-all per task rule
    return {"predicted": best, "scores": scores, "hits": hits}


def classify_signals_jsonl(signals_jsonl: Path, out_tsv: Path) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with signals_jsonl.open("r", encoding="utf-8") as f, out_tsv.open("w", encoding="utf-8") as out:
        out.write("file\tpredicted\tbest_score\tsecond_score\tneeds_review\n")
        for line in f:
            sig = json.loads(line)
            res = score(sig)
            scores = res["scores"]
            ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            best_s, best_v = ordered[0]
            second_v = ordered[1][1] if len(ordered) > 1 else 0
            # Flag low margin or low evidence for review.
            needs_review = int((best_v - second_v) < 2 or res["hits"][best_s] < 3)
            out.write(f"{sig['file']}\t{res['predicted']}\t{best_v}\t{second_v}\t{needs_review}\n")

# Example:
# classify_signals_jsonl(Path('previews/signals.jsonl'), Path('previews/classification.tsv'))
```

#### C) Reconciliation against expected mappings + human review loop
For reliable at-scale organization, add a reconciliation step that:
- checks every input file appears exactly once in the output mapping
- prints/exports `needs_review=1` items and near-ties for manual override
- supports an optional “expected mapping” file to compare and audit mistakes (useful for regression/testing)

Practical approach:
- Keep `classification.tsv` as the single source of truth for moves.
- Allow an overrides file (same format) applied after heuristics.

#### D) Poor PDFs: fallback ladder (pypdf → pdfplumber → pdftotext → OCR)
1) Try pypdf/pdfplumber first (fast, no external deps)
2) If empty/garbled, try `pdftotext -layout` for first 1–2 pages
3) If still empty, treat as scanned: OCR first page(s) **for preview only**

Use OCR sparingly: it is slower and noisier. Only OCR the first page(s) to get title/abstract signals.

#### E) Downstream organization: move as a separate step (and avoid stray artifacts)
Perform file moves only after review. Do not create or copy `.docx/.pptx` templates into unrelated directories during processing (e.g., library template files under site-packages can be mistaken as stray documents by verifiers). Keep working files under the dataset root (e.g., `previews/` inside your project directory) and avoid writing to `$HOME/.cache`.
### Batch PDF Topic Classification (read-only)

When organizing many PDFs into a small, fixed taxonomy, **do a read-only classification pass first**: extract lightweight signals (metadata + first 1–2 pages of text) into per-file previews, apply simple keyword heuristics aligned to your folder taxonomy, then review/override before moving files. Avoid rewriting PDFs during classification.

#### 1) Extract title/author + first-page/abstract signals (multi-extractor) with fallbacks
Notes:
- `page.extract_text()` can return `None`/empty for image-only PDFs or unusual encodings.
- For robust semantic classification at scale, extract **multiple signals**: metadata, first page text, and (when detectable) an abstract snippet.
- If Python extraction is empty, fall back to `pdftotext` for the first 1–2 pages (often better), then OCR **only if still empty**.

```python
from __future__ import annotations

import re
from pathlib import Path
from pypdf import PdfReader

SUBJECTS = ["LLM", "trapped_ion_and_qc", "black_hole", "DNA", "music_history"]

KEYWORDS = {
    "LLM": [
        "large language model", "llm", "transformer", "attention", "pretrain", "prompt", "instruction", "chatgpt",
        "token", "fine-tuning", "rlhf", "alignment", "diffusion language", "in-context",
    ],
    "trapped_ion_and_qc": [
        "trapped ion", "ion trap", "paul trap", "quantum computing", "qubit", "gate", "fidelity", "rydberg",
        "superconducting", "quantum error correction", "qec", "surface code", "entanglement", "cirac", "molmer",
    ],
    "black_hole": [
        "black hole", "event horizon", "hawking", "accretion", "kerr", "schwarzschild", "gravitational wave",
        "general relativity", "ads/cft", "singularity", "entropy", "information paradox",
    ],
    "DNA": [
        "dna", "genome", "chromatin", "nucleosome", "transcription", "replication", "polymerase", "sequence",
        "gene", "crispr", "base pair", "helix", "methylation",
    ],
    "music_history": [
        "music", "composer", "symphony", "opera", "sonata", "baroque", "classical", "romantic",
        "jazz", "blues", "musicology", "historical", "performance practice",
    ],
}

def safe_extract_first_pages(pdf_path: Path, max_pages: int = 2) -> tuple[str, dict]:
    reader = PdfReader(str(pdf_path))
    meta = reader.metadata or {}
    chunks = []
    for page in reader.pages[:max_pages]:
        t = page.extract_text() or ""
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            chunks.append(t)
    text = "\n\n".join(chunks).strip()
    return text, {
        "title": getattr(meta, "title", None) or "",
        "author": getattr(meta, "author", None) or "",
        "subject": getattr(meta, "subject", None) or "",
        "creator": getattr(meta, "creator", None) or "",
    }

def score_subject(text: str, meta: dict) -> dict[str, int]:
    hay = (" ".join([meta.get("title", ""), meta.get("subject", ""), text])).lower()
    scores = {s: 0 for s in SUBJECTS}
    for subj, kws in KEYWORDS.items():
        for kw in kws:
            if kw in hay:
                scores[subj] += 1
    return scores

def predict_subject(text: str, meta: dict) -> tuple[str, dict[str, int]]:
    scores = score_subject(text, meta)
    best = max(scores, key=scores.get)
    # If everything is zero, default to the catch-all folder (often music_history per task rule).
    if scores[best] == 0:
        best = "music_history"
    return best, scores
```

#### 2) Batch-generate per-file previews for human/LLM review
This produces a `previews/` directory containing one `.txt` per PDF with metadata, the first 1–2 pages of extracted text, and the heuristic label + scores.

```python
from pathlib import Path
import json

PDF_DIR = Path("papers/all")  # adjust
OUT_DIR = Path("previews")
OUT_DIR.mkdir(parents=True, exist_ok=True)

index = []
for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
    text, meta = safe_extract_first_pages(pdf_path, max_pages=2)
    pred, scores = predict_subject(text, meta)

    preview_path = OUT_DIR / (pdf_path.name + ".preview.txt")
    preview_path.write_text(
        "\n".join([
            f"FILE: {pdf_path.name}",
            f"PREDICTED: {pred}",
            f"SCORES: {json.dumps(scores, sort_keys=True)}",
            f"META_TITLE: {meta.get('title','')}",
            f"META_AUTHOR: {meta.get('author','')}",
            f"META_SUBJECT: {meta.get('subject','')}",
            "--- EXTRACT (first pages) ---",
            text or "<EMPTY_TEXT_EXTRACT>",
            "",
        ]),
        encoding="utf-8",
        errors="replace",
    )

    index.append({"file": pdf_path.name, "predicted": pred, "scores": scores})

(OUT_DIR / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
print(f"Wrote {len(index)} previews to {OUT_DIR}/")
```

#### 3) If pypdf text is empty: try pdftotext, then OCR (only when needed)
`pdftotext` can extract text that some Python libraries miss.

```bash
# Extract only the first 2 pages for a quick preview (read-only)
mkdir -p previews_txt
pdftotext -f 1 -l 2 -layout "input.pdf" "previews_txt/input.preview.txt"
```

If both pypdf and `pdftotext` yield empty output, the PDF is likely scanned. Use OCR for **previewing** (still read-only), e.g., convert the first page(s) to images and run Tesseract (see OCR example in this guide).

#### 4) Heuristic tips to reduce common confusions
- Prefer **domain-specific terms** over generic ones (e.g., “sequence”, “model”, “information” are ambiguous).
- Use **multi-keyword confirmation**: require ≥2 strong hits before auto-moving; otherwise flag for review.
- Add **folder-specific anchor terms**:
  - LLM: transformer, attention, pretraining, prompting, RLHF, tokens
  - trapped_ion_and_qc: trapped ion, qubit, gate fidelity, error correction, surface code
  - black_hole: event horizon, Hawking, Kerr, accretion, GR
  - DNA: genome, nucleosome, transcription, CRISPR, base pairs
  - music_history: composer, symphony, opera, baroque/romantic, musicology

#### 5) Move files only after preview/review
After generating previews and resolving ambiguous cases, perform file moves as a separate step (do not rename or modify PDFs). Keep the extraction/classification scripts read-only with respect to source PDFs.



**Practical move script (uses a reviewed mapping file):**

`classification.tsv` format (tab-separated): `file<TAB>subject` (ignore extra columns).

```python
from pathlib import Path
import csv
import shutil

ROOT = Path("/root/papers")
SRC = ROOT / "all"

subjects = {"LLM", "trapped_ion_and_qc", "black_hole", "DNA", "music_history"}

# Create folders
for s in subjects:
    (ROOT / s).mkdir(parents=True, exist_ok=True)

mapping_path = ROOT / "classification.tsv"  # reviewed output

seen = set()
with mapping_path.open() as f:
    r = csv.reader(f, delimiter="\t")
    for row in r:
        if not row or row[0].lower() == "file":
            continue
        name, subject = row[0].strip(), row[1].strip()
        if subject not in subjects:
            raise ValueError(f"Bad subject {subject} for {name}")
        if name in seen:
            raise ValueError(f"Duplicate mapping for {name}")
        seen.add(name)
        src = SRC / name
        dst = ROOT / subject / name
        if not src.exists():
            # If already moved, skip; otherwise treat as error in strict mode.
            continue
        shutil.move(str(src), str(dst))

# Optional: ensure staging folder is empty after successful move.
# (Only delete if you're sure no other files should remain there.)
# if SRC.exists() and not any(SRC.iterdir()):
#     SRC.rmdir()
```
### Extract Text from Scanned PDFs
```python
# Requires: pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

# Convert PDF to images
images = convert_from_path('scanned.pdf')

# OCR each page
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"

print(text)
```

### Add Watermark
```python
from pypdf import PdfReader, PdfWriter

# Create watermark (or load existing)
watermark = PdfReader("watermark.pdf").pages[0]

# Apply to all pages
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### Extract Images
```bash
# Using pdfimages (poppler-utils)
pdfimages -j input.pdf output_prefix

# This extracts all images as output_prefix-000.jpg, output_prefix-001.jpg, etc.
```

### Password Protection
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# Add password
writer.encrypt("userpassword", "ownerpassword")

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## Quick Reference

| Task | Best Tool | Command/Code |
|------|-----------|--------------|
| Merge PDFs | pypdf | `writer.add_page(page)` |
| Split PDFs | pypdf | One page per file |
| Extract text | pdfplumber | `page.extract_text()` |
| Extract tables | pdfplumber | `page.extract_tables()` |
| Create PDFs | reportlab | Canvas or Platypus |
| Command line merge | qpdf | `qpdf --empty --pages ...` |
| OCR scanned PDFs | pytesseract | Convert to image first |
| Fill PDF forms | pdf-lib or pypdf (see forms.md) | See forms.md |

## Next Steps

- For advanced pypdfium2 usage, see reference.md
- For JavaScript libraries (pdf-lib), see reference.md
- If you need to fill out a PDF form, follow the instructions in forms.md
- For troubleshooting guides, see reference.md
