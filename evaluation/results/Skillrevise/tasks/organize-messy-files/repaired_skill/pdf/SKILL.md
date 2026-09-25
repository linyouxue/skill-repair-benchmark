# Document Set Organizer (Content-Based Foldering)

## Purpose
Organize a directory of heterogeneous documents (for example PDF, DOCX, PPTX, and any other discovered file types) into subject-based folders by extracting text, classifying by topic, moving files safely, and verifying that every original file is accounted for.

## When to Use
Use when the task is to sort or reorganize many documents into folders based on their contents (topics/subjects) rather than filenames alone. Do not use for PDF editing tasks (merge/split/watermark/forms) unless those steps are strictly required to enable text extraction.

## Procedure
- 1) Discover and freeze scope (no changes yet)
- Identify the source directory to organize and list all files recursively.
- Create a manifest of every file: relative path, size, and extension; record total count and extension set.
- Checkpoint evidence: a saved manifest (or printed list) and a single total file count to reconcile later.
- 2) Validate environment and pick extractors (bounded fallback)
- For each extension in the manifest, probe available extractors in this order:
- Preferred: existing in-environment Python libraries (only if import succeeds without installing).
- Fallback A: existing command-line tools (only if present in PATH).
- Fallback B: minimal text heuristics (for unknown/binary formats): file metadata + safe strings extraction; treat results as low confidence.
- If package installation is required, first detect whether the environment blocks system installs (for example externally managed Python). If blocked, use a local virtual environment or skip installs and stay with CLI/heuristics; do not assume installs will work.
- Run a minimal extraction test on 1 representative file per extension using the selected method; if it fails or returns empty, switch to the next fallback and re-test once.
- Checkpoint evidence: per-extension selected extractor plus a short non-empty text preview or an explicit note like "no extractable text".
- 3) Extract signals and classify into subjects
- For each file, extract a bounded amount of text (for example first N characters/pages/slide notes) sufficient for topic detection; keep the raw file unchanged.
- Classify into a subject label using consistent rules:
- If confident: assign a single subject folder name (ASCII, filesystem-safe).
- If ambiguous/low text: assign to a clearly named "Needs_Review" or "Unclear" bucket with a short reason (do not guess wildly).
- Decision point: if many files are ambiguous, refine subject labels (merge/split labels) before moving anything.
- 4) Create folders and move files safely
- Create destination folders only after classification is complete (or at least after a stable batch is classified).
- Move files without renaming unless explicitly required; preserve extensions and base filenames.
- Use an atomic strategy: move a small batch, then re-list to confirm the batch moved, then continue.
- Checkpoint evidence: destination folder tree exists and moved-file counts increase as expected.
- 5) Verify accounting (must pass before declaring done)
- Reconcile against the manifest:
- Every original file path is now present exactly once under the destination root.
- No extra files were created or lost (count and total size should be plausible; investigate large discrepancies).
- List any leftover files in the original source directory; either classify and move them or explicitly state why they are excluded.
- Checkpoint evidence: moved count equals manifest total, and leftover list is empty (or explicitly handled).

## Constraints / Pitfalls
- Never delete files, overwrite existing documents, or modify document contents; only read for extraction and move/copy as required.
- Do not hard-code tool names, paths, or versions; always discover what is available first, and use one bounded fallback step per extractor failure (do not spiral into open-ended troubleshooting).