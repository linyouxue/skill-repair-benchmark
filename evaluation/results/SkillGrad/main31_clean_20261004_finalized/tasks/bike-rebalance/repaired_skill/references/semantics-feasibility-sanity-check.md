# Semantics + Feasibility Sanity Check (Targets vs Hard Bounds)

Use this procedure when translating a logistics/rebalancing statement into an optimization model and you notice (or suspect) that the chosen hard constraints make some targets/demands impossible.

Typical triggers:

- You bound net pickup by initial inventory (or net dropoff by free capacity) and some targets violate those bounds.
- You added a deviation/unmet penalty and the solver uses it, but the statement does not clearly permit unmet targets.
- Targets look “physically backwards” under your sign convention (e.g., requiring pickups where there is little/no stock).

## Step 1 — Write down the candidate semantics

Make the semantics explicit for each quantity:

- What does a positive target mean? net pickup? net dropoff? desired final inventory change?
- Is initial inventory a hard physical bound, informational only, or a starting state for a multi-period model?
- Is there a depot/source/sink of units? Can vehicles start loaded or must they start empty?

## Step 2 — Compute implied feasibility ranges

A fast pre-check often catches a wrong interpretation.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Node:
    initial: float
    capacity: float
    target: float  # interpreted as desired net_change


def feasibility_range_if_inventory_bounded(node: Node):
    """If you enforce final inventory in [0, cap] with final = initial - net_change,
    then net_change is constrained to [initial-cap, initial]."""
    lo = node.initial - node.capacity
    hi = node.initial
    return lo, hi


def check_targets(nodes):
    infeasible = []
    for idx, node in enumerate(nodes):
        lo, hi = feasibility_range_if_inventory_bounded(node)
        if not (lo <= node.target <= hi):
            infeasible.append((idx, node.target, (lo, hi)))
    return infeasible


nodes = [Node(initial=10, capacity=20, target=15), Node(initial=5, capacity=10, target=-9)]
violations = check_targets(nodes)
print("violations", violations)
```

Runtime branch:

- If `violations` is empty, your inventory-bounded interpretation is at least consistent with the targets.
- If `violations` is non-empty, stop and reconsider semantics before building the full model.

## Step 3 — Branch to the right corrective action

### Branch A: Flip sign convention

If positive/negative meaning is ambiguous, test the opposite convention by checking feasibility against `-target`.

```python
def check_with_sign_flip(nodes):
    flipped = [Node(n.initial, n.capacity, -n.target) for n in nodes]
    return check_targets(flipped)

violations_flipped = check_with_sign_flip(nodes)
print("violations_flipped", violations_flipped)
```

- If the flipped version has far fewer (or zero) violations, adopt the flipped convention consistently in *all* constraints and output fields.

### Branch B: Add explicit sources/sinks (e.g., depot supply/absorption, start loads)

If targets require net pickups beyond local initial stock, you may be missing a source of units.

Modeling options (choose what the statement supports):

- Allow vehicles to start with nonzero load (bounded by vehicle capacity).
- Add a depot inventory variable and allow load changes at the depot.
- Treat the depot as having unlimited supply/absorption (only when stated/standard in the benchmark).

### Branch C: Remove or reinterpret hard station-inventory bounds

If the benchmark’s `initial` values are informational or represent a different time snapshot, binding net service directly by initial/free-space may be incorrect.

Instead, the model might need:

- Only vehicle capacity and service aggregation constraints, with targets enforced as hard equalities.
- A different relationship between target and inventory (e.g., target is desired final inventory, not net change).
- Multi-period inventory dynamics.

### Branch D: Soft penalties are allowed (explicitly)

Only keep `unmet`/`deviation` variables if the statement clearly permits violating targets.

Even then, verify that your penalty meaning matches the scoring (absolute deviation vs one-sided unmet, per-unit weights, etc.).

## Verification — don’t proceed until a check passes

Verification check:

1. Under the chosen semantics, rerun the feasibility-range check and ensure **all targets are within bounds** (or that the statement explicitly allows violating them).
2. If the check still fails:
   - Do **not** “just increase penalties.”
   - Return to Step 1 and choose a different branch (flip sign, add source/sink, or reinterpret bounds) until the check is consistent.

When the feasibility check passes, then implement the full MIP and (separately) validate the extracted solution against the same semantics.
