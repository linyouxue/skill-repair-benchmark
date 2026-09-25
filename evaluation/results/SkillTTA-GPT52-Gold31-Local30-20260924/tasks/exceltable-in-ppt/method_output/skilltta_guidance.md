# SKILL.md

## When to use
Use this skill when a PowerPoint (`.pptx`) contains an **embedded Excel worksheet/table** (often as an OLE object) and you must:
- **Extract and read** the embedded sheet’s contents (including headers and formulas).
- **Read a nearby text box** that provides an updated numeric value (e.g., a rate for a specific row/column intersection).
- **Update exactly the relevant input cell** in the embedded workbook **without converting formula cells to constants** (i.e., preserve formulas and only change the intended non-formula value).
- **Re-embed the edited workbook** into the `.pptx` and save a new file with **everything else unchanged**.

Before acting, gather evidence from the target file:
- Which slide contains the embedded Excel object and which shape is the “nearby” text box.
- The text box content format (how it encodes the pair/labels and the numeric value).
- The embedded workbook format (true `.xlsx` payload vs OLE compound binary containing workbook streams).
- The table structure: row/column headers used to locate the correct cell to update.

## Possible Failure Modes
- **Overwriting formulas**: updating a cell that contains a formula (or rewriting formulas as values by using `values_only=True` or copying computed results instead of formulas).
- **Updating the wrong cell**: mis-parsing the currency pair, swapping row/column mapping, or misidentifying headers due to whitespace, casing, or merged cells.
- **Editing the wrong embedded object**: multiple embedded worksheets/charts exist; replacing the wrong `ppt/embeddings/*` part.
- **Breaking the OLE embedding**: saving the workbook in a different format than originally embedded or failing to repack it correctly into the `.pptx`.
- **Accidentally modifying unrelated slide content**: using a library that rewrites large parts of the presentation or changes layout/IDs when saving.
- **Losing number formatting**: writing a float without preserving Excel cell number format (may be acceptable logically but can fail visual/semantic expectations).
- **Locale/parse errors**: commas vs periods, percent signs, or extra text around the numeric value in the text box.
- **Relationship mismatches**: not updating the correct `slideX.xml.rels` relationship chain when identifying which embedding belongs to which shape.

## Possible procedures
### 1) Locate the relevant slide shapes (Excel object + adjacent text box)
- Prefer reading the `.pptx` as a ZIP:
  - Inspect `ppt/slides/slide*.xml` and their `ppt/slides/_rels/slide*.xml.rels`.
  - Identify OLE objects (e.g., `<p:oleObj>` or related relationship types) and the embedding part target (commonly under `ppt/embeddings/`).
- If using a high-level library (e.g., `python-pptx`), still be cautious: many save operations rewrite the whole file. Consider a **surgical ZIP replace** strategy (copy the original `.pptx` and replace only the embedding part).
- To find the “text box next to the table”:
  - Compare shape bounding boxes (x/y/width/height). Select the nearest text box to the OLE object by distance between centers or minimal edge gap.
  - Extract its text runs and normalize whitespace for parsing.

### 2) Parse the updated rate from the text box
- Implement a robust parser:
  - Normalize case, collapse whitespace, strip currency symbols if present.
  - Extract the two labels (row and column identifiers) and the numeric value with a regex that tolerates separators (e.g., `:` `=` `/`).
  - Convert numeric safely (handle commas, trailing punctuation).
- Keep evidence: log/record the extracted `(row_label, col_label, value)` for traceability.

### 3) Extract the embedded Excel payload
- From the identified embedding part (e.g., a `.bin` under `ppt/embeddings/`), detect format:
  - If it starts with ZIP magic (`PK\x03\x04`), it may be an `.xlsx` package embedded directly.
  - Otherwise it may be an OLE Compound File; use an OLE reader (e.g., `olefile`) to locate streams that contain the workbook.
- Write the extracted bytes to a temporary workbook file for editing.

### 4) Read the workbook and locate the target cell by headers
- Use an Excel library that preserves formulas on load/save (e.g., `openpyxl`).
- Load with `data_only=False` so formulas remain intact.
- Identify the table region:
  - Find the header row and header column by scanning for expected label patterns (currency codes or other identifiers).
  - Build a mapping `{header_text -> row_index}` and `{header_text -> col_index}`; normalize header strings (strip, uppercase).
  - Handle merged cells: if a header is merged, use the top-left cell value as the header for the merged region.
- Determine the target cell coordinates from `(row_label, col_label)` mapping.

### 5) Update only the intended non-formula cell
- Before writing:
  - Inspect the target cell’s existing value:
    - If it’s a formula (string starting with `=`), **do not overwrite**. Re-check mapping to ensure you’re not targeting a computed cell.
  - If the intended update cell is non-formula, set its value to the parsed numeric.
- Preserve formatting where possible:
  - Avoid recreating sheets/cells; modify only the existing cell.
  - Do not convert the whole sheet to raw values (avoid patterns like iterating with `values_only=True` for rewrite).

### 6) Save and re-embed without changing anything else
- Save the modified workbook back to bytes.
- Repack the `.pptx` by copying the original ZIP contents and **replacing only** the specific embedding part file with the updated bytes.
  - Keep filenames/paths identical.
  - Preserve other parts unchanged (do not rebuild the entire presentation unless unavoidable).
- Write output to the required path.

### Recovery / debugging tactics
- If the updated value doesn’t appear:
  - Confirm you replaced the correct embedding part (trace from slide rels → ole object → embeddings target).
  - Confirm you edited the correct sheet (embedded workbooks can have multiple sheets).
- If formulas get lost:
  - Ensure `openpyxl` was used with `data_only=False` and you didn’t copy computed results back into formula cells.
- If the PPT becomes unreadable:
  - Validate the resulting file is a proper ZIP and that the replaced part has the expected binary format.

## Verification Checklist
- [ ] Output saved to the exact required location and filename.
- [ ] Only the intended embedded Excel object changed; other slides/shapes/media remain bytewise or visually unchanged (surgical replace approach).
- [ ] The updated rate value appears in the correct row/column intersection (validated by re-opening the embedded workbook and re-checking headers).
- [ ] No formula cells were overwritten or converted to constants:
  - [ ] Cells that were formulas still begin with `=` after the edit.
  - [ ] You did not perform any operation that rewrites the entire sheet as values.
- [ ] The embedded workbook remains readable by Excel/PowerPoint (no corruption; PPT opens cleanly).
- [ ] Parsing is defensible:
  - [ ] Extracted labels and numeric value from the adjacent text box match the text content and were normalized consistently with workbook headers.
- [ ] You did not copy assumptions from unrelated examples; all mapping/paths/identifiers are derived from the current target file’s evidence.
- [ ] If any ambiguity exists (multiple candidate text boxes or embeddings), you applied a deterministic tie-break (e.g., nearest by geometry) and revalidated by checking that the resulting workbook contains the expected headers and table structure.
