# Trace the Labeled Dependency Chain Before Coding

**When to read this chapter.** Read when the task description contains any
ambiguity-signal phrase — "exposure", "shock", "annualized", "near-term",
"monthly", "quarterly", "N-period X", "volatility applied to", "latest",
"most recent", "replicate X from Step N" — OR when the template defines
any labeled intermediate cell (a named upstream cell that downstream rows
are likely to consume), OR when the current STEP writes more than one
formula referencing upstream labeled cells, OR when any formula references
a cell by row index whose year / period must be known. Skip when the task
is a direct one-step calculation with no intermediate cells and no
multi-reading phrases.

The procedure below is **required**, not advisory. Each step produces a
visible artifact (a comment block or an assertion) **per formula row** —
one artifact above each row's write line. A single pre-STEP block covering
several rows does not satisfy the per-row requirement; see the "Plan Per
Row Before Writing" section of SKILL.md.

**Picker priority (read this first).** When choosing which upstream cell a
downstream formula consumes, apply these rules **in order**; stop at the
first rule that selects a unique cell. **Rule 0 is primary** — the family's
σ convention determines the periodicity of σ, and rules 1–3 narrow among
the family-compatible candidates.

0. **Formula-family classification (primary).** Before any label match,
   classify the surrounding formula shape and import that family's
   σ-periodicity convention from the **Formula Family Index** below. The
   family convention binds σ periodicity; the task phrase's horizon
   qualifier then describes a different quantity (usually the exposure's
   horizon or the position's period) and becomes a tiebreaker among
   family-compatible candidates — **never a reason to override the family
   convention**.
1. **Horizon-qualifier label match (tiebreaker).** Among candidates whose
   periodicity matches the family convention, if the task phrase contains
   a horizon qualifier (*near-term*, *monthly*, *3-month*, *quarterly*,
   *annual*, *annualized*, *N-period*), the chosen cell's LABEL must
   contain the matching qualifier. **Rebuilding the matched quantity by
   applying a scaling factor (`× √(k/K)`, `/ √(K/k)`) to a mismatched
   upstream cell is a hard reject** — reference the label-matched cell
   directly.
2. **Oracle match (secondary; MANDATORY in the irreducible-ambiguity
   case).** If a reference value exists (template pre-fill, example cell,
   expected-result row), compute each remaining candidate and keep the
   one matching the oracle within tolerance. **Mandatory** whenever the
   family is VaR shock AND both raw and annualized labeled σ cells exist
   upstream — this is the case where family-convention and
   horizon-qualifier literalism can superficially conflict. If no oracle
   is available in that case, state the conflict explicitly in the plan
   comment and prefer the family convention; do not silently resolve by
   literalism.
3. **Orphan-avoidance (tiebreaker only).** When — and only when — exactly
   one candidate remains after rules 0–2, prefer the candidate that
   consumes a labeled intermediate. **Never the primary reason.** When the
   upstream STEP defines multiple labeled intermediates in the same
   semantic family (e.g. raw σ at C4 AND annualized σ at C5), orphan-count
   is symmetric and this rule MUST NOT be invoked.

---

## Formula Family Index

Classify the surrounding formula shape BEFORE picking a σ cell. Each
family carries a fixed σ-periodicity convention from its domain.

| Family                | Formula shape                     | σ convention              | Horizon qualifier in task phrase describes |
|-----------------------|-----------------------------------|---------------------------|--------------------------------------------|
| VaR shock             | `reserves × Z × σ`, `pos × Z × σ`, any `Z × σ × V` | **ANNUALIZED**            | the exposure's horizon (NOT σ's period)    |
| Carry / period return | `pos × σ_period` (no Z factor)    | **period-matched** to pos | the position's period (matches σ)          |
| Option greek          | `vega × σ × √t`, `delta × σ × √t` | **ANNUALIZED**            | the option's horizon `t`                   |
| Covariance product    | `ρ × σ_a × σ_b`, `cov(a, b)`      | **both ANNUALIZED**       | n/a                                        |
| Direct arithmetic     | sum / difference / ratio, no σ    | n/a                       | n/a                                        |

**Why VaR shock → annualized σ.** `Z` is a one-sided quantile of the
standard normal, applied in the VaR convention to an annualized vol to
produce an annualized shock. The task phrase's horizon qualifier (e.g.
"near-term") describes the exposure's HORIZON (how far forward the shock
is projected), not σ's periodicity. Using a raw-period σ (e.g. 3-month σ
directly) in a `Z × σ × V` formula understates the shock by `√(12/k)`
relative to the annualized convention.

