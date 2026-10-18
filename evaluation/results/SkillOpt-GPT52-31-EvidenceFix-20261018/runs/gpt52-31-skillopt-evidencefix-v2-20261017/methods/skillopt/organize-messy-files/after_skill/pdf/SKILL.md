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


### Batch PDF Topic Classification (read-only)

When organizing many PDFs into a small, fixed taxonomy, **do a read-only classification pass first**: extract lightweight signals (metadata + first 1–2 pages of text) into per-file previews, apply simple keyword heuristics aligned to your folder taxonomy, then review/override before moving files. Avoid rewriting PDFs during classification.

#### 1) Extract title/author + first-page text (pypdf) with fallbacks
Notes:
- `page.extract_text()` can return `None` or an empty string for image-only/scanned PDFs or unusual encodings.
- If text is empty, fall back to `pdftotext` (often better) and then OCR only if still empty.

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
