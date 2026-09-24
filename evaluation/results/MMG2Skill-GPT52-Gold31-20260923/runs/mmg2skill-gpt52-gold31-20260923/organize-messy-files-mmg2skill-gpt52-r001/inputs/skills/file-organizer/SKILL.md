---
name: file-organizer
description: Organize large mixed file sets into a required folder structure by *document
  content*, with verification that every file is placed exactly once and no strays
  remain.
---

## Steps
1. **Inventory and freeze scope**
   - Locate the target directory; count all candidate files and record extensions.  
   - Capture a manifest (paths + counts) before moving anything.
2. **Create the required folder structure (exact names)**
   - Create destination folders (e.g., `LLM/`, `trapped_ion_and_qc/`, `black_hole/`, `DNA/`, `music_history/`) under the specified root.
3. **Extract content text in a way suitable for classification**
   - Prefer a **single Python driver script** for batch processing (avoids fragile shell pipelines/quoting).  
   - For **PDFs**: extract more than just the first page when needed (start with first ~2–5 pages; escalate if low confidence).  
   - For **DOCX/PPTX**: extract text via `pandoc/markitdown` if available; otherwise fallback to ZIP/XML extraction (OOXML).
4. **Classify with confidence + escalation (don’t “dump” unknowns)**
   - Compute per-subject scores using subject-specific signals (keywords/phrases), but treat results as **provisional**.  
   - If **all scores are 0** or the best score is weak/close to the runner-up:
     - Re-extract with **more text** (more PDF pages; include PPTX notes; include additional DOCX parts).  
     - If still ambiguous, mark the file for **manual sampling** (e.g., print title/abstract lines) and only then assign.  
   - Only use “last folder” logic *after* deeper extraction/manual sampling shows no evidence for the other four subjects; keep a short review log so decisions are auditable.
5. **Move each file exactly once (no renaming, no content edits)**
   - Move (not copy) into exactly one destination folder; handle name collisions by aborting and asking (don’t rename silently).
6. **Post-move verification (must-pass checks)**
   - Recount totals under the new root equals the original manifest count.  
   - Confirm **no stray files** remain outside the five folders.  
   - Optionally remove the now-empty source folder only after counts match.
## Expected Result
All documents are placed into exactly one of the five required folders based on content, with a clear verification that totals match and nothing is left out or misplaced due to “unknown → default” shortcuts.
