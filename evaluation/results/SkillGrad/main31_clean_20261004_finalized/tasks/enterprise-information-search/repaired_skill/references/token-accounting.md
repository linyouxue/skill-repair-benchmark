# Token accounting when numeric counts are required

Use this when the output schema requires token counts (per item or overall) and the environment might or might not expose runtime usage.

## Procedure

1. Identify the exact contract: **which fields must be numeric** (e.g., `tokens`, `prompt_tokens`, `completion_tokens`) and whether the requirement is per-question or run-level.
2. Look for authoritative runtime/trace counters first (run metadata, tool return metadata, trace JSON): `total_tokens`, `prompt_tokens`, `completion_tokens`.
3. If only a run-level total exists but per-item counts are required, apply an explicit allocation rule (and keep values numeric).
4. If no counters exist, compute with a compatible tokenizer.
5. Verify the written JSON satisfies numeric type requirements; if not, stop and fix before any other refinement.

## Runnable reference implementation (with branches)

```python
import math
from dataclasses import dataclass

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def get_usage_from_meta(run_meta: dict) -> Usage | None:
    # Branch A: OpenAI-style nested usage
    if isinstance(run_meta.get("usage"), dict):
        u = run_meta["usage"]
        if all(isinstance(u.get(k), int) for k in ("prompt_tokens", "completion_tokens")):
            return Usage(u["prompt_tokens"], u["completion_tokens"])

    # Branch B: flat counters
    if all(isinstance(run_meta.get(k), int) for k in ("prompt_tokens", "completion_tokens")):
        return Usage(run_meta["prompt_tokens"], run_meta["completion_tokens"])

    # Branch C: only total available (cannot split without a rule)
    if isinstance(run_meta.get("total_tokens"), int):
        total = run_meta["total_tokens"]
        return Usage(prompt_tokens=total, completion_tokens=0)

    return None


def allocate_total_across_items(total: int, n_items: int) -> list[int]:
    # Branch D: proportional equal split (explicit rule)
    base = total // n_items
    rem = total - base * n_items
    return [base + (1 if i < rem else 0) for i in range(n_items)]


def compute_tokens_fallback(text: str) -> int:
    # Branch E: tokenizer available
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Branch F: no tokenizer; cannot satisfy strict numeric token contract safely
        raise RuntimeError("No runtime token counters and tokenizer unavailable")


def verify_numeric_tokens(obj) -> None:
    # Verification step
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("tokens") and v is not None and not isinstance(v, int):
                raise TypeError(f"{k} must be int; got {type(v).__name__}")
            verify_numeric_tokens(v)
    elif isinstance(obj, list):
        for v in obj:
            verify_numeric_tokens(v)


def demo(run_meta: dict, items: list[str]) -> dict:
    usage = get_usage_from_meta(run_meta)

    if usage is not None and isinstance(run_meta.get("total_tokens"), int):
        total = run_meta["total_tokens"]
        per_item = allocate_total_across_items(total, len(items))
        out = {"items": [{"answer": a, "tokens": t} for a, t in zip(items, per_item)]}

    elif usage is not None:
        # If only prompt/completion are available, still keep numeric totals.
        total = usage.total_tokens
        per_item = allocate_total_across_items(total, len(items))
        out = {"items": [{"answer": a, "tokens": t} for a, t in zip(items, per_item)]}

    else:
        # No runtime counters: compute from text.
        out = {"items": [{"answer": a, "tokens": compute_tokens_fallback(a)} for a in items]}

    verify_numeric_tokens(out)
    return out


if __name__ == "__main__":
    print(demo({"total_tokens": 1234}, ["a", "b", "c"]))
```

## If verification fails

- If `verify_numeric_tokens` raises a `TypeError`: rewrite those fields to integers (do not use strings like "unavailable"); re-run verification.
- If `compute_tokens_fallback` raises `RuntimeError`: you cannot satisfy a strict token-count contract without runtime counters or a tokenizer. Your next action is to **search for any available run/trace metadata** (tool outputs, logs, environment-provided usage) or change execution plan to one that exposes token usage; do not finalize with placeholders.
