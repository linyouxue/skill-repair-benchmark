---
name: pptx
description: Presentation (.pptx) inspection and targeted edits via OOXML/ZIP, including
  embedded objects (e.g., Excel workbooks), while keeping everything else unchanged.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. If you only need slide text, extract with `python -m markitdown file.pptx`; otherwise treat the PPTX as a ZIP archive and inspect members (e.g., `ppt/slides/slide*.xml`, `ppt/embeddings/*`).
2. For embedded Excel tables, locate the embedded workbook under `ppt/embeddings/` (commonly `Microsoft_Excel_Worksheet.xlsx`) and extract that single file for editing.
3. If an update value is provided in a nearby text box, parse the relevant `ppt/slides/slideN.xml` text runs (`a:t` nodes) to read the updated rate.
4. Edit only the extracted embedded workbook (see **xlsx** skill), then prepare to replace only that ZIP member in the PPTX.
5. Repack the PPTX by copying all ZIP entries byte-for-byte except the updated embedded workbook entry; preserve per-entry ZIP metadata (at least `compress_type`, plus filename/date/flags) so packaging characteristics (compression mix and file size profile) remain consistent with the input.
6. Verify the output PPTX: same ZIP entry count as input, compression-type distribution matches the original, and the embedded workbook contains the updated value while formula cells remain formulas.
7. Terminal/tool usage: issue **one shell command per tool call**, or explicitly chain commands (e.g., `cmd1 && cmd2`) rather than sending multiple separate commands in a single call.
## Expected Result
A new PPTX is produced with only the intended embedded workbook change applied; all other slide content and ZIP packaging characteristics remain unchanged.