**Why carry → period-matched σ.** A `position × σ_period` return has no Z
factor and no annualization operator; σ must be in the same units as the
holding period of the position. Here "3-month σ" is the correct σ for a
3-month return.

---

## Step 1 — Required artifact: candidate-enumeration comment

Before writing a formula whose phrasing admits more than one math reading,
emit the following comment block **immediately above that row's write
line**. Minimum two candidates. The `Reason` line must cite picker rules
in priority order — the family convention first, then the tiebreaker.

```python
# AMBIGUITY: "<verbatim task phrase>"
# Family: <VaR shock | carry/return | option greek | covariance | direct>
#   → σ convention: <annualized | period-matched | n/a>
# Horizon qualifier in phrase: <near-term|monthly|annualized|...|none>
#   → describes: <exposure horizon | σ period | option horizon | n/a>
# Candidates (restricted to family-compatible periodicity):
#   A = <expression A>   # upstream label: "<label of A>"
#   B = <expression B>   # upstream label: "<label of B>"
#   C = <expression C>   # upstream label: "<label of C>"
# Chosen: <A|B|C>
# Reason: rule 0 family=<F>, σ convention=<P>;
#         rule 1 label-text match on "<qualifier>"  (or rule 2 oracle match)
sheet['<ref>'] = '=<chosen formula>'
```

### Runtime branch

- Family=VaR shock AND exactly one labeled σ cell matches the annualized
  periodicity → pick it. If the task phrase has a horizon qualifier, that
  qualifier describes the exposure horizon, not σ; it does NOT reject the
  annualized σ.
- Family=VaR shock AND two labeled σ cells (raw AND annualized) exist
  upstream → this is the **irreducible-ambiguity case**: proceed to Step 3
  oracle check (mandatory). The family convention points to the annualized
  cell; horizon-qualifier literalism must NOT override. If no oracle is
  available, state the conflict in the `Reason` line and pick the
  annualized σ per family convention.
- Family=carry/return → pick the σ cell whose label matches the position's
  period (3-month position → "3-month σ"); horizon qualifier here is a
  genuine σ-period cue, not an exposure-horizon cue.
- Phrase contains a horizon qualifier but the only candidate "fitting"
  it is a rebuild (`σ_mismatched × scaling_factor`) → **reject the
  rebuild**. Re-scan upstream for the label-matched cell. If no such cell
  exists, the formula builds from raw inputs (returns, prices).
- Phrase is unambiguous AND family has a trivial σ decision → write a
  one-line note (`# unambiguous: <phrase> → <expr>`) and skip to Step 2.

### Verification

Re-read the emitted `Reason` line. If it cites "label-text match on
near-term" when the family is VaR shock and both raw and annualized σ
cells exist upstream, the step failed — rule 0 (family convention)
mandates annualized σ in a VaR shock; rule 1 is a tiebreaker **inside the
annualized candidates**, not a reason to pick a raw-period cell. Re-run
Step 1 with Step 3 oracle check or with the family convention as the
decisive rule. If the chosen formula applies a scaling factor to recover a
quantity a sibling labeled cell already provides, re-run Step 1 with the
label-matched cell as the chosen candidate.

---

## Step 2 — Required artifact: intermediate-to-consumer mapping

For every labeled intermediate cell in prior STEPs, emit one line mapping
it to its intended downstream consumer in the current STEP. This runs
**per formula row, immediately above that row's write line** (or, when a
row consumes multiple intermediates, as a block above that one row).

```python
# Dependency map (prior STEPs → current STEP):
# <cell_ref_1> (<label_1>) → consumed by <cell_ref_dn_1> (<label_dn_1>)
# <cell_ref_2> (<label_2>) → consumed by <cell_ref_dn_2> (<label_dn_2>)
# <cell_ref_k> (<label_k>) → ALLOWED ORPHAN (family mismatch OR label
#                              does not match any downstream phrase;
#                              standalone reported statistic)
```

### Runtime branch — multiple labeled upstream cells in same family

When the upstream STEP defines two or more labeled cells in the same
semantic family (e.g. both raw and annualized σ), apply this rule:

- **Classify the downstream formula's family first** (VaR shock, carry,
  etc.). The family convention binds σ periodicity.
- **Count the downstream consumers.** If the current STEP has fewer rows
  in that semantic family than the upstream STEP has labeled cells, at
  least one upstream cell WILL be an allowed orphan.
