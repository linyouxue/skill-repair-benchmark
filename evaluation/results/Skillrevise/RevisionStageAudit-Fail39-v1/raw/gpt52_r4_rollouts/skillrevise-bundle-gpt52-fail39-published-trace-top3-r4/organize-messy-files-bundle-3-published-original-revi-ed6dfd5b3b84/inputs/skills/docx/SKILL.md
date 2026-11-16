# Bulk Document Triage and Organization

## Purpose
Organize a directory of mixed-format documents (PDF, DOCX, PPTX, TXT, etc.) into subject folders by extracting minimal text/metadata, classifying, moving files safely, and verifying that the final filesystem state matches task requirements.

## When to Use
Use when the task is to sort or reorganize many files into folders (by topic, class, project, date bucket, or similar) and success depends on the final directory structure and file placement. Do not use for editing document contents, tracked changes, or professional redlining (that is a different skill/task family).

## Procedure
- 1) Confirm the contract and the target root (no assumptions)
- Identify the input directory to process and the required output root and folder naming rules from the task statement.
- If the task does not explicitly state the output root, discover likely candidates by listing the current working directory and asking/inferring only from visible structure (do not invent /root or any fixed path).
- Decision point: If folder taxonomy (subjects) is unspecified or ambiguous, stop and request clarification or propose a small set of candidate categories with a plan for an "Unsorted" bucket.
- 2) Environment discovery (choose the lightest viable extractors)
- Discover available tools before planning extraction:
- Check for PDF text tools (pdftotext, pdfinfo).
- Check for office conversion tools (soffice) for PPTX/DOCX-to-text/PDF fallback.
- Check for a Python interpreter for optional parsing.
- Record which tools are available and pick an extraction strategy per extension:
- Prefer CLI tools that are already present.
- Only plan Python library installs if CLI extraction is insufficient for classification.
- 3) Pre-move inventory and manifest (execution anchor)
- Create a manifest in a verifier-visible location under the task-specified output root (or a clearly identified working subdir under that root) containing, at minimum:
- Source relative path (or filename), size, extension.
- Evidence checkpoint: manifest file exists and is readable; total file count is known.
- Strict rule: Do not move or rename any files before this manifest exists.
- 4) Sample-based extraction and classification plan (avoid full-batch mistakes)
- Select a small, representative sample across file types (for example, 5-15 files).
- Extract a short snippet for classification:
- PDFs: pdftotext (first N pages or first K characters) when available.
- DOCX/PPTX: try soffice conversion to text/PDF then extract text; if not available, fall back to filename/metadata-based classification.
- Decision point: If extraction yields empty/garbled text for many files, switch to metadata/filename heuristics or conversion-based extraction; do not proceed to bulk moves until the sample classifications look plausible.
- 5) Dependency fallback (bounded) if Python parsing is required
- If you must use Python libraries (for docx/pptx parsing) and pip install fails due to an externally managed environment:
- Create a local virtual environment in a writable workspace under the task root (for example, <root>/.venv) and install there.
- If venv creation is blocked, stop attempting installs and proceed with CLI-only extraction plus a conservative classification strategy (more items to "Unsorted").
- Strict rule: Keep fallback bounded to one alternate route; do not turn the run into open-ended tool troubleshooting.
- 6) Safe move/organize (reversible first, then commit)
- Create destination subject folders exactly under the required output root (no extra nesting unless explicitly allowed).
- Use a two-phase approach:
- Phase A (dry run): produce a planned mapping (file -> destination folder) in a text file under the root.
- Phase B (apply): move files according to the mapping.
- Constraints during moving:
- Do not overwrite existing files; if a name collision occurs, stop and choose a deterministic disambiguation rule (for example, append a short suffix) and record it in the manifest.
- Move each source file at most once; do not duplicate unless explicitly requested.
- 7) Final audit at the exact output root (execution anchor)
- Re-inventory after moves and verify:
- Every original file from the pre-move manifest appears exactly once in the destination tree.
- No target files remain in the source location (unless the task allows leftovers).
- The destination contains only the expected folder structure plus allowed support files (manifest, mapping); no stray artifacts.
- Evidence checkpoint: a "leftovers" report is empty (or matches allowed exceptions) and counts match the pre-move manifest.
- Only after this audit, declare completion.

## Constraints / Pitfalls
- Never hard-code paths (for example, /root/...) or assume where the verifier looks; always use the task-specified output root or discover it and align all outputs and checks to that exact location.
- Do not claim success based on intent or partial progress: require a post-move audit that proves one-to-one file placement and no leftovers, and stop if requirements (categories, root, naming) are ambiguous.