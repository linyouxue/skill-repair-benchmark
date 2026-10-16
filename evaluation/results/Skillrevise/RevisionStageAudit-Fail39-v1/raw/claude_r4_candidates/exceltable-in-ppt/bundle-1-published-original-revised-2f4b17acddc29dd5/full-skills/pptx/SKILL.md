# pptx

## Purpose
Work with PowerPoint .pptx files for three task families: (A) read/analyze content, (B) edit slide XML or embedded OLE objects (xlsx/docx/bin) while preserving container integrity, and (C) create new presentations. A .pptx is a ZIP of XML and resources; edits must preserve the container unless the task explicitly rebuilds it.

## When to Use
Trigger when the task involves reading, editing, or creating a .pptx, including edits to objects embedded inside the .pptx (e.g., linked/embedded spreadsheets under ppt/embeddings/). Do not trigger for generic ZIP or XML tasks that are not .pptx. Choose exactly one branch below based on the task; do not execute unrelated branches.

## Procedure
- ### Step 0: Branch selection and discovery (always run)
- Classify the task into one branch: READ, EDIT_SLIDE_XML, EDIT_EMBEDDED_OBJECT, or CREATE.
- Identify the input .pptx path and the task-specified output path. If output path is unspecified, write next to the input with a clearly derived name and record the chosen path.
- Discover helper scripts before using them:
- `find . -maxdepth 8 -type f -name 'unpack.py' -o -name 'pack.py' -o -name 'validate.py' -o -name 'inventory.py' -o -name 'replace.py' -o -name 'rearrange.py' -o -name 'thumbnail.py' -o -name 'html2pptx.js'`
- If a referenced doc exists (`ooxml.md`, `html2pptx.md`), read it only when its branch is selected.
- Record which tools are present. For any missing tool, use the fallback listed in its branch. ### Branch READ: text / structure analysis
- For plain text: `python -m markitdown <file.pptx>`. Fallback if markitdown missing: unzip and read `ppt/slides/slide*.xml`, stripping tags.
- For XML internals (comments, notes, layouts, theme, embeddings): unpack via discovered `unpack.py`; fallback: `python -c "import zipfile; zipfile.ZipFile('<f>').extractall('<dir>')"`.
- Do not modify the file in this branch. ### Branch EDIT_SLIDE_XML: modify slide/notes/comments XML
- Unpack with discovered `unpack.py <file> <dir>`; fallback: `zipfile` extractall into a scratch dir.
- Edit only the targeted XML files (typically `ppt/slides/slideN.xml`, `ppt/notesSlides/*`, `ppt/comments/*`).
- Validate if `validate.py` exists: `python <path>/validate.py <dir> --original <file>`. Otherwise, parse edited files with `defusedxml` to confirm well-formedness.
- Repack with discovered `pack.py`; fallback: see container-preserving rewrite in the embedded-object branch, applied to all members.
- Run the final verification checklist (below). ### Branch EDIT_EMBEDDED_OBJECT: modify files inside ppt/embeddings/ (xlsx/docx/bin)
- List embedded members without extracting the full archive:
- `python -c "import zipfile; [print(n) for n in zipfile.ZipFile('<in>').namelist() if n.startswith('ppt/embeddings/')]"`
- Identify the target member by name hint, slide relationship (`ppt/slides/_rels/slideN.xml.rels`), or content inspection.
- Edit the embedded object in-memory using the right library:
- xlsx: `openpyxl` (preserve formulas: write values only to intended cells; never call `data_only` save; verify formula cells still start with `=` after edit).
- docx: `python-docx`.
- Opaque `.bin` OLE: do not edit unless the task explicitly requires binary surgery.
- Rewrite the .pptx preserving container metadata. Use this pattern: ```python import zipfile, shutil with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w') as zout: for item in zin.infolist(): data = new_bytes if item.filename == target else zin.read(item.filename) # Preserve compression and metadata per member zi = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time) zi.compress_type = item.compress_type zi.external_attr = item.external_attr zi.create_system = item.create_system zi.flag_bits = item.flag_bits zout.writestr(zi, data) ```
- Do not touch `[Content_Types].xml`, `_rels/*`, or any member you did not intend to change.
- Run the final verification checklist (below). ### Branch CREATE: new presentation (from scratch or template)
- Use this branch only when the task is to produce a new deck. Then read `html2pptx.md` (scratch) or template-flow docs (`inventory.py`, `replace.py`, `rearrange.py`, `thumbnail.py`) as needed.
- Do not execute this branch when editing an existing file; its design/palette guidance is out of scope for edits.
- Follow discovered scripts; if absent, fall back to `python-pptx` for minimal programmatic creation. ### Final verification checklist (run for every EDIT branch)
- Output file exists at the task-specified path and is non-empty.
- `python -c "import zipfile; z=zipfile.ZipFile('<out>'); print(z.testzip())"` prints `None` (archive integrity OK).
- Open with python-pptx: `python -c "from pptx import Presentation; Presentation('<out>')"` succeeds without exception.
- Member-level diff: for every member name in the input, assert the output has the same name and that CRCs match for all members except the intended target(s): ```python import zipfile a={i.filename:i.CRC for i in zipfile.ZipFile(src).infolist()} b={i.filename:i.CRC for i in zipfile.ZipFile(dst).infolist()} diff=[k for k in a if a[k]!=b.get(k)] print('changed:', diff) ``` Expect `changed` to contain only the intended file(s).
- Semantic re-check of the edit (e.g., re-open embedded xlsx with openpyxl and confirm target cell value plus that formula cells still begin with `=`).
- If any check fails, do not finalize; inspect, fix the specific cause, and re-run checks before declaring done.

## Constraints / Pitfalls
- Do not hard-code script paths; always discover first and fall back to standard libraries if absent.
- When rewriting the .pptx container, preserve each `ZipInfo`'s `compress_type`, `date_time`, `external_attr`, `create_system`, and `flag_bits`; naive `ZipFile.write` changes compression and can break verifiers.
- Never re-serialize untouched members through XML parsers; copy their raw bytes.
- Do not modify `[Content_Types].xml` or any `_rels/*` file unless the task adds/removes parts.
- When editing embedded xlsx with openpyxl, do not use `data_only=True` for save; it strips formulas. Verify formula preservation explicitly.
- Do not invent output paths. Use the task-specified path; if none, derive one and report it. Confirm existence after writing.
- Trim scope: do not execute CREATE guidance (palettes, html2pptx, thumbnails) during READ or EDIT tasks.
- Read `ooxml.md` or `html2pptx.md` only when the corresponding branch is active and the file exists; otherwise proceed with the documented fallbacks.
- If a referenced helper script errors or is missing, switch to the fallback once and continue; do not loop on the same failing command.
- Keep edits minimal: change only the cells, runs, or members required by the task; leave all other content untouched.