- **Pick by family convention first, label-text match second.** In a VaR
  shock, the annualized σ cell is consumed regardless of a "near-term" /
  "monthly" / "3-month" phrase in the downstream row (that phrase
  qualifies the exposure horizon). In a carry/return formula, the σ cell
  matching the position's period is consumed. The unmatched labeled cell
  is an allowed orphan — mark it `ALLOWED ORPHAN` in the dependency map.
- **Do not force consumption** of a labeled cell whose periodicity
  contradicts the family convention just to avoid an orphan.
- **Do not rebuild** the family-matched quantity from a mismatched cell
  via a scaling factor. If the family-matched cell exists upstream,
  reference it directly.

### Runtime branch — row-index-to-period verification (cross-sheet)

When a formula references a cell by row index whose period / year must
be known (e.g. "`Value!row 18 is 2025`", "`Volume!row 22 is 2024`"),
confirm the row-to-period mapping **by reading THAT sheet's own label
column (A or B)** before writing. **Do not transfer the mapping by
analogy from a different sheet in the same workbook** — row layouts need
not agree.

```python
# Row-index-to-period verification artifact (one per sheet referenced):
# <sheet>!row <N> target period: <Y>
# Verified by reading <sheet>!A<N> (or B<N>): "<label>"
# Match: <yes|no>  → if no, re-scan this sheet's column A for the row
#                    whose label matches "<Y>" and use that index instead
from openpyxl import load_workbook
wb_check = load_workbook(source_path, data_only=True)
for sheet_name, row_idx, expected_period in cross_sheet_row_refs:
    sh = wb_check[sheet_name]
    label_a = sh.cell(row=row_idx, column=1).value
    label_b = sh.cell(row=row_idx, column=2).value
    print(f"{sheet_name}!row {row_idx}: A={label_a!r} B={label_b!r} "
          f"expected={expected_period!r}")
    assert (str(expected_period) in str(label_a) or
            str(expected_period) in str(label_b)), (
        f"{sheet_name}!row {row_idx} does not label '{expected_period}' — "
        f"re-scan {sheet_name} col A for the correct row before writing")
```

### Runtime branch — "replicate X from Step N" phrasing

When the task says "replicate X from Step N into row R" (or any
copy-across phrasing where Step N is the stated source):

- **Scan every label in Step N** for a semantic match to X. "volatility"
  matches rows labeled "N-period volatility" / "annualized volatility";
  "exposure" matches rows labeled "exposure" / "valuation shock";
  "reserves" matches rows labeled "total reserves" / "reserves ($mm)".
- **Do NOT default to positional adjacency.** If Step N has three rows
  and none is literally labeled X, the answer is the semantically closest
  row by label, not the row whose position is closest.
- If no Step-N label semantically matches X, re-read the task — Step N
  may be the wrong source, or X may be a derived quantity to compute.

```python
# "replicate X from Step N into row R" — label-scan artifact:
# X = "<task phrase for the quantity>"
# Step N labels:
#   row N1: "<label>"   → semantic match to X? <yes|no>  (why)
#   row N2: "<label>"   → semantic match to X? <yes|no>  (why)
#   row N3: "<label>"   → semantic match to X? <yes|no>  (why)
# Chosen source row: <N_k>
# Reason: label "<label of N_k>" semantically matches "<X>"
sheet['<ref_R>'] = f"={source_sheet}!{N_k_ref}"
```

### Runtime branch — "latest" / "most recent" phrasing

When the task says "latest data point", "most recent observation", or
similar, do NOT accept a pre-filled template date / label as
authoritative — the template may lag the source file.

- **Inspect the source file's actual last non-null row** of the
  relevant series. Iterate from the bottom up until a non-null value
  is found.
- Compare that date / index to any pre-filled template row. If they
  differ, the source file is the authority.
- Record both values in the plan comment so the choice is reviewable.

```python
# "latest X" — source last-non-null artifact:
import pandas as pd
df = pd.read_excel(source_path, sheet_name='<sheet>')
series = df['<col>'].dropna()
latest_idx = series.index[-1]
latest_label = df.loc[latest_idx, '<date_col>']
template_label = sheet['<pre_filled_cell>'].value
# Record: template={template_label}, source last={latest_label}
assert latest_label == template_label or <template-extension-written>
```

### Runtime branch — single labeled intermediate per family

- Every labeled intermediate has a downstream consumer (1:1): proceed to
  write formulas, using the mapped references directly.
- A labeled intermediate has no obvious consumer and no label-text match
  to any downstream phrase: mark `ALLOWED ORPHAN` and proceed. Do not
  rebuild its value inside a downstream formula.

