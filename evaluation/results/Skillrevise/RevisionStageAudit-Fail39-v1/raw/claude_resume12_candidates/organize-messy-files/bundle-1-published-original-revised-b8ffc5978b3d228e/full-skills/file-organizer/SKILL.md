# Content-Based File Classifier

## Purpose
Sort a set of documents into a caller-provided set of semantic categories by reading each file's content, scoring it against each category, and moving it into the matching destination folder with pre/post verification.

## When to Use
Use when the task gives (a) a source directory of mixed documents and (b) a fixed list of destination category folders defined by subject or topic, and requires each file to be routed to the correct category based on its contents. Do not use for generic cleanup, duplicate detection, or type/date-based organization.

## Procedure
- Discover and validate: list the source directory, record the exact set of destination folder names from the task (do not invent, rename, or add folders), and record `pre_count` of files to classify.
- For each file, extract textual content using the tool appropriate to its format (e.g., `pdftotext` for PDF, unzip + read `word/document.xml` for DOCX, unzip + read `ppt/slides/*.xml` for PPTX, direct read for TXT/MD/HTML). If a tool is unavailable, fall back to filename, path, and any available metadata, and mark the file as low-confidence.
- Classify: build category descriptors from the task's own category names plus any hints given; score each file against every category using keyword and phrase evidence drawn from the extracted text. Pick the top category only if its score is strictly greater than the second-best by a clear margin and strictly greater than zero.
- Low-confidence branch (bounded fallback): if score is zero, tied, or margin is small, re-extract more content (additional pages, headers, references, metadata), then re-score. If still ambiguous, route to a `_review` subfolder (or surface the ambiguous list to the user) rather than defaulting to any fixed category.
- Act: move each confidently classified file into its destination folder. Preserve filenames; do not rename, edit, or delete content.
- Verify: compute `post_count` across destination folders plus `_review`; assert `pre_count == post_count` and that the source directory has no remaining unclassified files. Sample a few files per category and re-check that extracted text supports the chosen label. Report counts per category and any `_review` items.

## Constraints / Pitfalls
- Never default low-confidence or zero-score files to a single category; use the review bucket or ask.
- Use only the destination folder names provided by the task; do not create extra buckets beyond an explicit `_review` for ambiguous items.
- Do not declare success until pre/post counts match and at least a small sample has been re-verified against extracted content.
- Classify by document contents, not by file extension, size, date, or superficial filename tokens alone.
- Skip clarifying questions when the task fully specifies source and categories; proceed autonomously.