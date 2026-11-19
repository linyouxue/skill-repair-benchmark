# lab-unit-harmonization

Reusable tooling and references for harmonizing mixed-unit clinical lab panels.

## What this skill provides

- A feature reference with expected ranges and common unit conversions:
  - `reference/ckd_lab_features.md` (human-readable)
  - `reference/ckd_lab_features.json` (machine-readable)
- A stdlib-only harmonization script:
  - `harmonize_ckd_labs.py`

## Usage (example)

```bash
python3 skills/lab-unit-harmonization/harmonize_ckd_labs.py \
  --input /path/to/input.csv \
  --output /path/to/output.csv \
  --id-column patient_id \
  --strict
```

Notes:
- `--reference` is optional; by default the script uses the bundled
  `reference/ckd_lab_features.json` next to the script.
- Always write to the exact output path requested by your task/prompt.

## Design notes

- **Missing values**: rows with any missing/unparseable numeric value are dropped.
- **Parsing**: handles scientific notation, comma decimals, thousands separators,
  and strips stray unit characters.
- **Unit harmonization**: range-based; tries feature-specific conversion factors
  first, then a small set of generic power-of-10 multipliers as a last resort.
- **Output formatting**: all numeric values are written with exactly two decimals
  (e.g., `12.34`).

This bundle intentionally avoids hard-coding any task instance paths or outputs.