### Verification (post-write orphan scan)

After writing all formulas in the STEP, scan each labeled intermediate.
A cell marked `consumed by <ref>` MUST appear textually in that formula;
a cell marked `ALLOWED ORPHAN` MAY be absent from all downstream formulas.

```python
mapping = {
    "<cell_ref_1>": ("<label_1>", "<downstream_ref_or_ALLOWED_ORPHAN>"),
    "<cell_ref_2>": ("<label_2>", "<downstream_ref_or_ALLOWED_ORPHAN>"),
}
downstream_formulas = [sheet[c].value for c in downstream_cells
                       if isinstance(sheet[c].value, str)
                       and sheet[c].value.startswith("=")]
violations = []
for ref, (label, consumer) in mapping.items():
    if consumer == "ALLOWED_ORPHAN":
        continue
    if not any(ref in f for f in downstream_formulas):
        violations.append((ref, label, consumer))
assert not violations, f"mapped-but-unconsumed: {violations}"
```

If the assertion fires, rewrite the specific downstream formula to
reference the mapped cell; do not re-classify a `consumed by` entry as
`ALLOWED ORPHAN` to silence the check.

---

## Step 3 — Oracle check (MANDATORY in VaR shock + two labeled σ case)

**Mandatory trigger.** Run Step 3 whenever (family=VaR shock) AND
(upstream STEP has both a raw-period labeled σ cell AND an annualized
labeled σ cell). This is the irreducibly ambiguous case where family
convention and horizon-qualifier literalism can superficially conflict;
literalism alone is insufficient — the oracle check locks the family
convention empirically.

Optional (but recommended) otherwise.

A reference value is any of: a template pre-fill in the target cell, an
example value in a note or neighboring cell, an expected-result row the
task provides, or a prior sheet row whose relationship to the current
cell is known.

```python
# Oracle check — compute each candidate's value, compare to reference
reserves, Z, sigma_period, sigma_annualized, k = <load inputs>
candidates = {
    "A_period_sigma":  reserves * Z * sigma_period / 100,
    "B_annualized":    reserves * Z * sigma_annualized / 100,
    "C_rebuilt":       reserves * Z * sigma_annualized * (k / 12) ** 0.5 / 100,
}
oracle = <reference value from template / example / prior row>
tol = max(abs(oracle) * 0.01, 1e-6)
matches = {name: abs(v - oracle) <= tol for name, v in candidates.items()}
print(matches)
```

### Runtime branch

- Exactly one candidate matches within tolerance → commit to it; record
  the match in the Step 1 `Reason` line as "rule 2 oracle match".
- Multiple candidates match → tolerance too loose; tighten `tol` or fall
  back to rule 0 (family convention).
- No candidate matches AND no oracle value is available → fall back to
  rule 0 (family convention). **Never** fall back to orphan-avoidance;
  **never** let horizon-qualifier literalism override the family
  convention in a VaR shock.
- No candidate matches BUT an oracle value IS available → the candidate
  list is incomplete; return to Step 1 and add candidates. Common misses:
  off-by-100 percent conversion, missing `/sqrt(k)`, transposed
  numerator/denominator.

### Verification

After committing, recompute the chosen formula's value one more time
and re-check `abs(computed - oracle) <= tol`. If it fails post-commit
(e.g. because a cell reference pointed to the wrong column), the
formula is wrong — fix the reference and re-run the check before saving.

---

## Worked example — VaR shock with "near-term" phrase and two labeled σ cells

