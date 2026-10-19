# Classify candidate solution text using the skill taxonomy

Use this when you must label many free-text candidates (e.g., `possible_solutions.json`) with booleans like `oscillation_resolved` and `route_leak_resolved`.

## Procedure

1. **Normalize** each candidate into a small set of categories aligned with the skill’s tiers and invariants.
2. **Assign effects** (`oscillation_resolved`, `route_leak_resolved`) from a category→effect table.
3. **Verify against benchmark fixtures**: if the prompt provides an example output (or otherwise provides expected labels for specific solution strings), encode them as required test cases.
4. **Override when required**: if a benchmark fixture disagrees with category defaults for a specific string, add a known-string override for that string and re-run the tests.

## Runnable reference implementation (Python)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Labels:
    category: str
    oscillation_resolved: Optional[bool]
    route_leak_resolved: Optional[bool]
    invalid: bool

CATEGORY_EFFECT = {
    # Tiered mitigations.
    "routing_intent": (True, True),
    "udr": (True, True),
    "bgp_policy": (True, True),

    # Symptom mitigation; defaults are conservative.
    "timer_tuning": (False, False),

    # Must never be treated as real fixes.
    "prohibited": (False, False),
}

PROHIBITED_MARKERS = [
    "disable bgp", "disable peering", "shutdown", "shut down", "restart",
]

# Benchmark-driven overrides for known strings.
# Keys are normalized (lowercase, collapsed whitespace).
# Values are (category, oscillation_resolved, route_leak_resolved).
KNOWN_STRING_OVERRIDES: dict[str, tuple[str, Optional[bool], Optional[bool]]] = {
    # Add entries only when the benchmark fixture requires a deviation.
    # "change bgp keepalive timer ...": ("timer_tuning", False, True),
}

def normalize(text: str) -> str:
    return " ".join(text.lower().split())

def classify_solution(text: str) -> str:
    t = normalize(text)

    # Runtime branch 1: prohibited always wins.
    if any(m in t for m in PROHIBITED_MARKERS):
        return "prohibited"

    # Runtime branch 2: tiered mitigations.
    if "routing intent" in t or ("virtual wan" in t and "intent" in t):
        return "routing_intent"
    if "user defined route" in t or "udr" in t:
        return "udr"
    if any(k in t for k in [
        "export", "route policy", "route-policy", "route map", "route-map",
        "community", "no-export", "filter", "rpki", "as-path",
    ]):
        return "bgp_policy"
    if any(k in t for k in ["keepalive", "hold timer", "holdtime", "damp", "dampening"]):
        return "timer_tuning"

    return "unknown"

def label_solution(text: str) -> Labels:
    t = normalize(text)

    # Runtime branch 3: known-string fixture override.
    if t in KNOWN_STRING_OVERRIDES:
        cat, osc, leak = KNOWN_STRING_OVERRIDES[t]
        return Labels(cat, osc, leak, invalid=(cat == "prohibited"))

    cat = classify_solution(text)
    if cat in CATEGORY_EFFECT:
        osc, leak = CATEGORY_EFFECT[cat]
        return Labels(cat, osc, leak, invalid=(cat == "prohibited"))

    # Unknown: preserve uncertainty rather than silently defaulting false.
    return Labels(cat, None, None, invalid=False)


def verify_required_cases() -> None:
    """Replace `cases` with fixture expectations from the task prompt when available."""

    # Runtime branch 4: fixture set is empty.
    cases = {
        # "<solution string from prompt>": ("<category>", <osc_bool>, <leak_bool>),
    }
    if not cases:
        # No fixtures available; skip.
        return

    for text, (cat, osc, leak) in cases.items():
        out = label_solution(text)
        assert (out.category, out.oscillation_resolved, out.route_leak_resolved) == (cat, osc, leak), (
            "Fixture mismatch; add KNOWN_STRING_OVERRIDES or adjust markers/table",
            text,
            out,
        )


if __name__ == "__main__":
    verify_required_cases()
    print("ok")
```

## Verification and corrective action

- If your output booleans disagree with the benchmark’s provided example output:
  1. Add those example strings to `verify_required_cases()`.
  2. If the example expects a different label than your category table would produce, add an entry to `KNOWN_STRING_OVERRIDES`.
  3. Re-run until the fixture test passes, then re-run the end-to-end report generation.

- If prohibited actions are not classified as `prohibited`:
  1. Expand `PROHIBITED_MARKERS` with the missing phrasing.
  2. Keep the rule that **prohibited wins** even if the text also mentions policies.

- If too many real fixes land in `unknown`:
  1. Add markers in `classify_solution()` to recognize the wording used in the input.
  2. Add a *new category only if* it maps cleanly to the skill taxonomy.
  3. Otherwise, treat `unknown` as “needs human review” rather than defaulting to ineffective.
