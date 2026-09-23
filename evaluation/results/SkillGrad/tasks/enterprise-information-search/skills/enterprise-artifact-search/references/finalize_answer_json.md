# Finalize and verify `/root/answer.json` (completion gate)

Read this when the task specifies multiple questions, a non-default output path, extra required fields, or you saw a prior failure where the run ended without a file-write.

Skip this when there is exactly one question and the harness clearly states the default output path and baseline schema.

## Procedure

1) **Determine required path + schema**
- Prefer explicit instructions from the harness/task.
- If missing, default to `/root/answer.json` and a dict keyed by `q1..qN`.

2) **Assemble answers as JSON-serializable values**
- Ensure each question key exists.
- Ensure each answer is present even if empty (unless explicitly allowed to omit).

3) **Enforce baseline per-question schema**
- Minimum safe baseline:
  - `answer`: list
  - `tokens`: int
- If additional required fields exist (e.g., `evidence`, `sources`, `reasoning`), add them *consistently for every question*.

4) **Write** the file to the required path.

5) **Read-back validation** and corrective action
- If any check fails, fix the object and re-write, then re-validate.

## Runnable Python: write + validate with branches

```python
import json
from pathlib import Path

def normalize_answer_value(x):
    # Branch: caller already produced list vs singleton
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def build_payload(question_keys, answers_by_key, extra_fields_by_key=None):
    extra_fields_by_key = extra_fields_by_key or {}
    payload = {}
    for k in question_keys:
        base = {
            "answer": normalize_answer_value(answers_by_key.get(k)),
            "tokens": int(extra_fields_by_key.get(k, {}).get("tokens", 0)),
        }
        # Branch: optional extra fields required by harness
        for fk, fv in extra_fields_by_key.get(k, {}).items():
            if fk not in base:
                base[fk] = fv
        payload[k] = base
    return payload


def validate_payload(payload, question_keys):
    assert isinstance(payload, dict) and payload, "top-level must be a non-empty dict"
    missing = [k for k in question_keys if k not in payload]
    assert not missing, f"missing question keys: {missing}"

    for k in question_keys:
        v = payload[k]
        assert isinstance(v, dict), f"{k} must map to an object"
        assert "answer" in v and "tokens" in v, f"{k} must contain answer and tokens"
        assert isinstance(v["answer"], list), f"{k}.answer must be a list"
        assert isinstance(v["tokens"], int), f"{k}.tokens must be an int"


def write_and_verify(out_path, payload, question_keys):
    out_path = Path(out_path)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    # Verify: file exists and parses
    assert out_path.exists(), f"missing output file: {out_path}"
    loaded = json.loads(out_path.read_text())
    validate_payload(loaded, question_keys)
    return loaded


# Example usage (replace question_keys/answers_by_key with real values)
question_keys = ["q1", "q2"]
answers_by_key = {"q1": "value", "q2": ["a", "b"]}
extra_fields_by_key = {"q1": {"tokens": 12}, "q2": {"tokens": 34}}

payload = build_payload(question_keys, answers_by_key, extra_fields_by_key)
loaded = write_and_verify("/root/answer.json", payload, question_keys)
print("OK:", list(loaded.keys()))
```

## Verification and corrective action

- If **file missing**: you wrote to the wrong path → re-read harness instructions, write to the exact required location, then re-run `write_and_verify`.
- If **JSON parse fails**: payload contained non-serializable objects → convert to plain dict/list/str/int/float/bool/None and re-write.
- If **missing keys**: you forgot to answer all questions → add missing `q*` entries (use empty list if genuinely no answer) and re-validate.
- If **`answer` not a list**: wrap singletons with `normalize_answer_value` and re-write.
- If **schema differs from harness**: update `build_payload` to match the harness-required fields consistently for all questions, then re-validate.
