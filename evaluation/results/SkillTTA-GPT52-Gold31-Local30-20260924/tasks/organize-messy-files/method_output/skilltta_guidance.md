# SKILL.md

## When to use
Use this skill when you must **organize a large collection of heterogeneous documents** (e.g., PDF/PPTX/DOCX and possibly other file types) into a **fixed set of subject folders**, where the **correct destination is determined by each document’s content** rather than filename alone.  

Before acting, gather:
- The **exact list of target subject folders** (names must match the contract).
- The **root directory** containing the messy files and whether there are existing subfolders.
- The **file types present** and what tooling is available to read content (PDF text extraction, DOCX/PPTX parsing).
- Any constraints: **do not rename files**, **do not modify file contents**, and **every file must end up in exactly one folder** with **no leftovers**.

## Possible Failure Modes
- **Misnaming folders** (wrong casing/underscores) causing misplaced files or extra directories.
- **Leaving files unassigned** (hidden files, uncommon extensions, nested directories overlooked).
- **Accidentally modifying data** (opening and saving Office files, rewriting PDFs, or renaming during move).
- **Classifying using filenames only**, leading to systematic mis-sorts when titles are ambiguous.
- **Inability to extract text** (scanned PDFs, corrupted files, protected Office docs) and failing to handle these gracefully.
- **Copying instead of moving** (or vice versa) when the task expects a single organized set with no duplicates; conversely, moving without a backup when you need recovery.
- **Moving directories or the destination folders into themselves** due to naive directory traversal.
- **Overwriting collisions** when two files share the same name (often from different subfolders) and a move would replace one.
- **Non-deterministic categorization** (e.g., different outcomes run-to-run) without a stable rule for ties/low-confidence cases.
- **Forgetting the “exactly one subject” rule**, e.g., placing one file into multiple folders or leaving a “misc” folder not allowed by the contract.

## Possible procedures
1. **Inventory and safeguards**
   - Enumerate all files to be organized (recursively if the messy directory contains subfolders), excluding the intended destination folders if they already exist.
   - Record a manifest: `(relative_path, filename, extension, size)` to support reconciliation later.
   - Decide on a safety approach:
     - Prefer: move files but keep a manifest + allow rollback; or stage classification results first, then move in one pass.

2. **Create/validate target folder structure**
   - Create the required subject folders at the correct location with **exact names** from the contract.
   - Ensure the organizer does not traverse into these destination folders during classification.

3. **Content extraction strategy (by type)**
   - PDFs: extract text from first N pages (and optionally last page) to capture titles/abstracts; fallback to OCR only if available and necessary.
   - DOCX: extract paragraph text and headings.
   - PPTX: extract slide titles and body text.
   - For unknown/binary formats: attempt minimal metadata inspection; otherwise treat as “unreadable” and route via fallback rules.
   - Normalize extracted text: lowercase, strip punctuation, collapse whitespace.

4. **Classification approach**
   - Build a lightweight **keyword/phrase signal set** per subject (domain terms, hallmark concepts, typical acronyms). Keep it interpretable.
   - Score each document by counting weighted matches (e.g., title/first page gets higher weight than body).
   - Add negative signals if helpful (terms that strongly indicate another category).
   - Decision points:
     - If a clear winner score exceeds a threshold → assign that folder.
     - If tie/low confidence → inspect more text (more pages/slides/sections) or use secondary cues (references, author affiliations, terminology clusters).
     - If still ambiguous, apply the contract’s rule: **each file must go to exactly one folder**, so choose a consistent fallback (e.g., “best available” or a predetermined “catch-all subject” per contract wording).

5. **Plan then execute moves**
   - First produce a **planned mapping**: `source_path -> destination_folder`.
   - Detect name collisions within a destination folder:
     - If collisions exist, do not overwrite silently. Consider keeping original subfolder structure inside the destination (if allowed) or using a safe non-destructive collision-handling approach that still respects “do not change filenames” (e.g., create per-source subdirectories rather than renaming files).
   - Move files using filesystem move operations; ensure you only move files (not directories unless the contract implies otherwise).

6. **Recovery and iteration**
   - Log decisions for hard/ambiguous cases (file path, top keywords found, final folder).
   - If extraction fails for a subset, re-run with alternate extractors or reduced expectations, then apply deterministic fallback so nothing remains unassigned.

## Verification Checklist
- [ ] The output contains **exactly the required folders** with **exact names** (no extras, no typos).
- [ ] **Every original file** from the initial manifest appears in **exactly one** subject folder (no missing files).
- [ ] **No files remain** in the original messy location (except the subject folders themselves and any explicitly excluded system artifacts, if permitted by the contract).
- [ ] **No filenames changed** (byte-for-byte identical names) and **no file contents modified** (spot-check hashes or sizes/timestamps where feasible).
- [ ] No accidental **overwrites** occurred (verify file counts and detect duplicates/collisions handled without data loss).
- [ ] Destination folders do not contain nested copies of themselves (no recursive move mistakes).
- [ ] Ambiguous/unreadable documents were still assigned deterministically, consistent with the “must belong to one subject” rule.
- [ ] If any errors occurred during moving (permissions/locked files), rerun only for failures and re-validate the manifest reconciliation until complete.
- [ ] Ensure the final approach does **not rely on retrieved examples’ specific paths/names/values**; classification rules and folder names come only from the target contract.
