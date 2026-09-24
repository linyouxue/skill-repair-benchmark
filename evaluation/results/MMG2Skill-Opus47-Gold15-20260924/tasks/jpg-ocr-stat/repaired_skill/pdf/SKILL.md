---
name: pdf
description: Comprehensive PDF manipulation toolkit for extracting text and tables,
  creating new PDFs, merging/splitting documents, and handling forms.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. Pick the right library: `pypdf` for merge/split/metadata/rotation, `pdfplumber` for text and table extraction, `reportlab` for creating PDFs, `pytesseract`+`pdf2image` for scanned PDFs.
2. For merges, iterate readers and `writer.add_page(page)`; for splits, write one page per output.
3. For tables, use `page.extract_tables()` and optionally build a pandas DataFrame.
4. For CLI, prefer `qpdf` for merge/split/rotate/decrypt and `pdftotext -layout` for text.
5. For forms, follow `forms.md` in the skill bundle.
## Expected Result
The requested PDF operation completes and the output file is written to disk.
