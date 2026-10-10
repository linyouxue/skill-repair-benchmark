# OOXML (PPTX/DOCX) Embedded Spreadsheet Update With Verifier-Aligned Checks

## Purpose
Safely modify values or formulas in an Excel workbook that is either a standalone XLSX/XLSM or embedded inside a zip-based OOXML container (PPTX/DOCX), while preserving formulas/formatting and proving the semantic edit is visible in the final produced artifact via concrete, re-open-and-assert verification.

## When to Use
Use this skill when you must update spreadsheet data programmatically and the file may be an OOXML zip (pptx/docx/xlsx) containing embedded workbooks and possibly slide/chart caches that can cause edits to be invisible unless validated and, when required, updated.

## Procedure
- 1) Discovery checkpoint (inputs, environment, and targets)
- Validate inputs: confirm the input path exists and is readable; capture the required output path (if not specified, stop and ask).
- Execution anchor (single command): confirm zip-OOXML and discover candidate members (do not assume paths):
- `python -c "import sys,zipfile; p=sys.argv[1]; print('is_zip',zipfile.is_zipfile(p)); z=zipfile.ZipFile(p); names=z.namelist(); print('embedded_xlsx',[n for n in names if n.lower().endswith(('.xlsx','.xlsm')) and ('embeddings/' in n.lower() or n.lower().startswith(('ppt/','word/')))]); print('slide_xml',[n for n in names if n.lower().startswith(('ppt/slides/','ppt/charts/')) and n.lower().endswith('.xml')])" INPUT`
- Tool availability decision: try importing `openpyxl`. If missing, stop unless the task explicitly allows a non-xlsx downgrade (CSV) that preserves required semantics.
- If no embedded workbook candidates are found for a PPTX/DOCX input, stop and ask whether the data is externally linked or stored only in chart caches.
- 2) Requirement extraction checkpoint (pair/rate/text to edit) with ambiguity stops
- If requirements come from free-form slide text (e.g., currency pairs/rates), parse robustly and gate progress:
- Accept variants like "AAA/BBB", "AAA to BBB", "AAA->BBB" and tolerate extra whitespace/punctuation.
- Validate parse outputs: currency codes must be exactly 3 ASCII letters; rate must parse to a finite positive number.
- If parsing yields zero candidates or multiple plausible pairs/rates, stop and ask for clarification (do not guess).
- Record the intended edit in a minimal, testable form: (base_code, quote_code, numeric_rate, directionality if relevant).
- 3) Workbook targeting checkpoint (prove the correct cell before writing)
- Extract the candidate embedded workbook(s) to memory or a temp location (discovered member name only).
- Load with openpyxl normally (do not use data_only=True for a file you will save).
- Identify the correct cell by discovery, not fixed offsets:
- Search for header-like cells containing 3-letter currency codes; build candidate header rows and header columns.
- Determine the unique intersection cell for (base_code row, quote_code column) or (quote_code row, base_code column), depending on the workbook layout.
- Uniqueness rule: proceed only if exactly one sheet and one cell mapping matches the required pair unambiguously; otherwise stop and ask which sheet/table to edit.
- Pre-write safety check: confirm the target cell is not part of a merged range that would redirect writes; if it is, resolve the true top-left write cell or stop for clarification.
- 4) Write, repack, and final verification checkpoint (in the final output artifact)
- Apply the minimal edit:
- Write a numeric value only if the requirement is a fixed number; write an Excel formula string (leading '=') only if the requirement is a formula.
- Do not remove or rewrite unrelated sheets, styles, or defined names unless explicitly requested.
- Save the workbook to bytes/file and repack the OOXML container by replacing only the discovered member(s) you edited; otherwise copy entries through unchanged.
- When copying zip entries, preserve each entry name and compression method; do not rename or drop members.
- Execution anchor (single command): re-open the final output container, re-extract the exact edited member, reload, and assert the target edit is present:
- `python -c "import sys,zipfile,io; from openpyxl import load_workbook; out=sys.argv[1]; member=sys.argv[2]; sheet=sys.argv[3]; addr=sys.argv[4]; exp=sys.argv[5]; z=zipfile.ZipFile(out); b=z.read(member); wb=load_workbook(io.BytesIO(b),data_only=False); ws=wb[sheet]; v=ws[addr].value; print('member_ok',member in z.namelist()); print('cell',sheet,addr,'value',v,'type',type(v).__name__); assert member in z.namelist(); assert (str(v)==exp) or (isinstance(v,(int,float)) and str(float(v))==exp)" OUTPUT MEMBER SHEET ADDR EXPECTED`
- If the container is PPTX and the task requires slide-visible updates (tables/charts):
- Inspect slide/chart XML members in the final output for the old/new value string. If the old value still appears and the new value does not, treat as not complete and either (a) update the relevant cache member(s) discovered, or (b) stop and report the limitation clearly rather than claiming success.

## Constraints / Pitfalls
- Never proceed past ambiguity: if requirement parsing (pair/rate) or workbook cell mapping is not uniquely identified, stop and ask; do not guess headers, offsets, or currency-to-cell heuristics.
- Never claim completion based only on "output file exists" or "a formula was preserved"; completion requires re-opening the final output artifact and asserting the intended change at the exact discovered member and cell, plus slide/cache reflectance when slide-visible output is required.