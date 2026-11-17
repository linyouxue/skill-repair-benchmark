# Reject empty-string keys and fail-closed on unknown properties at a Jackson boundary

Use this chapter when the exploit relies on **JSON shape quirks** (e.g., empty-string field names, duplicate keys, or unexpected properties) and the vulnerable code path is reached through a configured `ObjectMapper`/provider.

## Goal

Create a **single chokepoint** close to the HTTP→Jackson boundary that deterministically rejects:

- Empty-string object field names (`""`)
- Duplicate keys (or at least detects and rejects them)
- Unknown properties for security-sensitive DTOs/specs (fail closed)

This is usually more robust than modifying a handful of leaf classes.

---

## Approach A — Streaming pre-scan + strict binding (works without special parser features)

This approach reads the JSON as a token stream first, rejects suspicious structure, then binds to DTOs.

```python
import json
from typing import Any


def reject_empty_keys(obj: Any) -> None:
    # Recursive structural validation for dict/list trees.
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "":
                raise ValueError("empty-string JSON key rejected")
            reject_empty_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            reject_empty_keys(item)


def boundary_parse_and_bind(raw: str) -> dict:
    # Branch A: structural reject (empty key)
    tree = json.loads(raw)
    reject_empty_keys(tree)

    # Branch B: proceed to binding step (placeholder)
    # In Java, this is where mapper.readValue(...) happens.
    return tree


def verify_rejection() -> None:
    malicious = '{"a": 1, "": {"enabled": true}}'
    try:
        boundary_parse_and_bind(malicious)
        raise AssertionError("expected empty-key rejection")
    except ValueError:
        pass


if __name__ == "__main__":
    verify_rejection()
```

### Runtime branch

- If the pre-scan raises for empty keys, return HTTP 400 (or equivalent) with a safe error message.
- If it does not raise, proceed to normal Jackson binding.

### Verification

1. Confirm the malicious payload is rejected.
2. If a variant still passes, **expand the scan scope** (ensure you scan the raw request body used by the endpoint) and add checks for:
   - Duplicate keys (see Approach B)
   - Keys that are whitespace-only (e.g., `"   "`) if that’s relevant to the codebase

Next corrective action on failure: if the malicious payload still reaches the DTO, move the rejection earlier (closest possible boundary: JAX-RS provider / message converter) and add a test that exercises the real endpoint wiring.

---

## Approach B — Reject duplicate keys (parser-level) + unknown-property failure (mapper-level)

Prefer parser-level duplicate-key rejection, because “last key wins” semantics can bypass upstream validation.

```python
import json


def loads_reject_dupes(raw: str):
    # object_pairs_hook sees all pairs, including duplicates.
    def no_dupes(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate key rejected: {k!r}")
            out[k] = v
        return out

    return json.loads(raw, object_pairs_hook=no_dupes)


def verify_duplicate_key_rejection() -> None:
    dup = '{"role": "user", "role": "admin"}'
    try:
        loads_reject_dupes(dup)
        raise AssertionError("expected duplicate-key rejection")
    except ValueError:
        pass


if __name__ == "__main__":
    verify_duplicate_key_rejection()
```

### Runtime branch

- If duplicates are found, reject the request before binding.
- If duplicates are not found, proceed.

### Verification

- If the application still accepts a duplicate-key variant, ensure you are not parsing twice with different stacks (e.g., a gateway/WAF parses once, the application parses again). Move the rejection logic to the **closest possible boundary**.

Next corrective action on failure: if the endpoint still accepts duplicates, add an integration test that submits the raw body through the HTTP stack and confirm only one JSON parser is used.

---

## Approach C — Fail closed on unknown fields for only security-sensitive types

In Java/Jackson, failing on unknown properties globally can be too breaking. Scope it:

- Use a dedicated mapper/provider for “spec” DTOs
- Or annotate only the sensitive DTO classes to deny unknown fields

### Runtime branch (scoping)

- If other endpoints rely on permissive parsing, keep them on the default mapper.
- If only a subset of endpoints is risky, apply strict parsing only there.

### Verification

- Add three tests per hardened boundary:
  1) malicious payload rejects
  2) a close variant rejects (different nesting / placement)
  3) a legitimate payload still succeeds

If the legitimate payload fails, narrow the strictness scope (endpoint-specific mapper/provider or per-type annotations) rather than re-enabling permissive parsing.

Next corrective action on failure: if making the mapper strict breaks valid clients, scope strictness to the vulnerable endpoint (separate mapper/provider) and add per-endpoint contract tests to prevent regression.

---

## Approach D — Single-artifact deployment constraints (verifier swaps only some jars)

When the evaluation harness replaces only a subset of artifacts, a “correct” code change can still fail because it is not on the runtime classpath. Treat this as part of the threat model.

```python
from dataclasses import dataclass


@dataclass
class PatchPlan:
    deployed_artifacts: set[str]


def choose_fix_location(plan: PatchPlan) -> str:
    # Branch A: you can only change the artifact that is actually deployed
    if len(plan.deployed_artifacts) == 1:
        return "implement boundary rejection in the deployed artifact (endpoint provider/validator)"

    # Branch B: multiple artifacts swapped; you can patch shared libraries too
    return "implement boundary rejection at the shared JSON provider used by all artifacts"


def verify_plan(plan: PatchPlan, fix_location: str) -> None:
    # Minimal correctness check: fix must live where verifier runs it.
    if len(plan.deployed_artifacts) == 1 and "deployed artifact" not in fix_location:
        raise AssertionError("fix location likely not deployed; move fix into the swapped artifact")


if __name__ == "__main__":
    plan = PatchPlan(deployed_artifacts={"some-service"})
    loc = choose_fix_location(plan)
    verify_plan(plan, loc)
```

### Runtime branch

- If only one service jar is swapped, implement empty-key/duplicate-key rejection in that service’s request parsing/validation path (closest chokepoint you can ship).
- If multiple jars are swapped, prefer a shared JSON provider/chokepoint to avoid inconsistent policy.

### Verification

1. Confirm your patched classes/resources are packaged into the artifact the verifier deploys.
2. If the verifier still observes the exploit, assume your fix was not on the runtime classpath and **move the mitigation closer to the deployed HTTP boundary**.

Next corrective action on failure: inspect the produced artifacts (jar contents) and relocate the mitigation to a class guaranteed to be loaded by the swapped artifact.
