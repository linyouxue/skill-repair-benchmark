---
name: image-ocr
description: Extract text content from images using Tesseract OCR via Python
---

## Steps
1. Enumerate image files once (e.g., `Path(img_dir).iterdir()`), filter by extension, and **sort by filename**.
2. **Avoid expensive multi-pass OCR by default**: run a single OCR pass per image using a receipt-friendly segmentation mode (typically `--psm 6`), optionally with light preprocessing (grayscale + autocontrast + sharpen).
3. If you must improve recall, **only escalate** to additional OCR passes (other `--psm` values / variants) **when parsing fails** for the specific field(s), not for every image.
4. For long batch runs, **cache OCR outputs** so later steps (parsing / Excel writing) don’t re-OCR:
   - Build a `{filename: ocr_text}` dict during the OCR phase.
   - Optionally write/read a JSON cache file (e.g., `/app/workspace/ocr_cache.json`) to resume without repeating OCR.
5. Return/store raw OCR text (per filename) for downstream parsing; keep filenames as the stable join key.
## Expected Result
A deterministic, filename-keyed collection of OCR text produced in a single bounded pass (with optional targeted fallback), enabling later parsing/Excel export **without re-running OCR**.
