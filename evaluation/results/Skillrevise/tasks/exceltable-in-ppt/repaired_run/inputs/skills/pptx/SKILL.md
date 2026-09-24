# PPTX Embedded Spreadsheet Update (OOXML)

## Purpose
Safely locate, verify, and update values inside an embedded spreadsheet (OLE/Excel) within a PPTX by discovering which embedding is shown on which slide, finding the associated annotation text, editing only validated non-formula input cells, and repacking with verifier-visible checks.

## When to Use
Use when a task requires changing data shown in a PowerPoint table/chart that is backed by an embedded spreadsheet object (not regular slide text), especially when there may be multiple slides and multiple embedded objects and the correct update must match a nearby label (for example, an "updated rate" text box).

## Procedure
- Step 1: Validate inputs and prepare a reversible workspace
- Confirm you have the PPTX path and the intended output PPTX path/name (do not overwrite the input unless explicitly required).
- Create a temporary working directory and copy the PPTX there.
- Check tool availability by discovery, not assumptions: locate any helper scripts (unpack/pack/validate/thumbnail) with find/ls; if missing, plan to use standard ZIP operations instead.
- Step 2: Discover and map embedded objects to slides (do this before reading any specific slide)
- Unpack the PPTX (via the environment-provided OOXML unpacker if present; otherwise treat it as a ZIP and extract).
- Enumerate candidate embeddings by listing ppt/embeddings/ and noting all parts (do not assume a specific filename).
- For each slide:
- Inspect ppt/slides/_rels/slideN.xml.rels and record any relationships whose Target points into ppt/embeddings/ (or other OLE-related parts).
- Cross-check slide XML (ppt/slides/slideN.xml) for object references that use those rIds.
- Save a short mapping artifact (e.g., mapping.md): slideN -> rId -> Target part path.
- Decision point: If multiple embeddings exist, select the embedding to edit only after also identifying the slide context (next step) rather than choosing the first file.
- Step 3: Select the correct embedding using slide context, then locate the correct editable cell
- On the mapped slide(s), extract all visible text runs from the slide XML and identify the annotation text relevant to the requested update (for example, the text containing the new rate). If multiple candidates exist, prefer those spatially near the embedded object:
- Use shape coordinates in slide XML (x/y extents) to estimate proximity between the embedded object shape and text boxes; do not assume they are on slide1.
- Open the selected embedding only if it is a directly readable workbook format (for example, an .xlsx part). If the embedding is an OLE binary (for example, .bin) and no extractor is available, stop and report the slide->embedding mapping evidence and what additional tooling/input is needed.
- In the workbook, discover the table schema rather than assuming it:
- Search for the requested row/column headers (currency codes/names) across a bounded region (used range or first N rows/cols).
- Determine the intersection cell for the requested pair and direction, and confirm it matches exactly one plausible location.
- Pre-edit checkpoint (mandatory):
- Confirm the chosen write cell is a non-formula input (not a formula string). If it is a formula, do not overwrite it and do not redirect to an "inverse" cell by heuristic. Instead, locate the upstream input cell that drives it (if clear), or stop and request clarification about which input cell is intended.
- Step 4: Apply the minimal change, then ground the result in the packed PPTX
- Write only the validated target input cell(s); keep all other cells unchanged.
- Save the workbook back into the same embedding part path selected in Step 2 (do not create a new random part name unless you also update relationships accordingly).
- Repack the PPTX and run validation if a validator is available.
- Post-edit grounding checks (mandatory):
- Re-open the output PPTX as a ZIP and confirm the specific embedding part path exists and has changed compared to the original (hash/size).
- Re-unpack/read the output embedding and confirm the target cell now contains the intended value and that formula cells remain formulas.
- If thumbnail tooling exists, generate thumbnails to visually confirm the slide showing the object reflects the updated value.

## Constraints / Pitfalls
- Never hard-code slide numbers, embedding filenames, or table header locations. Always discover them via ppt/slides/_rels relationships plus workbook search.
- Never overwrite formula cells and never "fix" by writing an inverse or alternate cell unless you have explicit evidence it is the correct upstream input. If the correct editable input cannot be unambiguously identified, stop and ask for clarification rather than guessing.