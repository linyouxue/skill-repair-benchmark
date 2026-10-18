# Best-run / top-performer ranking

Use this reference when a task asks for the "best run", "top performer",
"recommended run", or "highest-yielding run" per group (board family, oven,
etc.) in a context where per-run compliance verdicts (ramp / TAL / peak /
feasibility) have already been computed. Skip when the task asks only for
a per-run metric with no cross-run selection.

## Why this matters

A strict compliance filter (`ramp_ok AND tal_ok AND peak_ok AND
feasibility_ok` as a hard gate) and a bare quality ranking (yield + throughput
with no compliance signal at all) are both wrong in general. The correct
choice depends on the prompt wording:

- **Strict:** when the prompt scopes "best" explicitly to compliant runs
  ("best **compliant** run", "top performer that meets all specs", "pick
  only runs that pass compliance"), use the hard mask and emit `null` for
  groups with no compliant run.
- **Graded:** when the prompt uses softer language ("best run based on
  **quality and efficiency**", "recommended run", "top performer per
  family"), rank ALL runs in the group by a composite score; compliance acts
  as a tie-break / penalty, not a gate. Emit a non-null top pick whenever the
  group has ≥ 1 run.

The default misreading in both directions:
- iter_0 under-filter: no mask at all → shipped a ramp-violator as "best".
- iter_1 over-filter: hard mask → 4/6 families collapsed to `null` because
  TAL compliance happened to fail 51/60 runs; sanity log read `0/N compliant`
  per family and was ignored.

## Decision procedure

Three inputs:
1. The task prompt — strict scope ("compliant") or soft scope ("quality and
   efficiency")?
2. The per-run compliance mask (built from Q1–Q4 verdicts).
3. The per-group compliant counts: `df.groupby(group_col)[mask].sum()`.

Branches:

- **Branch A — strict scope.** Rank the mask=True subset by the stated
  criterion. If a group has zero compliant runs, emit `best_run_id = null`
  and an empty runner-up list for that group. Document that the prompt
  licensed null.

- **Branch B — soft scope ("quality and efficiency" or unqualified "best").**
  Rank ALL runs in the group by a composite score. Suggested order:
  `fp_yield_pct` desc, then `boards_per_min` desc, then
  `compliance_violation_count` asc (tie-break / penalty), then `run_id` asc
  for determinism. Emit the top run as `best_run_id` and the rest as
  runner-ups in the same order. Only emit `null` when the group has zero
  runs at all.

- **Branch C — ambiguous prompt.** If the prompt wording is unclear AND the
  strict mask would wipe out ≥ 1 group, prefer Branch B and record the
  interpretation in a code comment. A graded answer that still prefers
  compliant over non-compliant runs is safer than a `null` emission.

## Code

```python
import pandas as pd

def rank_best_runs(df: pd.DataFrame,
                   group_col: str,
                   mode: str,                   # "strict" or "graded"
                   quality_cols: list[str],     # e.g. ["fp_yield_pct","boards_per_min"]
                   id_col: str = "run_id") -> dict:
    """
    df must already carry per-run columns:
      ramp_ok, tal_ok, peak_ok, feasibility_ok  (bool)
      <quality_cols...>, <id_col>
    Returns {group_value: {"best_run_id": str|None, "runner_ups": [str,...]}}.
    """
    df = df.copy()
    mask = df["ramp_ok"] & df["tal_ok"] & df["peak_ok"] & df["feasibility_ok"]
    df["_violations"] = (~df[["ramp_ok","tal_ok","peak_ok","feasibility_ok"]]).sum(axis=1)

    out = {}
    for grp, sub in df.groupby(group_col):
        if mode == "strict":
            pool = sub[mask.loc[sub.index]]
            if pool.empty:
                out[grp] = {"best_run_id": None, "runner_ups": []}
                continue
            ordered = pool.sort_values(
                quality_cols + [id_col],
                ascending=[False] * len(quality_cols) + [True],
            )
        else:  # graded
            if sub.empty:
                out[grp] = {"best_run_id": None, "runner_ups": []}
                continue
            ordered = sub.sort_values(
                quality_cols + ["_violations", id_col],
                ascending=[False] * len(quality_cols) + [True, True],
            )
        ids = ordered[id_col].astype(str).tolist()
        out[grp] = {"best_run_id": ids[0], "runner_ups": ids[1:]}
    return out
```

## Verification

Two post-rank checks:

```python
# 1. Compliance-counts sanity: print the per-group compliant totals.
compliant_counts = (mask.groupby(df[group_col]).sum()
                        .to_dict())
print("compliant per group:", compliant_counts)

# 2. Null-emission audit for ranking outputs.
null_groups = [g for g, v in out.items() if v["best_run_id"] is None]
non_empty_groups = [g for g, sub in df.groupby(group_col) if len(sub) > 0]
if null_groups and mode == "graded":
    raise AssertionError(
        f"graded mode must not emit null best_run_id when group has runs: "
        f"{null_groups}"
    )
if mode == "strict" and len(null_groups) >= 0.5 * len(non_empty_groups):
    print(f"[stop] strict mode is emitting null for {len(null_groups)}/"
          f"{len(non_empty_groups)} groups — re-read the prompt and confirm "
          f"strict scope before shipping")
```

**If check 1 shows `0/N compliant` for any group:** stop. Re-read the task
prompt. If the prompt says "compliant" / "meets all specs", keep `mode=
"strict"` and the group's null is justified. If the prompt says "quality and
efficiency" or just "best", switch to `mode="graded"` and re-run.

**If check 2's AssertionError fires in graded mode:** a group with runs
produced `best_run_id=None`. The composite sort failed to include a non-mask
fallback — fix by removing any accidental mask filter inside the graded
branch, then re-run.

**If check 2's `[stop]` print fires in strict mode:** ≥ 50% of groups
collapsed to null. Treat as a prompt-interpretation error until the prompt
wording explicitly licenses this outcome. Flip to graded mode if the prompt
is softer than "compliant-only".