```python
# Context: STEP 1 writes TWO labeled σ intermediates:
#   Cp = raw period sigma           (label: "<N>-period volatility", k=N months)
#   Ca = annualized period sigma    (label: "annualized <N>-period volatility")
# STEP 2 row R computes an "<asset> near-term valuation swing" with formula
# shape `reserves × Z × σ`. Only ONE downstream row references a σ, so
# one of Cp / Ca WILL be an allowed orphan.

# Step 1 artifact (per-row, above the row R write line):
# AMBIGUITY: "<asset> near-term valuation swing"
# Family: VaR shock (shape = reserves × Z × σ)
#   → σ convention: ANNUALIZED
# Horizon qualifier in phrase: "near-term"
#   → describes: EXPOSURE horizon (how far forward the shock is projected),
#     NOT σ's periodicity. Does NOT reject the annualized σ.
# Candidates (restricted to family-compatible periodicity = annualized):
#   B = reserves * Z * Ca / 100                    # label: "annualized ..."
# Non-family candidates (rejected by rule 0):
#   A = reserves * Z * Cp / 100                    # label: "<N>-period volatility"
#     → REJECT: Cp is raw period σ; VaR convention requires annualized.
#   C = reserves * Z * Ca * SQRT(N / 12) / 100     # rebuilds Cp from Ca
#     → REJECT: rebuild is a hard reject under rule 1 even if a raw σ were
#                family-compatible.
# Step 3 oracle check (MANDATORY: VaR + both Cp and Ca exist upstream):
#   Compare B vs A against any available reference; expect B to match.
# Chosen: B
# Reason: rule 0 family=VaR shock → annualized σ (Ca); rule 2 oracle match
#         confirms B. "near-term" in the phrase refers to the exposure
#         horizon, not σ's periodicity.

# Step 2 artifact (per-row, above the row R write line):
# Cp (<N>-period volatility)             → ALLOWED ORPHAN (family mismatch
#                                           with VaR shock; standalone STEP 1
#                                           reported statistic)
# Ca (annualized <N>-period volatility)  → consumed by row R (near-term
#                                           valuation swing)

sheet[f'<col>{R}'] = f'=<reserves_ref> * <Z_ref> * {Ca_ref} / 100'

# Step 2 verification — mapped-but-unconsumed check passes because row R
# references Ca; Cp is marked ALLOWED ORPHAN so its absence is accepted.
```

### Anti-pattern (what NOT to do)

```python
# WRONG #1: horizon-qualifier literalism overrides family convention in a
# VaR shock. The task phrase says "near-term"; agent picks the raw-period
# σ cell Cp by rule 1 label-text match. This bypasses rule 0 (family =
# VaR shock → annualized σ). Numerically understates the shock by
# √(12/N) relative to the correct annualized shock.
#
# Chosen: A = reserves * Z * Cp / 100       # label match on "near-term"
# Reason: rule 1 label-text match — "near-term" in phrase matches Cp's
#         label "<N>-period volatility".
#         ^^ INVALID — rule 0 is primary. In a `Z × σ × V` VaR shock, σ is
#         annualized by domain convention; the horizon qualifier in the
#         phrase describes the EXPOSURE horizon, not σ's periodicity.
#         Rule 1 is a tiebreaker INSIDE the annualized candidates; it
#         cannot select a raw-period σ in a VaR shock.

# WRONG #2: orphan-avoidance used as primary picker when both Cp and Ca
# are labeled. Both candidates orphan the other; orphan-count cannot
# disambiguate. Rule 0 (family convention) is the picker.
#
# Chosen: B
# Reason: leaving Ca unconsumed would orphan a labeled intermediate.
#         ^^ INVALID as REASON — the correct Reason is rule 0 family
#         convention. (The resulting Chosen cell B happens to be correct
#         for this VaR shock, but under rule 3 reasoning the agent will
#         flip the wrong direction when the family is carry/return.)

# WRONG #3: rebuild one σ from the other via a scaling factor.
#
# Chosen: C = reserves * Z * Ca * SQRT(N / 12) / 100
# Reason: references the labeled intermediate Ca so it is not orphaned.
#         ^^ INVALID — the scaling factor SQRT(N/12) undoes the
#         annualization that produced Ca, re-deriving a quantity equal to
#         Cp. Picker rule 1 requires referencing the family-matched cell
#         (Ca for VaR) directly; rebuilds are hard rejects.
```

---

## Worked example — carry/return with period-matched σ

```python
# Context: STEP 1 writes Cp (3-month σ) and Ca (annualized σ) as above.
# STEP 2 row R computes a "3-month expected carry" with formula shape
# `position × σ_period` (no Z factor).

# Step 1 artifact (per-row):
# AMBIGUITY: "3-month expected carry"
# Family: carry/return (shape = position × σ, no Z)
#   → σ convention: period-matched to the position (= 3-month)
# Horizon qualifier in phrase: "3-month"
#   → describes: σ period (matches the position period)
# Candidates (restricted to family-compatible periodicity = 3-month):
#   A = position * Cp / 100         # label: "3-month volatility"  ✓
# Rejected by rule 0:
#   B = position * Ca / 100         # label: "annualized ..."       → wrong period
# Chosen: A
# Reason: rule 0 family=carry/return → period-matched σ; "3-month" in
#         phrase names the period and rule 1 label-text match selects Cp.

sheet[f'<col>{R}'] = f'=<position_ref> * {Cp_ref} / 100'

# Here Cp is consumed and Ca is the ALLOWED ORPHAN — the opposite picker
# outcome from the VaR shock example above, driven entirely by the
# different family convention.
```
