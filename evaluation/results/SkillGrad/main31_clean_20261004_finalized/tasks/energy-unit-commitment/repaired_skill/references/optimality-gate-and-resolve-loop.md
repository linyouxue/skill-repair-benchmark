# Optimality gate + re-solve loop for open-source MILP solvers

Use this chapter when the task is scored on objective quality ("economical", "minimize cost") and the solver can stop early with a feasible incumbent (time limit, node limit, gap limit).

## Goal

Do not finalize a grader-facing artifact from a solution that is merely feasible. Require either:

- a solver-reported optimal status, or
- a solver-reported MIP gap at/below an explicitly chosen tolerance that the task accepts.

If neither holds, re-solve with more time and/or stronger settings until the acceptance condition holds.

## Runnable pattern (SciPy `milp`)

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds


@dataclass
class SolveAttempt:
    options: Dict[str, Any]
    status: int
    message: str
    fun: float
    mip_gap: Optional[float]


def solve_with_gate(c, integrality, bounds, constraints, *, gap_tol: float) -> tuple[np.ndarray, SolveAttempt]:
    # A small ladder of increasing effort; extend if needed.
    option_ladder = [
        {"time_limit": 60.0, "mip_rel_gap": gap_tol, "disp": False},
        {"time_limit": 300.0, "mip_rel_gap": gap_tol, "disp": False},
        {"time_limit": 1800.0, "mip_rel_gap": gap_tol, "disp": False},
    ]

    last: Optional[SolveAttempt] = None
    for opts in option_ladder:
        res = milp(
            c=c,
            integrality=integrality,
            bounds=bounds,
            constraints=constraints,
            options=opts,
        )
        if res.x is None:
            last = SolveAttempt(opts, res.status, res.message, float("nan"), None)
            continue

        # SciPy exposes mip_gap when supported by the backend; if absent, treat as unknown.
        gap = getattr(res, "mip_gap", None)
        last = SolveAttempt(opts, res.status, res.message, float(res.fun), None if gap is None else float(gap))

        # Branch A: solver proves optimality (backend-specific status codes; rely on message too).
        msg = (res.message or "").lower()
        is_optimal = ("optimal" in msg) and ("not" not in msg)

        # Branch B: solver didn't prove optimal, but reported gap is good enough.
        gap_ok = (last.mip_gap is not None) and (last.mip_gap <= gap_tol)

        if is_optimal or gap_ok:
            return res.x, last

    raise RuntimeError(f"No accepted solve under gate; last_attempt={last}")


# --- minimal smoke test wiring (replace with a real model) ---
# minimize x subject to x >= 1, x integer
c = np.array([1.0])
integrality = np.array([1], dtype=int)
bounds = Bounds([0.0], [10.0])
constraints = [LinearConstraint([[1.0]], [1.0], [np.inf])]

x, attempt = solve_with_gate(c, integrality, bounds, constraints, gap_tol=0.0)
assert int(round(x[0])) == 1
```

## If you are using HiGHS directly (highspy)

Commonly available signals:

- model/solution status (e.g., optimal vs. time limit),
- best incumbent objective,
- best bound,
- relative gap computed from those.

Implement the same gate:

- **Branch A (accept):** status is optimal.
- **Branch B (accept):** status is feasible but not optimal *and* you can compute/obtain a MIP gap that is ≤ `gap_tol`.
- **Else (reject):** increase time limit and/or tighten options, then re-solve.

## Verification (must pass before writing the final artifact)

1. Record `solver_status`, `objective`, and (if available) `mip_gap` *from the accepted solve*.
2. Check the acceptance condition:
   - `solver_status` indicates optimal, **or**
   - `mip_gap` is known and `mip_gap <= gap_tol`.
3. If step 2 fails: **do not write** the final report; re-enter the solve loop with a higher time limit and/or stronger settings.

## Common corrective actions when the gate fails

- Increase/remove `time_limit`.
- Strengthen the formulation to close the gap faster (tighter linking constraints, avoid overly weak Big-Ms, correct ramp/reserve coupling).
- Provide a warm start from a good incumbent if the interface supports it.
- Switch solver/backends if allowed.
