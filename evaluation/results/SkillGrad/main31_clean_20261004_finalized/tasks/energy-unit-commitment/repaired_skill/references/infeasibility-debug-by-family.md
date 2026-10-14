# Infeasibility Debugging By Constraint Family (MILP)

Use this when a MILP returns infeasible (or no incumbent), especially when the LP relaxation is feasible. The goal is to identify *which constraint family* creates the contradiction, then fix the formulation rather than guessing.

## Step 0 — Minimal reproduction and snapshot

- Freeze the exact input data snapshot and your variable map.
- Record solver status/message, and whether `result.x` exists.
- Save a copy of constraint-family toggles so each solve is comparable.

## Step 1 — Branch: LP relaxation feasible?

```python
import numpy as np
from dataclasses import dataclass

@dataclass
class SolveResult:
    status: str
    x: np.ndarray | None
    obj: float | None

def solve_model(*, integrality_on: bool, families_enabled: dict[str, bool]) -> SolveResult:
    # Placeholder: call your solver, using families_enabled to include/exclude rows.
    raise NotImplementedError

families = {
    "bounds_and_domains": True,
    "balance": True,
    "linking_transitions": True,
    "min_up_down": True,
    "ramp_start_stop": True,
    "reserve_deliverability": True,
    "tier_logic": True,
}

lp = solve_model(integrality_on=False, families_enabled=families)
if lp.status != "optimal":
    print("Branch A: LP relaxation not feasible/optimal -> debug numeric/bounds/balance first")
else:
    print("Branch B: LP relaxation feasible -> prioritize integer/logic families")
```

### Branch A — LP relaxation not feasible

Focus on: wrong bounds (sign/index), missing balance term, inverted min/max, unit mismatch. Fix these before investigating integer logic.

### Branch B — LP relaxation feasible but MILP infeasible

Continue with isolation / slack diagnosis below.

## Step 2 — Family isolation by disable/enable (runtime branch)

Run a baseline MILP solve first, then disable one family at a time.

```python
base = solve_model(integrality_on=True, families_enabled=families)
assert base.status == "infeasible", "This procedure is for infeasible MILPs"

culprits = []
for fam in [k for k in families.keys() if k not in ("bounds_and_domains", "balance")]:
    test_fams = dict(families)
    test_fams[fam] = False
    trial = solve_model(integrality_on=True, families_enabled=test_fams)
    if trial.status != "infeasible":
        culprits.append(fam)

print("Families whose removal restores feasibility:", culprits)
```

Interpretation:
- If disabling *one* family restores feasibility, that family likely contains the contradiction (or interacts tightly with another family).
- If no single family fixes it, try disabling pairs: `(min_up_down + linking_transitions)`, `(ramp_start_stop + reserve_deliverability)`, `(tier_logic + linking_transitions)`.

## Step 3 — Slack-per-family diagnosis (alternative branch)

Instead of toggling families, add explicit nonnegative slacks to each family and penalize them heavily.

```python
def solve_with_slacks(*, penalty: float) -> tuple[SolveResult, dict[str, float]]:
    # Placeholder: extend your model with slacks per family and return slack usage.
    raise NotImplementedError

res, slack_usage = solve_with_slacks(penalty=1e6)
print("Total slack used by family:")
for fam, amt in sorted(slack_usage.items(), key=lambda kv: -kv[1]):
    print(f"  {fam}: {amt:.6g}")
```

Decision rule:
- If a single family dominates slack, fix that family first.
- If multiple families use slack, fix the one closest to integrality/transition logic (often linking/min-up-down/ramp-start-stop) before capacity/balance.

## Step 4 — Fix in the smallest consistent UC core

When the culprit set includes tier/heuristic logic, remove it until the base UC is feasible, then reintroduce one feature at a time:
1) bounds + balance
2) commitment + linking
3) min up/down
4) ramp with start/stop coupling
5) reserve deliverability
6) tiers / startup lags

## Verification (required) + corrective action on failure

After applying a fix, rerun three checks:

```python
milp = solve_model(integrality_on=True, families_enabled=families)
if milp.status == "infeasible" or milp.x is None:
    raise RuntimeError(
        "Still infeasible: rerun Step 2 (pairwise disable) or Step 3 (slack) "
        "to refine the culprit set before editing more constraints."
    )

lp2 = solve_model(integrality_on=False, families_enabled=families)
if lp2.status != "optimal":
    raise RuntimeError(
        "LP relaxation became infeasible: you likely introduced a sign/index/bounds bug; "
        "re-check Step 0 sanity + bounds/balance rows."
    )

print("Feasible incumbent found; proceed to extraction + independent validation.")
```

If the MILP is feasible but post-extraction validation fails, treat it as either (a) a missing constraint family in the model, or (b) a conversion bug; add the missing family or align extraction to the modeled convention, then revalidate.
