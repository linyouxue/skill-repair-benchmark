# Report-field parity checks (transition-derived aggregates)

Use this when the grader compares top-level summary fields (totals/counters) that are derived from time-series decisions, especially commitment transitions with initial conditions.

## Goal

Ensure every derived summary field in the report (e.g., total startups/shutdowns) matches a single explicit definition and is **internally consistent with the arrays you actually write**.

## Procedure (with runtime branches)

```python
import numpy as np

def round_binary(x, tol=1e-6):
    """Round near-binary values; raise if far from {0,1}."""
    x = np.asarray(x, dtype=float)
    dist = np.minimum(np.abs(x - 0.0), np.abs(x - 1.0))
    if np.max(dist) > tol:
        raise ValueError(f"binary not within tol={tol}: max_dist={float(np.max(dist))}")
    return (x >= 0.5).astype(int)


def recompute_transitions(u_rep, initial_on):
    """Compute start/stop from u and initial state with an explicit t=0 convention."""
    u_rep = np.asarray(u_rep, dtype=int)
    initial_on = np.asarray(initial_on, dtype=int)
    G, T = u_rep.shape

    start = np.zeros((G, T), dtype=int)
    stop = np.zeros((G, T), dtype=int)

    prev = initial_on.copy()
    for t in range(T):
        start[:, t] = ((u_rep[:, t] == 1) & (prev == 0)).astype(int)
        stop[:, t] = ((u_rep[:, t] == 0) & (prev == 1)).astype(int)
        prev = u_rep[:, t]
    return start, stop


def parity_check_report(report, tol=1e-6):
    """Validate and (optionally) correct transition-derived fields."""
    # Branch A: u already integer/binary
    try:
        u_rep = np.asarray(report["commitment"], dtype=int)
        if not np.all((u_rep == 0) | (u_rep == 1)):
            raise ValueError("not binary")
    except Exception:
        # Branch B: u is float-ish -> round once, then recompute everything
        u_rep = round_binary(report["commitment"], tol=tol)

    initial_on = np.asarray(report["initial_on"], dtype=int)

    start, stop = recompute_transitions(u_rep, initial_on)

    # Structural transition identities (include t=0 via initial_on)
    assert np.all(u_rep[:, 0] - initial_on == start[:, 0] - stop[:, 0]), "t=0 transition identity fails"
    assert np.all(u_rep[:, 1:] - u_rep[:, :-1] == start[:, 1:] - stop[:, 1:]), "transition identity fails"
    assert np.all(start + stop <= 1), "start/stop overlap"

    # Ensure totals are sums of the same arrays that are written
    total_startups = int(start.sum())
    total_shutdowns = int(stop.sum())

    # If report already has these fields, ensure parity; otherwise, populate
    if "total_startups" in report:
        assert int(report["total_startups"]) == total_startups, "total_startups mismatch"
    if "total_shutdowns" in report:
        assert int(report["total_shutdowns"]) == total_shutdowns, "total_shutdowns mismatch"

    # Write back canonical versions (optional, but keeps the report consistent)
    report["commitment"] = u_rep.tolist()
    report["startup"] = start.tolist()
    report["shutdown"] = stop.tolist()
    report["total_startups"] = total_startups
    report["total_shutdowns"] = total_shutdowns

    return report
```

## Verification step (and corrective action on failure)

1. Run `parity_check_report(report)` immediately before JSON serialization.
2. If an `assert` fails:
   - **Do not** patch the totals by hand.
   - Print (or log) the first failing generator/time index.
   - Re-check that your `initial_on` matches the prompt/schema and that you are not mixing “modeled” and “rounded/extracted” arrays.
   - If you intended to report solver `start/stop` binaries directly, skip recomputation and instead validate `u` and `start/stop` satisfy the transition identity, then compute totals from those reported arrays.

Decision rule: once you decide the report will be based on rounded `u_rep`, recompute *all* transition-derived arrays and aggregates from `u_rep` and `initial_on` and discard any earlier versions.
