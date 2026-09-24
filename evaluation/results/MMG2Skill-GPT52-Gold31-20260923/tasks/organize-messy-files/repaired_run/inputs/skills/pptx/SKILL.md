---
name: pptx
description: Create/edit/analyze .pptx files, with reliable text extraction from slides
  and notes for content-based decisions when high-level converters aren’t available.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Decide extraction route (fast → fallback)**
   - Check for `markitdown` availability (`python -m markitdown --help`).  
   - If available: `python -m markitdown file.pptx` to extract text quickly.
2. **If high-level extraction is unavailable, use OOXML fallback**
   - Unpack via `python ooxml/scripts/unpack.py file.pptx out_dir` if present, or unzip directly (PPTX is a ZIP).
3. **Extract text from the right PPTX parts**
   - Primary: `ppt/slides/slide*.xml` (shape text runs).  
   - Also include: `ppt/notesSlides/notesSlide*.xml` (speaker notes often contain the real content).
4. **Validate extraction sufficiency**
   - If text is still sparse, treat the file as “needs manual sampling” rather than forcing a default category.
## Expected Result
You can consistently extract enough PPTX text (including notes) to classify the presentation by subject without modifying the PPTX.
