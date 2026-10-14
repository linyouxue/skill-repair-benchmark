# Reserve deliverability parity (derive benchmark definition + validate report arrays)

Use this chapter when the task includes spinning reserve and the evaluator checks **deliverability** (not just that the system reserve sum meets a requirement). The objective is to prevent “verified the wrong thing” failures: your model and your checks must match the benchmark’s definition.

## Step 1 — Write the reserve definition you are targeting

Before coding constraints, make an explicit checklist for each thermal unit `g` and time `t`:

1. **Eligibility (online-only):** whether `u[g,t] == 1` is required for spinning reserve.
2. **Headroom coupling:** whether reserve must be backed by unused capacity above dispatched MW.
3. **Deliverability over the response interval:** whether reserve must be deployable from the operating point within the benchmark’s response time using ramp limits.
4. **Startup/shutdown hours:** whether starting/stopping in period `t` changes the allowed headroom/ramp envelope or disqualifies reserve.

Decision rule: if you cannot phrase these four items using only input fields and report arrays, stop and inspect the task statement/data until you can.

## Step 2 — Implement a parity validator (runnable pattern)

This validator reads **only** (a) input parameters and (b) the arrays you plan to write to the report (`u, start, stop, p, r`). It recomputes reserve feasibility under your stated definition.

```python
import numpy as np


def reserve_parity_check(
    *,
    u: np.ndarray,
    start: np.ndarray,
    stop: np.ndarray,
    p: np.ndarray,
    r: np.ndarray,
    pmin: np.ndarray,
    pmax: np.ndarray,
    ramp_up: np.ndarray,
    startup_limit: np.ndarray | None = None,
    shutdown_limit: np.ndarray | None = None,
    response_hours: float = 1.0,
    initial_p: np.ndarray | None = None,
    tol: float = 1e-6,
) -> None:
    """Raise AssertionError with a specific failing (g,t) when parity fails."""
    u = np.asarray(u, dtype=int)
    start = np.asarray(start, dtype=int)
    stop = np.asarray(stop, dtype=int)
    p = np.asarray(p, dtype=float)
    r = np.asarray(r, dtype=float)

    G, T = u.shape

    # --- helper: previous period production ---
    if initial_p is None:
        initial_p = np.zeros(G)
    initial_p = np.asarray(initial_p, dtype=float)

    def prev_p(g, t):
        return initial_p[g] if t == 0 else p[g, t - 1]

    for g in range(G):
        for t in range(T):
            # 1) Online-only eligibility
            if u[g, t] == 0:
                assert abs(r[g, t]) <= tol, f"reserve from offline unit at (g={g}, t={t})"
                continue

            # 2) Headroom coupling (actual-MW form)
            assert p[g, t] + r[g, t] <= pmax[g] + tol, f"headroom violated at (g={g}, t={t})"
            assert p[g, t] + tol >= pmin[g], f"min output violated at (g={g}, t={t})"

            # 3) Startup/shutdown capability (optional fields)
            if startup_limit is not None and start[g, t] == 1:
                assert p[g, t] + r[g, t] <= startup_limit[g] + tol, f"startup limit violated at (g={g}, t={t})"

            if shutdown_limit is not None and stop[g, t] == 1:
                # Interpret shutdown_limit as max sustainable output in shutdown period.
                assert p[g, t] + r[g, t] <= shutdown_limit[g] + tol, f"shutdown limit violated at (g={g}, t={t})"

            # 4) Ramp deliverability over response interval
            # Assume reserve must be deployable on top of current dispatch from last period's dispatch.
            # If the benchmark uses a different convention, update this function and your model together.
            ru = ramp_up[g] * response_hours
            assert p[g, t] + r[g, t] - prev_p(g, t) <= ru + tol, f"ramp-up deliverability violated at (g={g}, t={t})"


# --- minimal smoke test (replace with real arrays) ---
G, T = 1, 2
u = np.array([[1, 1]])
start = np.array([[0, 0]])
stop = np.array([[0, 0]])
p = np.array([[10.0, 12.0]])
r = np.array([[1.0, 0.0]])
pmin = np.array([0.0])
pmax = np.array([20.0])
ramp_up = np.array([5.0])
reserve_parity_check(
    u=u, start=start, stop=stop, p=p, r=r,
    pmin=pmin, pmax=pmax, ramp_up=ramp_up,
    response_hours=1.0, initial_p=np.array([10.0]),
)
```

## Runtime branch: what to do when parity fails

- **Branch A (fails at headroom):** you are counting reserve not backed by unused capacity. Fix either (a) the model constraint (`p + r <= capability`) or (b) the extraction/report conversion.
- **Branch B (fails at ramp deliverability):** your ramp coupling is too weak or uses the wrong operating point (`t` vs `t-1`, actual vs above-min). Fix the ramp-reserve constraint to mirror the check.
- **Branch C (fails only on startup/shutdown hours):** the benchmark likely tightens or disqualifies reserve during transitions. Use the task’s startup/shutdown capability fields (if present) and implement explicit transition-hour rules consistently in both model and validator.

Decision rule: do not “patch” the validator to pass without simultaneously updating the model constraints; the validator is the contract with the benchmark.

## Verification step (required) + corrective action on failure

1. Run `reserve_parity_check(...)` on the **final report arrays** immediately before writing JSON.
2. If it raises/prints a failing `(g,t)`:
   - print that unit’s `u,start,stop,p,r` for `t-1,t` and the relevant limits;
   - update the model constraint family responsible (headroom vs ramp vs transition-hour capability);
   - re-solve and re-run the parity check.

If the parity validator passes but the benchmark still fails, your definition likely differs from the benchmark’s response interval or transition convention. Update the checklist in Step 1 and adjust both model + validator together.
