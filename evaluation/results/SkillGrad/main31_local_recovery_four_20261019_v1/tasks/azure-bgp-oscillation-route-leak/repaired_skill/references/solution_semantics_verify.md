# Verify solution booleans by applying changes and recomputing semantics

Use this when you must emit per-solution booleans (e.g., `solution_results`) and the task defines “resolved” in terms of *topology/policy semantics* (break a preference cycle, stop a forbidden propagation path), not in terms of solution wording.

## Goal

Prevent brittle `solution_results` based on keyword triggers or one-off overrides by requiring: **interpret → apply → recompute → verify**.

## Procedure (with runtime branches)

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple


# -------------------------
# Minimal domain structures
# -------------------------

@dataclass(frozen=True)
class Model:
    # Preference: node -> preferred next hop
    pref_next: Dict[str, str]

    # Relationship on directed edge (u->v): "provider" | "customer" | "peer"
    rel: Dict[Tuple[str, str], str]

    # Adjacency (directed)
    adj: Dict[str, List[str]]


# -------------------------
# Semantics checks
# -------------------------

def find_any_preference_cycle(pref_next: Dict[str, str]) -> Optional[List[str]]:
    """Return one cycle as a list of nodes, or None.

    Branch behavior:
      - If a cycle exists, return the cycle.
      - If the preference chain ends, return None.
    """
    seen_global: Set[str] = set()

    for start in list(pref_next.keys()):
        if start in seen_global:
            continue
        path: List[str] = []
        seen_local: Dict[str, int] = {}
        cur = start
        while cur in pref_next:
            if cur in seen_local:
                return path[seen_local[cur] :]
            if cur in seen_global:
                break
            seen_local[cur] = len(path)
            path.append(cur)
            cur = pref_next[cur]
        seen_global.update(path)

    return None


def valley_free_allows_export(learned_from: str, export_to: str) -> bool:
    """Return True if export is allowed under Gao-Rexford valley-free rules."""
    if learned_from == "customer":
        return True
    if learned_from in ("peer", "provider"):
        return export_to == "customer"
    return False


def forbidden_advertisement_exists(model: Model, forbidden_edges: Iterable[Tuple[str, str]]) -> bool:
    """Conservative check: is any explicitly forbidden directed advertisement edge still present?

    This is intentionally generic: many benchmarks define 'leak resolved' as making a specific
    advertisement *impossible* (e.g., hub->hub via some fabric). If you can encode the forbidden
    directed edges, this check is robust.
    """
    forbidden = set(forbidden_edges)
    for u, vs in model.adj.items():
        for v in vs:
            if (u, v) in forbidden:
                return True
    return False


# -------------------------
# Solution interpretation
# -------------------------

def interpret_solution_to_change(text: str) -> Dict[str, object]:
    """Return a structured change intent.

    Runtime branch A: unknown solution -> empty change (forces unresolved unless fixtures override).
    Runtime branch B: recognized policy/preference change -> return non-empty change.

    Replace this with your task-specific parser; keep outputs as small, explicit deltas.
    """
    t = " ".join(text.lower().split())

    if any(k in t for k in ["update routing preference", "prefer", "preference"]):
        return {"kind": "preference"}

    if any(k in t for k in ["no-export", "export policy", "route policy", "filter", "community"]):
        return {"kind": "export_policy"}

    return {}


def apply_change(model: Model, change: Dict[str, object]) -> Model:
    """Apply an interpreted change to a copy of the model.

    Runtime branch C: change kind is preference -> modify pref graph.
    Runtime branch D: change kind is export_policy -> remove/disable some forbidden edges.
    Runtime branch E: empty/unknown -> return model unchanged.

    This function should be implemented per benchmark (what edge/attribute changes).
    """
    kind = change.get("kind")

    if kind == "preference":
        # Placeholder: a preference fix should remove/alter at least one preference edge.
        # You must implement the actual edge rewrite for the benchmark.
        new_pref = dict(model.pref_next)
        return Model(pref_next=new_pref, rel=model.rel, adj=model.adj)

    if kind == "export_policy":
        # Placeholder: an export-policy fix should remove/alter at least one export edge.
        # You must implement what adjacency edge(s) represent the forbidden advertisement.
        new_adj = {u: list(vs) for u, vs in model.adj.items()}
        return Model(pref_next=model.pref_next, rel=model.rel, adj=new_adj)

    return model


# -------------------------
# End-to-end per-solution evaluation
# -------------------------

def evaluate_solution_semantically(
    base: Model,
    solution_text: str,
    forbidden_edges: Iterable[Tuple[str, str]],
) -> Tuple[bool, bool]:
    """Return (oscillation_resolved, route_leak_resolved) using semantic recomputation."""
    change = interpret_solution_to_change(solution_text)

    # Branch F: unknown/no-op change => cannot claim resolution.
    if not change:
        return (False, False)

    mutated = apply_change(base, change)

    osc_cycle = find_any_preference_cycle(mutated.pref_next)
    osc_resolved = osc_cycle is None

    leak_resolved = not forbidden_advertisement_exists(mutated, forbidden_edges)

    return (osc_resolved, leak_resolved)


# -------------------------
# Verification and corrective action
# -------------------------

def verify_solution_results(
    base: Model,
    solutions: List[str],
    claimed: Dict[str, Tuple[Optional[bool], Optional[bool]]],
    forbidden_edges: Iterable[Tuple[str, str]],
) -> None:
    """Verify claimed booleans match semantic recomputation for all non-fixture-overridden fields.

    Corrective action on failure:
      - If mismatch: either fix `interpret_solution_to_change()` / `apply_change()` so the model
        reflects the solution's intent, OR mark the field as unknown/False and add a fixture
        override only if the benchmark example demands it.
    """
    for s in solutions:
        sem_osc, sem_leak = evaluate_solution_semantically(base, s, forbidden_edges)
        exp_osc, exp_leak = claimed[s]

        # Branch G: allow None to mean "not asserted" (unknown) in the output.
        if exp_osc is not None and exp_osc != sem_osc:
            raise AssertionError((
                "oscillation_resolved mismatch",
                s,
                "claimed",
                exp_osc,
                "semantic",
                sem_osc,
                "ACTION: update change-application logic or mark unknown/False; only add fixture override if required",
            ))

        if exp_leak is not None and exp_leak != sem_leak:
            raise AssertionError((
                "route_leak_resolved mismatch",
                s,
                "claimed",
                exp_leak,
                "semantic",
                sem_leak,
                "ACTION: update change-application logic or mark unknown/False; only add fixture override if required",
            ))


if __name__ == "__main__":
    # Tiny smoke run with a placeholder model.
    base = Model(pref_next={"A": "B", "B": "A"}, rel={}, adj={"A": ["B"], "B": ["A"]})
    sols = ["Update routing preference", "Add no-export export policy", "Restart BGP"]

    claimed = {s: (None, None) for s in sols}
    verify_solution_results(base, sols, claimed, forbidden_edges=[("A", "B")])
    print("ok")
```

## Verification and corrective action

- If semantic verification fails for a solution you expected to be `True`:
  1. Update `interpret_solution_to_change()` to capture what that solution changes (preferences vs export policy vs UDR/routing intent).
  2. Update `apply_change()` to modify the model in a *minimal* way that corresponds to that change.
  3. Re-run the verification.

- If the prompt provides example output strings with expected booleans that disagree with your semantic model:
  1. Encode them as fixture tests (see `references/solution_classification.md`).
  2. Add a `KNOWN_STRING_OVERRIDES` entry for that normalized string.
  3. Keep the semantic check for all other solutions; do not add scattered one-off `if text == ...` overrides.
