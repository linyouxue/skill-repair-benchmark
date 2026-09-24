# Persist plan outputs from `problem.json`

Use this procedure when the task provides a JSON manifest that lists multiple planning instances and a `plan_output` file path for each instance.

## Procedure (with branches)

```python
import json
from pathlib import Path

def load_inventory(manifest_path: str):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    # Support either a list of instances or a dict wrapper.
    if isinstance(manifest, list):
        items = manifest
    elif isinstance(manifest, dict) and "instances" in manifest:
        items = manifest["instances"]
    else:
        raise ValueError("Unrecognized manifest shape; expected list or dict with 'instances'")

    required = []
    for it in items:
        required.append((it["domain"], it["problem"], it["plan_output"]))
    return required


def ensure_written(output_path: str, text: str):
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def render_plan(plan) -> str:
    # Branch A: planner returned no plan (unsat/timeout/unknown)
    if plan is None:
        return ""  # empty-plan convention

    # Branch B: normal sequential plan
    # Unified Planning plans iterate over actions; stringify one per line.
    lines = []
    for a in plan.actions:
        lines.append(str(a))
    return "\n".join(lines) + ("\n" if lines else "")


def persist_all(manifest_path: str, solve_one):
    inventory = load_inventory(manifest_path)

    for domain_path, problem_path, plan_output in inventory:
        plan = solve_one(domain_path, problem_path)
        text = render_plan(plan)
        out = ensure_written(plan_output, text)

        # Verification step: confirm existence + convention
        read_back = out.read_text(encoding="utf-8")
        if not out.exists():
            raise RuntimeError(f"Plan file missing after write: {out}")

        # If your harness requires non-empty plans, treat empty as a failure.
        if (plan is not None) and (read_back.strip() == ""):
            raise RuntimeError(
                "Non-empty plan expected but wrote empty text; re-render plan and re-write"
            )

        # Corrective action on mismatch:
        # - If file missing: check parent mkdir + permissions, then retry ensure_written.
        # - If file empty but plan exists: print plan object, adjust render_plan(), then rewrite.

    # End-of-run verification: all outputs exist
    missing = [p for _, _, p in inventory if not Path(p).exists()]
    if missing:
        raise RuntimeError(f"Missing required outputs: {missing}. Re-run persist_all after fixing write step")
```

## Notes

- `solve_one(domain_path, problem_path)` should encapsulate: parse PDDL → solve → (optional) validate → return a plan object or `None`.
- If the benchmark specifies a different failure marker than an empty file, change `render_plan(None)` accordingly and keep the read-back verification aligned.
