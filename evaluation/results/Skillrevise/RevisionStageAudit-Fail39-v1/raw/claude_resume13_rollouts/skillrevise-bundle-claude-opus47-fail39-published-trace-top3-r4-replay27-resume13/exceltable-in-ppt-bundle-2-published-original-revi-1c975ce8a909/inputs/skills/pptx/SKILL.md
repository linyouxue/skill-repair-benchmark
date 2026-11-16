# pptx

## Purpose
Reusable procedures for working with PowerPoint (.pptx) files across four distinct task families: (A) reading/analyzing content, (B) authoring new presentations, (C) editing slide XML in an existing deck, and (D) editing an embedded OLE object (xlsx/docx) inside a deck while preserving the container losslessly. A .pptx is a ZIP of XML and resources; different families require different tools and verification gates.

## When to Use
Trigger this skill when the task touches a .pptx file. Route to the correct sub-workflow by the explicit ask: extract text, create a deck, edit slide content/layout, or modify an embedded spreadsheet/document inside the deck. Do not apply authoring/templating guidance to embedded-object edits.

## Procedure
- Classify the task into one family: (A) read, (B) create, (C) edit slide XML, (D) edit embedded OLE object. If unclear, ask or inspect the input first.
- Discover tools and layout before running fixed commands:
- Locate helper scripts under the skill root: `find . -type f -name 'unpack.py' -o -name 'pack.py' -o -name 'validate.py' -o -name 'inventory.py' -o -name 'replace.py' -o -name 'rearrange.py' -o -name 'thumbnail.py' -o -name 'html2pptx.js' 2>/dev/null`.
- If a referenced script is missing, do not invent a path; fall back to the stdlib approach described below for that family.
- Confirm the task-specified output path (e.g., `results.pptx`) exists as a writable location; do not silently switch paths.
- Family A - Read/analyze:
- Text: `python -m markitdown <file.pptx>`.
- Raw XML: unzip the pptx into a temp dir (`unpack.py` if present, else `python -m zipfile -e`). Inspect `ppt/presentation.xml`, `ppt/slides/slide*.xml`, `ppt/notesSlides/*`, `ppt/comments/*`, `ppt/theme/*`, `ppt/embeddings/*`.
- Family B - Create new deck:
- If an authoring doc `html2pptx.md` exists in the skill, read it fully and follow the HTML->pptx workflow with `html2pptx.js` + PptxGenJS. Otherwise fall back to python-pptx.
- Validate visually with a thumbnail grid when a `thumbnail.py` is available.
- Family C - Edit existing slide XML:
- If `ooxml.md` and `unpack.py`/`pack.py`/`validate.py` exist, follow that unpack -> edit XML -> validate -> pack flow.
- Otherwise: unzip with stdlib, edit only the targeted `ppt/slides/slideN.xml`, re-zip preserving every other member byte-identical (see Constraints).
- Do not use python-pptx to round-trip the file if the task requires preserving unrelated structures (comments, embeddings, custom XML).
- Family D - Edit an embedded OLE object (xlsx/docx) inside a pptx:
- Discover: unzip the pptx to a temp dir; list `ppt/embeddings/`; read the owning slide's rels (`ppt/slides/_rels/slideN.xml.rels`) to confirm which embedding corresponds to the target.
- Edit the embedding in isolation:
- For xlsx: open with `openpyxl.load_workbook(path, data_only=False, keep_vba=<match extension>)`. Modify only the target cell(s). Never assign a plain value to a cell whose current value starts with `=` unless the task explicitly asks to replace a formula.
- For docx: use `python-docx` or direct XML edit on the inner document only.
- Repack losslessly:
- Rebuild the pptx by iterating the original zip's `infolist()` in original order. For every member except the edited embedding, copy raw bytes and preserve `compress_type`, `external_attr`, `date_time`, and `flag_bits` (use `ZipInfo` copies, not re-added defaults). For the edited embedding, write the new bytes with the same `compress_type` as the original entry.
- Do not re-order members. Do not re-serialize `[Content_Types].xml`, `_rels/.rels`, or any file you did not intend to change.
- Do not open and re-save the pptx with python-pptx in this family; it rewrites unrelated parts.
- Verification gate (run before declaring done):
- Existence: assert the task-specified output file exists and is a valid zip (`zipfile.is_zipfile(path)`).
- Member parity: `set(out.namelist()) == set(in.namelist())` and order matches.
- Byte parity for untouched members: compare sha256 of every member except the intended target(s); any unexpected diff is a failure, fix the repack path rather than ignoring it.
- Semantic checks for Family D: reopen the embedded xlsx with `data_only=False` and assert (a) the target cell has the new value/formula, and (b) the count and locations of cells whose value starts with `=` match the pre-edit count and locations.
- For Families B/C: if `validate.py` is available, run it against the original.

## Constraints / Pitfalls
- Do not hard-code script paths or commands. Discover scripts locally; fall back to stdlib + openpyxl/python-pptx when absent.
- Write to the exact output path the task specifies. If a write fails, inspect permissions/mounts rather than switching paths.
- Lossless repack rules for any family that must preserve the container: copy `ZipInfo` fields verbatim, preserve member order, preserve `compress_type` and `flag_bits`, and never regenerate `[Content_Types].xml` or `_rels` you did not edit.
- Formula preservation: when editing an embedded xlsx, always load with `data_only=False`; never let openpyxl's calculated-value mode strip formulas; verify formula cell count post-write.
- Scope of edit: change only the files the task requires. A diff of the output zip against the input zip must contain only intended members.
- Keep sub-workflows (color palettes, thumbnail grids, html2pptx details, template rearrange, replace.py JSON schema) in their referenced docs; do not inline them when the task is Family A, C, or D.
- Treat verifier failure after a plausible edit as a container or semantics regression first; re-run the verification gate before re-attempting the content change.