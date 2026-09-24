---
name: pdf
description: Extract and work with PDF text robustly for downstream automation (e.g.,
  subject classification), including handling low-text/scanned PDFs.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Extract text with command-line tooling first**
   - Use `pdftotext` (poppler) when available:  
     - First N pages: `pdftotext -f 1 -l 5 file.pdf -`  
     - Try `-layout` if structure matters: `pdftotext -layout ...`
2. **Detect empty/low-yield extraction**
   - If extracted text is very short or empty, assume the PDF may be scanned or image-heavy.
3. **Escalate for scanned PDFs (when required)**
   - Use OCR (e.g., `pdf2image` + `pytesseract`) on a small page range to obtain enough text for classification.
4. **Use metadata only as supplemental signal**
   - Title/subject metadata can help but should not override extracted body text when available.
## Expected Result
You obtain enough text signal from each PDF to support accurate content-based routing, including handling cases where the first page is sparse or the PDF is scanned.
