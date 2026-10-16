# Tooling preflight + file discovery (recover from shell/tool errors)

Use this when you cannot locate/open the workbook, or when an early tool call fails and you have not yet printed `sheetnames`.

## Goal
Regain a working loop where you can (1) locate the workbook file, (2) open it with `python3` + openpyxl, and (3) preview the destination area before doing any planning or edits.

## Procedure (with runtime branches)

### 1) Minimal known-good shell sequence
Run these commands *exactly* (avoid fancy flags, pipes, and complex quoting).

```bash
pwd
ls
find . -maxdepth 6 -type f \( -iname "*.xlsx" -o -iname "*.xlsm" \)
```

- If multiple candidate workbooks exist, prefer the one referenced by the task or the most recent template-like name; otherwise open each candidate and check `sheetnames`.

### 2) Open workbook and print `sheetnames`

```python
from openpyxl import load_workbook
from pathlib import Path

path = Path("input.xlsx")  # replace with a discovered path
wb = load_workbook(path, data_only=False)
print("workbook:", path)
print("sheets:", wb.sheetnames)

# Preview a small area from a likely destination sheet
ws = wb[wb.sheetnames[0]]
print("A1:D5:", [[c.value for c in r] for r in ws["A1:D5"]])
```

### Branch A: shell command failed
Symptoms: `ls: invalid option`, `bash: syntax error`, command returns nonzero.

Corrective action:
1) Re-run *only* `pwd` then `ls`.
2) If that works, re-run the `find` command above exactly.
3) If `find` is still erroring, remove grouping and run:

```bash
find . -maxdepth 6 -type f -iname "*.xlsx"
```

### Branch B: workbook opens but sheetnames are unexpected
Symptoms: opens successfully but you don’t see an expected sheet.

Corrective action:
1) You may have opened the wrong file. Go back to step (1) and open a different candidate.
2) If it is the correct file but sheets are hidden/very hidden, use openpyxl to list sheet states:

```python
for s in wb.worksheets:
    print(s.title, s.sheet_state)
```

### Branch C: openpyxl fails to open
Symptoms: exception like `BadZipFile`, or file is not a real xlsx.

Corrective action:
1) Confirm the path points to an `.xlsx/.xlsm` from `find` and is not a temporary lock file.
2) Try another candidate workbook.

## Verification (and corrective action)

Verification checklist (must pass before proceeding):
1) You have a concrete workbook path.
2) A `python3` run successfully prints `wb.sheetnames`.
3) You have previewed a small cell window in the destination area you will write.

If any verification item fails:
- Do **not** proceed to planning/mapping/formula writing.
- Return to the nearest earlier step (shell discovery or workbook open) and simplify further (fewer flags, shorter commands, smaller scripts) until inspection succeeds.
