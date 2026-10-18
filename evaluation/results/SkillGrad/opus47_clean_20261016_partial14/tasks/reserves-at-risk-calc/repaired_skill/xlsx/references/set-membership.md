# Enumerate Set Membership From Source Data

**When to read this chapter.** Read when a formula or output depends on
*which* items belong to a set — which countries, which columns, which
rows to include / drop / keep — AND any of the following is true: the
candidate set is wide enough that a terminal dump could truncate; a
lookup (XLOOKUP, INDEX+MATCH, VLOOKUP) is used to filter the set,
especially with a wildcard (`*`) or partial-string match; the current
code contains a literal list of member names; **the task describes a
drop/keep rule driven by an in-sheet lookup** (e.g. "use XLOOKUP to
find row X; if a candidate doesn't have X, delete it"). Skip when the
set is a small fixed enumeration explicitly stated in the task text
(e.g. "use exactly these three: X, Y, Z").

The procedure below is **required**, not advisory. The failure modes
this chapter prevents: (a) committing to a membership decision from a
truncated dump or a hard-coded list that was not computed in the
current run; (b) pre-filtering candidates in Python one step upstream
of the lookup the task names as the authoritative decision mechanism.

---

## Step 1 — Dump the full, non-truncated listing

Pandas and openpyxl default to **truncating wide output** with ellipses.
A truncated dump is NOT a valid review. Either disable truncation or
iterate per-cell so every candidate value appears in the trace.

```python
import pandas as pd

# Option A — disable pandas truncation before any dump
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

# Option B — iterate per cell (preferred for openpyxl sheets)
from openpyxl import load_workbook
wb = load_workbook(path, data_only=True)
sh = wb['<sheet>']
for col_idx, cell in enumerate(sh[<header_row>], start=1):
    val = sh.cell(row=<data_row>, column=col_idx).value
    print(f"col {col_idx} ({cell.value!r}): {val!r}")
```

### Runtime branch

- Dump output contains any ellipsis (`...`) or "`[N columns omitted]`" →
  the listing is incomplete; re-run with Option A or Option B above
  before deriving membership.
- Dump output shows every candidate explicitly → proceed to Step 2.

### Verification

Count the printed rows/columns and compare to the sheet's
`sh.max_column` / `sh.max_row`. If the counts differ, the dump is still
truncated — fix the dump before continuing.

---

## Step 2 — Derive the set with an explicit predicate

Membership comes from a Python expression over the dump output — not
from memory, not from a literal list typed from inspection.

```python
# Example: countries that have data in sheet B at row R but not sheet A
headers_a = [c.value for c in sheet_a[<header_row>]]
headers_b = [c.value for c in sheet_b[<header_row>]]
members_a = {h for h, v in zip(headers_a, sheet_a[<data_row>])
             if h is not None and v.value is not None}
members_b = {h for h, v in zip(headers_b, sheet_b[<data_row>])
             if h is not None and v.value is not None}
additional = sorted(members_b - members_a)   # explicit predicate
print("additional members:", additional)     # print for review
```

### Runtime branch — any hard-coded member list present

If the code about to be written contains a literal list
(e.g. `countries = ["X", "Y", "Z"]`, `step3_countries = [...]`,
`kept_names = ["A", "B"]`) that was not assigned from a predicate in
this run, **delete the literal and recompute** from the dump. This is
a hard rule: a literal member list that pre-exists the dump is
unverified.

### Verification

Print the derived set and manually confirm its length matches your
expectation. If the derived set has an unexpected count, inspect the
predicate — the dump may contain `None`, empty strings, or whitespace
values that need a stricter filter (`v.value not in (None, "", 0)`).

---

## Step 3 — Wildcard / partial-string lookups require row-by-row review

When a drop / keep decision depends on `MATCH("*substring*", range, 0)`,
`XLOOKUP("*s*", ...)`, or any INDEX+MATCH against a `.DESC` row or
similar substring field, wildcard matches can **collide silently**
(one needle matches multiple haystacks) or **miss silently** (needle
absent from haystack, returns `#N/A` masked by `IFERROR`).

```python
# Print the lookup result for EVERY candidate before committing.
import pandas as pd
pd.set_option('display.max_rows', None)
results = []
for name in candidates:
    row = run_lookup(name)   # emulate the sheet's XLOOKUP / INDEX+MATCH
    results.append({"candidate": name, "lookup_hit": row})
print(pd.DataFrame(results).to_string(index=False))

# Then derive the kept/dropped set from the printed table:
kept = [r["candidate"] for r in results
        if r["lookup_hit"] not in (None, 0, "", "#N/A")]
dropped = [r["candidate"] for r in results if r["candidate"] not in kept]
print("kept:", kept)
print("dropped:", dropped)
```

### Runtime branch

- Any candidate's `lookup_hit` is `#N/A` or `None` → that candidate is
  a drop; confirm the drop is intentional against the task text.
- Two candidates map to the same `lookup_hit` row → wildcard collision;
  the lookup pattern is too broad. Tighten the pattern (anchor the
  substring, add a disambiguating prefix) and re-run.
- Lookup table has rows that no candidate matched → either the
  candidate list is incomplete (go back to Step 1) or those rows are
  legitimately out-of-scope (confirm against the task).

### Verification

The final kept / dropped lists written into the workbook must appear in
the trace as output of the predicate expression above — NOT as literals
typed into the Python source. If `kept = ["A", "B"]` appears as a
literal assignment anywhere, replace it with the derived expression and
re-run.

---

## Step 4 — In-sheet lookup drives the drop: write-all → lookup → delete

When the task text names an in-sheet lookup as the drop/keep mechanism
— phrasings like *"Use INDEX+MATCH or XLOOKUP to find X. If a candidate
doesn't have X, delete it"* — the lookup is the authoritative decision
mechanism. **It must execute inside the workbook for every candidate at
least transiently.** Pre-filtering the candidate set in Python before
writing erases this mechanism and shifts the output's column / row
layout away from what the evaluator expects.

The required sequence is four steps, in order:

1. **Write ALL candidates** into the destination rows / columns of the
   target STEP. No pre-filtering, no omission. The destination must
   contain every candidate that passed the prior-STEP enumeration.
2. **Write the lookup formula** (XLOOKUP / INDEX+MATCH / VLOOKUP) in
   the designated row for every candidate column (or every candidate
   row, if the layout is transposed).
3. **Run recalc** so the lookup evaluates. Inspect the recalc'd values
   with `load_workbook(..., data_only=True)` to see which candidates
   returned `#N/A` / `None` / `0`.
4. **Delete the no-match rows/columns** from within the workbook, in a
   second write pass. The delete acts on the recalc'd lookup column,
   not on a Python pre-decision.

```python
# ----- Correct sequence: write-all → lookup → recalc → delete -----
from openpyxl import load_workbook
import subprocess, json

# Step 4.1 — write ALL candidates (from Step 2 enumeration)
wb = load_workbook(target_path)
sh = wb['<answer_sheet>']
for col_idx, name in enumerate(all_candidates, start=<start_col>):
    sh.cell(row=<name_row>, column=col_idx, value=name)
    # … write every candidate's upstream values into their column …

# Step 4.2 — write the lookup formula for every candidate column
for col_idx in range(<start_col>, <start_col> + len(all_candidates)):
    col_letter = sh.cell(row=1, column=col_idx).column_letter
    sh[f'{col_letter}<lookup_row>'] = (
        f'=IFERROR(INDEX(<src>!<range>, MATCH({col_letter}<name_row>, '
        f'<src>!<key_range>, 0)), "")'
    )
wb.save(target_path)

# Step 4.3 — run recalc so the lookup evaluates
subprocess.run(['python', 'recalc.py', target_path], check=True)

# Step 4.4 — inspect recalc'd lookup values, then delete no-match columns
wb_vals = load_workbook(target_path, data_only=True)
sh_vals = wb_vals['<answer_sheet>']
no_match_cols = []
for col_idx in range(<start_col>, <start_col> + len(all_candidates)):
    v = sh_vals.cell(row=<lookup_row>, column=col_idx).value
    if v in (None, "", 0):
        no_match_cols.append(col_idx)
print("deleting (no 2025 data):", no_match_cols)

wb = load_workbook(target_path)   # re-open writable (not data_only)
sh = wb['<answer_sheet>']
for col_idx in sorted(no_match_cols, reverse=True):   # right-to-left
    sh.delete_cols(col_idx)
wb.save(target_path)
subprocess.run(['python', 'recalc.py', target_path], check=True)
```

### Runtime branch

- The task text contains "if X doesn't have Y, delete it" / "use
  XLOOKUP to find Y, delete if missing" → the four-step sequence
  above is required.
- The task text just says "include only countries with Y data" with no
  lookup mechanism named → Step 3 (Python-side predicate on lookup
  emulation) is sufficient; the four-step in-sheet sequence is not
  required.
- Only one candidate exists → the sequence still applies; a trivial
  layout is still a layout the evaluator may check.

### Verification

After the delete pass, re-read the destination range and confirm two
things:

```python
wb_check = load_workbook(target_path, data_only=True)
sh_check = wb_check['<answer_sheet>']
# (a) every remaining candidate column has a non-empty lookup value
for col_idx in range(<start_col>, sh_check.max_column + 1):
    v = sh_check.cell(row=<lookup_row>, column=col_idx).value
    assert v not in (None, "", 0), f"col {col_idx} should have been deleted"
# (b) the count of remaining columns matches len(all_candidates) - len(no_match_cols)
expected = len(all_candidates) - len(no_match_cols)
actual = sum(1 for c in range(<start_col>, sh_check.max_column + 1)
             if sh_check.cell(row=<name_row>, column=c).value)
assert actual == expected, f"delete mismatch: {actual} vs {expected}"
```

If (a) fails, a `#N/A` or empty column survived the delete — re-run
Step 4.4 against the recalc'd values. If (b) fails, either the delete
loop ran out-of-order (deleting left-to-right shifts indices) or an
extra column was deleted — re-run the delete loop right-to-left (as
shown above).

### Anti-pattern (what NOT to do)

```python
# WRONG — pre-filter candidates in Python before writing anything.
# This erases the lookup the task names as the decision mechanism and
# shifts the output's column layout.

all_candidates = ["A", "B", "C", "D"]
# Agent inspects source data and decides C, D have no 2025 Total Reserves:
kept_candidates = ["A", "B"]           # <-- hard-coded pre-decision
for col_idx, name in enumerate(kept_candidates, start=<start_col>):
    sh.cell(row=<name_row>, column=col_idx, value=name)
    # … lookup formula is now only written for A and B; C and D never
    # enter the sheet; the evaluator's expected layout includes C and D
    # columns (at least transiently) and the lookup result in their
    # row, so the output no longer matches.
```

The anti-pattern's tell is: a `kept = [...]` or `step3_countries =
[...]` literal appearing before any sheet write, with values that
came from inspection rather than from a lookup formula result in the
same run.

---

## Step 5 — State ordering before writing

Set membership is unordered; the spreadsheet is ordered. Before writing,
pick and state the ordering convention explicitly:

- Alphabetic by member name.
- Source-sheet column order (preserve the order they appear in the dump).
- Evaluator-expected order (if the task gives a sample row or template).

```python
# Example — alphabetic within sheet-order groups:
value_members = [h for h in headers_value_in_order if h in all_members]
volume_only = sorted(all_members - set(value_members))
final_order = value_members + volume_only
print("writing in order:", final_order)
```

### Verification

Before `wb.save(...)`, print the final ordered list AND the list as it
appears in the target column of the sheet after writing. The two must
be identical. If they differ, the write loop skipped or re-ordered
members — fix before saving.
