# Output Population Definition (Universe of Keys)

Use this when a streaming/batch pipeline must emit one record per key/entity, and the pipeline includes joins, gating, or auxiliary streams that could implicitly change which keys appear.

## Core idea

A correct per-key metric is not sufficient if you output for the wrong set of keys. Prevent this by:

1. Writing a one-sentence **population rule**: “emit exactly one record for every `<key>` such that `<predicate>`”.
2. Deciding whether auxiliary streams (enrichment/terminal-status) are:
   - **Constraints** (missing aux record means exclude key), or
   - **Optional** (missing aux record means default/emit anyway).
3. Verifying both **coverage** (no missing required keys) and **exclusion** (no extra keys).

## Runnable reference model (Python)

```python
from dataclasses import dataclass
from typing import Iterable, Optional, Set, Tuple

@dataclass(frozen=True)
class PrimaryEvent:
    key: str

@dataclass(frozen=True)
class AuxEvent:
    key: str


def universe_from_primary(primary: Iterable[PrimaryEvent]) -> Set[str]:
    return {e.key for e in primary}


def apply_aux_constraint(keys: Set[str], aux: Iterable[AuxEvent], mode: str) -> Set[str]:
    """mode: 'optional' or 'required'.

    - optional: do not filter keys by aux presence
    - required: keep only keys that appear in aux
    """
    aux_keys = {e.key for e in aux}
    if mode == "optional":
        return keys
    if mode == "required":
        return keys & aux_keys
    raise ValueError(f"unknown mode: {mode}")


def coverage_exclusion_checks(expected: Set[str], actual: Set[str]) -> Tuple[Set[str], Set[str]]:
    missing = expected - actual
    extra = actual - expected
    return missing, extra


if __name__ == "__main__":
    primary = [PrimaryEvent("a"), PrimaryEvent("b"), PrimaryEvent("c")]
    aux = [AuxEvent("a"), AuxEvent("b")]  # 'c' missing from aux shard

    expected = universe_from_primary(primary)

    # Branch A: aux is optional (emit even when aux missing)
    actual_a = apply_aux_constraint(expected, aux, mode="optional")
    missing, extra = coverage_exclusion_checks(expected, actual_a)
    print("optional", {"missing": missing, "extra": extra})

    # Branch B: aux is required (drop keys without aux)
    actual_b = apply_aux_constraint(expected, aux, mode="required")
    missing, extra = coverage_exclusion_checks(expected, actual_b)
    print("required", {"missing": missing, "extra": extra})
```

## Runtime branches (choose one)

### Branch A — Primary stream defines the universe (common)

Use when:
- The spec is phrased like “for each key in the primary stream … compute …”, or
- The aux stream is known to be incomplete/optional, or
- You can finalize on bounded input (end-of-input watermark) and don’t need aux to decide completeness.

Implementation:
- Compute the metric from the primary stream.
- If aux is used, treat it as enrichment/defaulting.
- Emit for every primary key that satisfies the predicate.

### Branch B — Aux stream constrains the universe

Use when:
- The spec explicitly requires aux evidence (e.g., “only keys with a terminal status record”), and
- Missing aux records should exclude keys.

Implementation:
- Make the constraint explicit (`expected_keys = primary_keys ∩ aux_keys`).
- Ensure your join/gate enforces exactly that, not “whatever aux happened to include in this shard”.

## Verification

1. **Coverage check:** derive `expected_keys` from the spec (often from the primary stream) and confirm `expected_keys ⊆ output_keys`.
2. **Exclusion check:** confirm `output_keys ⊆ expected_keys`.

If verification fails:
- If keys are missing: remove/relax gating on aux presence, or define default behavior for missing aux records (emit anyway vs hold until end-of-input).
- If extra keys appear: tighten the predicate that defines `expected_keys`, or ensure deduplication/one-record-per-key finalization is correct.
