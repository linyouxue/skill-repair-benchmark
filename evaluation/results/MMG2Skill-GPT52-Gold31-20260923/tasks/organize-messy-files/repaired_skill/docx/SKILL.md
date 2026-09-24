---
name: docx
description: Create/edit/analyze .docx files, with reliable text extraction for content-based
  decisions (e.g., classification) even when higher-level converters aren’t available.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Decide extraction route (fast → fallback)**  
   - Check if `pandoc` exists (`command -v pandoc`).  
   - If available, prefer: `pandoc --track-changes=all file.docx -t plain` (or `-o output.md`) for clean text.
2. **If `pandoc` is unavailable, extract text from OOXML (DOCX is a ZIP)**  
   - Either use the OOXML unpacker if present: `python ooxml/scripts/unpack.py file.docx out_dir`  
   - Or unzip directly and read `word/document.xml`.
3. **Parse for actual readable text**  
   - Extract text nodes from `word/document.xml` (primarily `<w:t>`), joining in reading order.  
   - If needed for context, also scan `word/comments.xml` and headers/footers, but prioritize `document.xml`.
4. **Use extracted text for downstream tasks (e.g., routing files)**  
   - If extracted text is suspiciously short/empty, treat as “needs deeper inspection” rather than assuming a category.
## Expected Result
You can reliably obtain sufficient DOCX text to determine the document’s subject, even without `pandoc`, without modifying the DOCX.
