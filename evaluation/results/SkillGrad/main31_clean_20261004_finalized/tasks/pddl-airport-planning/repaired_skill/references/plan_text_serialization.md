# Plan text serialization for PDDL/IPC evaluators

Many benchmark evaluators expect a plain-text plan file with **one action per line** in a tokenized format:

- Common form: `(<action-name> <arg1> <arg2> ...)`
- Tokens are whitespace-separated, no commas.
- Use object names exactly as they appear in the PDDL.

Unified Planning’s `str(ActionInstance)` is a **pretty-print** that may look like `move_x(airplane_1, loc_2)` or `move_x(airplane_1)` and is often rejected by evaluators that parse IPC plan text.

## Procedure

### 1) Serialize each action instance into PDDL tokens

```python
import re

LINE_RE = re.compile(r"^\s*\([^\s()]+(\s+[^\s()]+)*\)\s*$")

def serialize_action_instance(ai):
    name = ai.action.name
    args = []
    for p in ai.actual_parameters:
        # Branch: object parameter vs constant value
        obj = getattr(p, "object", None)
        if callable(obj) and p.object() is not None:
            args.append(p.object().name)
        else:
            args.append(str(getattr(p, "constant_value", lambda: p)()))
    return "(" + " ".join([name] + args) + ")"

def write_plan_text(plan, path):
    with open(path, "w", encoding="utf-8") as f:
        for ai in plan.actions:
            f.write(serialize_action_instance(ai) + "\n")

```

### 2) Runtime branch: choose formatting variant

Some evaluators accept unparenthesized lines (`action arg1 arg2`), but many require parentheses.

```python
def write_plan(plan, path, require_parentheses=True):
    lines = []
    for ai in plan.actions:
        line = serialize_action_instance(ai)
        if not require_parentheses:
            line = line.strip()
            line = line[1:-1] if line.startswith("(") and line.endswith(")") else line
        lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

```

### 3) Verification: re-open and sanity-check syntax

```python
def verify_plan_file(path, require_parentheses=True):
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]

    if require_parentheses:
        bad = [ln for ln in lines if not LINE_RE.match(ln)]
        if bad:
            # Corrective action: rewrite using parenthesized token format
            raise ValueError(f"Plan text lines not in '(a b c)' token form: {bad[:3]}")
    else:
        # Corrective action: if lines still look like UP pretty-print, switch to parentheses and rewrite
        if any("(" in ln and ")" in ln and "," in ln for ln in lines):
            raise ValueError("Plan appears to use pretty-print/commas; rewrite in token format")

    # Additional guardrail: detect function-call style `name(arg)`
    if any(re.search(r"\w\([^\s].*\)", ln) and not ln.lstrip().startswith("(") for ln in lines):
        raise ValueError("Detected name(arg) style; rewrite as whitespace-separated tokens")

    return True

```

If verification fails: **do not submit** the plan; instead rewrite serialization with `serialize_action_instance()` and re-run `verify_plan_file()`.
