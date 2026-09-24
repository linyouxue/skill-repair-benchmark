---
name: pdf
description: Extract schema/field definitions from the provided PDF so downstream
  parsing matches the dataset format.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. Extract readable text from the PDF schema doc:
   - Prefer CLI for quick inspection: `pdftotext -layout /app/workspace/data/format.pdf - | less`
   - Or use Python (`pypdf` / `pdfplumber`) when you need programmatic extraction.
2. Identify (and note) for each file type:
   - Column order and data types
   - Time unit (here: microseconds) and any sentinel/null conventions
3. Use the extracted schema to implement/verify CSV parsing logic (indices, numeric parsing, optional fields).
## Expected Result
You can precisely map each CSV column to the correct field (including microsecond timestamps) without guessing.
