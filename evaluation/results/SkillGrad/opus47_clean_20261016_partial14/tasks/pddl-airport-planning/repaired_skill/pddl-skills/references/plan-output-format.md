# Plan output format: task-example mirroring, pre-grounded schema splitting, and case-map construction

## When this chapter applies

Load this chapter from `save-plan` (SKILL.md §3) and the planning-time
format-authority step when **any** of:

- The task description or prompt shows a worked plan line (even as an
  "illustration"), e.g. `drive(truck1, depot1, market1)`.
- A reference/sample plan file ships with the task bundle (`*.plan`,
  `*.soln`, `plan.txt`).
- At least one `:action` identifier in the domain file contains
  underscores joining what look like object constants — the IPC
  **airport** family is the canonical example
  (`move_seg_rw_0_400_seg_rww_0_50_south_south_medium`).
- The task description asserts that plan tokens must match the PDDL
  domain/problem identifiers (case-sensitivity against the files).

If none of these fire, return to the plain canonical-IPC `save_plan` in
SKILL.md §3.

---

## The three orthogonal decisions

| Decision          | Authority rank (highest-first)                                                                                                                                | Fallback (no higher-rank authority present) |
|-------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------|
| Surface wrapper   | (1) task example first line → (2) prose spec                                                                                                                  | canonical IPC `(verb args ...)`             |
| Schema expansion  | (1) **domain inspection: pre-grounded ⇒ `head_is_schema=True`** → (2) task example head token (same-family only) → (3) reference plan head token (same-family) | split if pre-grounded; else identity        |
| Case convention   | (1) task example case pattern → (2) raw PDDL problem/domain file **if task prose demands match**                                                              | planner's lowercase `str(p)` verbatim       |

Resolve each row from its own evidence. **Evidence from one row does
not drive a decision in another.** A plain-verb example (e.g. `drive(...)`
from the depot/truck family) tells you comma-call wrapper and
uppercase object case — nothing about schema expansion in a pre-grounded
airport domain. For schema expansion, inspect the current task's domain
first; the example only speaks to schema expansion when its own domain
family matches the current task's.

Common mixed scenarios:

- **Example `drive(truck1, depot1, market1)` present, current task is
  pre-grounded airport.** Row 1 → `verb(args, ...)` comma-call;
  Row 2 → **keep schema whole** (pre-grounded domain overrides example
  head); Row 3 → example-driven uppercase case map. Correct output is
  Form 1 below.
- **No example, prose demands match-the-PDDL-files case.** Row 1 →
  canonical wrapper; Row 2 → canonical split (domain pre-grounded, no
  example); Row 3 → problem-file case map.
- **Example present and same-family (both plain-verb or both
  pre-grounded with matching convention).** All three rows → mirror the
  example.
- **Nothing specified.** All three rows → canonical IPC defaults.

---

## Pre-grounding detector (sub-track 2 rank-1 authority)

```python
import re

ACTION_HEADER = re.compile(
    r"\(\s*:action\s+([A-Za-z0-9_\-]+)\s+:parameters\s*\(([^)]*)\)",
    flags=re.IGNORECASE,
)

def is_pregrounded_domain(domain_path):
    """Return True iff the raw domain file declares at least one
    :action whose identifier contains underscore-joined constants that
    could not all be free parameters.

    Signals (any triggers True):
      - action name contains `seg_` (airport-family hard signal).
      - action name has >= 2 underscores AND fewer :parameters than
        the number of underscore-joined parts of the name.
    """
    if not domain_path:
        return False
    with open(domain_path) as f:
        text = f.read()
    for m in ACTION_HEADER.finditer(text):
        name = m.group(1)
        params_block = m.group(2)
        # Count typed parameter slots: each `?x` token is one.
        n_params = len(re.findall(r"\?[A-Za-z0-9_\-]+", params_block))
        if "seg_" in name:
            return True
        if name.count("_") >= 2 and name.count("_") + 1 > max(n_params, 1):
            return True
    return False
```

**Two runtime branches on the return value:**
- `True` → sub-track 2 is resolved: `head_is_schema=True`. Downstream
  (`format_like_example`, `save_plan`) must emit `action.name` as a
  single head token and ignore any example's head shape for this
  decision.
- `False` → sub-track 2 falls through to its lower-ranked authorities
  (task example head → reference plan head → canonical fallback).

**Verification (mandatory):**

```python
def verify_pregrounded_detection(domain_path, expected):
    got = is_pregrounded_domain(domain_path)
    assert got == expected, (
        f"pre-grounding detection: got {got} want {expected} for {domain_path}"
    )
```

**On failure (what to do next):**
- `got False, want True` on an airport-family domain: the `:action`
  identifier regex missed the shape — print `ACTION_HEADER.findall(text)`
  on the raw text and extend `ACTION_HEADER` or the signal predicates
  (add new hard-signal tokens besides `seg_` if a related family uses
  different constant prefixes). Re-run.
- `got True, want False` on a plain-verb domain: a parameter count was
  mis-read; print `(name, n_params, name.count('_'))` for each hit and
  tighten the second signal (e.g. require `name.count('_') >= 3`).
  Re-run.

---

## Worked airport-family examples (side-by-side)

Same domain, same plan, three valid outputs depending on authority:

**Form 1 — task example present (`drive(truck1, depot1, market1)`) AND
current task domain is pre-grounded airport:**

```
move_seg_rw_0_400_seg_rww_0_50_south_south_medium(airplane_CFBEG)
park_seg_rww_0_50_airside_a(airplane_CFBEG)
```

Fingerprint: head token is the full underscored schema (**no split** —
sub-track 2 is resolved by `is_pregrounded_domain(domain_path) == True`,
NOT by the example's head), wrapper is `name(args)` (sub-track 1 from
example), args are comma-separated (sub-track 1 from example), case
mirrors the example — uppercase object constants preserved (sub-track 3
from example). The example's plain-verb head (`drive`) is irrelevant to
sub-track 2 because the depot/truck family is not pre-grounded; its
head shape is **absent evidence** about airport schema expansion, not
negative evidence.

**Form 2 — no task example, canonical-IPC fallback (no case-sensitivity prose):**

```
(move airplane_cfbeg seg_rw_0_400 seg_rww_0_50 south south medium)
(park airplane_cfbeg seg_rww_0_50 airside_a)
```

Fingerprint: S-expression wrapper, space-separated, head is the split
base verb, baked-in constants are separate tokens, all lowercase.

**Form 2′ — no task example, but task prose says "action names and object
names in the generated plan should match the PDDL domain and PDDL
problem":**

```
(move airplane_CFBEG seg_rw_0_400 seg_rww_0_50 south south medium)
(park airplane_CFBEG seg_rww_0_50 airside_a)
```

Fingerprint: identical to Form 2 for wrapper and schema expansion, but
`airplane_CFBEG` is preserved because sub-track 3 (case) is driven by
the raw problem file. The planner emitted `airplane_cfbeg`; the case
map `{"airplane_cfbeg": "airplane_CFBEG", ...}` re-cased it at write
time.

**Wrong form (iter_4 defect — do not emit this):**

```
move(airplane_CFBEG, seg_rw_0_400, seg_rww_0_50, south, south, medium)
park(airplane_CFBEG, seg_pp_0_60, south)
```

Why wrong: the example's plain-verb head (`drive`) was allowed to
override the current task's pre-grounded domain evidence, triggering
schema splitting. Sub-track 2 must be resolved from
`is_pregrounded_domain(domain_path)` **before** reading the example's
head shape.

---

## Building a case map from the raw problem file

PDDLReader lowercases every identifier internally, so `str(parameter)`
and `action.name` only carry lowercase. To recover the original case,
scan the raw problem file text (and domain file for constants) and
tokenize `(:objects ...)` and `(:init ...)` blocks:

```python
OBJECT_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")

def _extract_section(text, header):
    """Return the body of `(:header ...)`, respecting nested parens."""
    m = re.search(rf"\(\s*:{header}\b", text, flags=re.IGNORECASE)
    if not m:
        return ""
    i = m.end()
    depth = 1
    start = i
    while i < len(text) and depth > 0:
        if text[i] == "(": depth += 1
        elif text[i] == ")": depth -= 1
        i += 1
    return text[start:i-1]

def build_case_map_from_problem_file(problem_path, domain_path=None):
    """Return {lowercase_token: original_case_token} for every identifier
    declared in :objects / :constants / :init of the raw files."""
    case_map = {}
    def add_tokens(section_text):
        for tok in OBJECT_TOKEN.findall(section_text):
            if tok.startswith(":") or tok in {"-"}:
                continue
            case_map.setdefault(tok.lower(), tok)
    for path in filter(None, [problem_path, domain_path]):
        with open(path) as f:
            text = f.read()
        for header in ("objects", "constants", "init"):
            add_tokens(_extract_section(text, header))
    return case_map

def task_prose_demands_match_pddl_files(task_description: str) -> bool:
    """Trigger the problem-file case authority."""
    t = task_description.lower()
    needles = [
        "match the pddl domain", "match the pddl problem",
        "match the pddl", "case-sensitive", "case sensitive",
        "action names and object names", "names in the generated plan should match",
    ]
    return any(n in t for n in needles)
```

Two runtime branches:
- Prose demands match → call `build_case_map_from_problem_file`, use its
  output as `case_map`.
- Prose does not demand match AND no example → leave `case_map` empty;
  `save-plan` emits `str(p)` verbatim.

**Verification (mandatory):**

```python
def verify_case_against_problem(plan_path, problem_path, domain_path=None):
    """Assert every plan token whose lowercase appears in the problem file
    matches the problem file's original case character-for-character."""
    case_map = build_case_map_from_problem_file(problem_path, domain_path)
    bad = []
    with open(plan_path) as f:
        for i, raw in enumerate(f, 1):
            s = raw.strip()
            if not s or s.startswith(";"):
                continue
            for tok in OBJECT_TOKEN.findall(s):
                want = case_map.get(tok.lower())
                if want and tok != want:
                    bad.append((i, tok, want, s))
    if bad:
        raise AssertionError(
            f"case mismatch vs problem file (first 5): {bad[:5]}"
        )
```

**On failure (what to do next):**
- `case mismatch` on tokens that **are** in the case map: `save-plan`
  received the case map but did not apply it uniformly. Re-check that
  `format_action` runs **every** emitted token (head and args) through
  `case_map.get(tok, tok)`. Re-emit, re-verify.
- `case mismatch` on tokens that are **not** in the case map but should
  be: `build_case_map_from_problem_file` missed the section — print the
  returned map, inspect `_extract_section` output, extend the header
  list if the identifier was declared under a non-standard section
  (`:private`, `:derived`, etc.). Rebuild, re-emit, re-verify.
- Case map empty when prose demands match:
  `task_prose_demands_match_pddl_files` did not trigger on this
  phrasing. Add the exact needle (lowercased) from the task description
  to the needle list, re-run from the top.

---

## Mirroring an example (Branch A), with pre-grounding override

```python
def parse_example_shape(example_line):
    """Extract the shape fingerprint from a single task-example line.
    NOTE: head_is_schema here is a tentative read from the example
    ALONE. The caller (format_like_example / verify_mirrors_example)
    MUST override it to True when the current task's domain is
    pre-grounded — the example cannot speak to schema expansion when
    its own domain family does not match the current task's."""
    s = example_line.strip()
    sexpr = s.startswith("(") and s.endswith(")")
    verb_call = (not sexpr) and "(" in s and s.endswith(")")
    comma_sep = "," in s
    has_upper = any(c.isupper() for c in s)
    if sexpr:
        head = s[1:-1].split()[0] if s[1:-1].split() else ""
    elif verb_call:
        head = s[: s.index("(")]
    else:
        head = s.split()[0] if s.split() else ""
    head_is_schema = head.count("_") >= 2 or "seg_" in head
    return {
        "sexpr": sexpr, "verb_call": verb_call, "comma": comma_sep,
        "upper": has_upper, "head": head, "head_is_schema": head_is_schema,
    }

def format_like_example(action_instance, shape, case_map=None,
                       domain_path=None):
    """Emit one line matching `shape`. Schema-expansion override: if
    the CURRENT task's domain is pre-grounded, force head_is_schema=True
    regardless of what the example's head looked like."""
    # ---- Pre-grounding override (sub-track 2 rank-1 authority) ----
    # The example tells us wrapper, separator, and case. It does NOT
    # tell us schema expansion when the current task's domain is
    # pre-grounded and the example's domain is not. Absent evidence,
    # not negative evidence.
    if domain_path and is_pregrounded_domain(domain_path):
        shape = {**shape, "head_is_schema": True}
    # ---------------------------------------------------------------
    name = action_instance.action.name
    params = [str(p) for p in action_instance.actual_parameters]
    if case_map:
        name = case_map.get(name, name)
        params = [case_map.get(p, p) for p in params]
    if shape["head_is_schema"]:
        head, args = name, params                 # keep schema whole
    else:
        head, args = recover_action(name, params) # Branch B split
    sep = ", " if shape["comma"] else " "
    if shape["verb_call"]:
        return f"{head}({sep.join(args)})"
    return f"({head} {' '.join(args)})" if args else f"({head})"
```

**Two runtime branches** on the schema-expansion decision inside
`format_like_example`:
- `head_is_schema=True` (either from the example's own head or forced
  by `is_pregrounded_domain(domain_path)`) → `head = action.name` as a
  single token, `args = free parameters only`. Never call
  `recover_action`.
- `head_is_schema=False` (no pre-grounding and example head is a plain
  verb) → run `recover_action` (Branch B) to split baked-in constants
  back out.

**Verification (mandatory):**

```python
def verify_mirrors_example(path, example_line, domain_path=None):
    with open(path) as f:
        first = next((l.strip() for l in f if l.strip() and not l.startswith(";")), "")
    want = parse_example_shape(example_line)
    got = parse_example_shape(first)
    # Pre-grounding override: when current domain is pre-grounded, the
    # emitted first line MUST have head_is_schema=True regardless of
    # the example. This closes the vacuous-pass gap where both the
    # example head and the (incorrectly-split) output are plain verbs.
    if domain_path and is_pregrounded_domain(domain_path):
        if not got["head_is_schema"]:
            raise AssertionError(
                f"schema-expansion violation: current domain is "
                f"pre-grounded but emitted head '{got['head']}' is a "
                f"plain verb. Expected the full pre-grounded schema as "
                f"the head token.\n  mine: {first}"
            )
        # Skip the example's head_is_schema compare — it is absent
        # evidence in this case, not an authority to diff against.
        compare_keys = ("sexpr", "verb_call", "comma", "upper")
    else:
        compare_keys = ("sexpr", "verb_call", "comma", "upper",
                       "head_is_schema")
    for k in compare_keys:
        if want[k] != got[k]:
            raise AssertionError(
                f"shape mismatch on {k}: want={want[k]} got={got[k]}\n"
                f"  example: {example_line.strip()}\n  mine:    {first}"
            )
```

**On failure (what to do next):**
- `schema-expansion violation`: `format_action` ran the pre-grounded
  action name through `recover_action` / `split_prefix` / an invented
  `:constants` matcher. Delete the splitting path when `domain_path` is
  pre-grounded; emit `action.name` as a single head token with only
  `actual_parameters` as args. Re-emit, re-verify. Cross-check against
  the oddity signal: the number of comma-separated args in the emitted
  `name(args)` line must equal the `:parameters` arity of that
  `:action` in the raw domain — airport actions have one free
  parameter (`?a - airplane`), so one arg inside `(...)`.
- `sexpr`/`verb_call` mismatch: `format_like_example` picked the wrong
  wrapper branch — check `shape['verb_call']` detection; re-emit.
- `comma` mismatch: swap the `sep` between `", "` and `" "`; re-emit.
- `upper` mismatch and example is uppercase: build a case map from the
  example (or the problem file, keyed to the example's convention),
  pass it as `case_map`; re-emit. Do not case-restore when example is
  lowercase AND no prose spec demands match.
- `head_is_schema` mismatch (only possible on non-pre-grounded
  domains): toggle the schema-splitting branch — if example keeps the
  schema whole, bypass `recover_action` and use `name` verbatim; if
  example splits, go through `recover_action`.

---

## Splitting a pre-grounded schema (Branch B — canonical-IPC fallback only)

**When to call `recover_action`:** only when `shape["head_is_schema"]`
is False **after** the pre-grounding override has run. In practice this
means: canonical-IPC fallback (no example, pre-grounded domain → split
to produce Form 2 / 2′) or a same-family example that itself shows a
split head. **Never** call it when the current domain is pre-grounded
and the example is from a non-pre-grounded family — that path produces
the iter_4 wrong form `move(airplane_CFBEG, seg_rw_0_400, ...)`.

Base-verb vocabulary for the airport family:

```python
AIRPORT_VERBS = [
    "move-back", "move_back", "pushback", "startup",
    "takeoff", "land", "move", "park",
]
DIRECTIONS = {"north", "south", "east", "west"}
TYPES = {"medium", "heavy", "light", "small", "large"}

def split_prefix(name, verbs):
    for v in sorted(verbs, key=len, reverse=True):
        if name == v or name.startswith(v + "_"):
            return v, name[len(v):].lstrip("_")
    return None, name

def regroup_tokens(tail):
    """Glue `seg_<...>` runs back together until a direction/type word
    closes the current segment."""
    raw = tail.split("_")
    out, buf = [], []
    i = 0
    while i < len(raw):
        tok = raw[i]
        if tok == "seg":
            buf = ["seg"]; i += 1
            while i < len(raw) and raw[i] not in DIRECTIONS and raw[i] not in TYPES and raw[i] != "seg":
                buf.append(raw[i]); i += 1
            out.append("_".join(buf))
        else:
            out.append(tok); i += 1
    return out

def recover_action(action_name, free_params):
    verb, tail = split_prefix(action_name, AIRPORT_VERBS)
    if verb is None:                       # plain verb — no split
        return action_name, list(free_params)
    constants = regroup_tokens(tail) if tail else []
    return verb, list(free_params) + constants
```

Two runtime branches inside `recover_action`:
- Plain verb (`split_prefix` returns `None`) → emit as-is with free
  parameters.
- Pre-grounded (base verb + non-empty tail) → regroup tail and prepend
  free parameters.

**Canonical save with optional case map (covers Form 2 and Form 2′,
NOT Form 1):**

```python
def save_plan_canonical(plan, output_path, case_map=None):
    cm = case_map or {}
    with open(output_path, "w") as f:
        for ai in plan.actions:
            free = [cm.get(str(p), str(p)) for p in ai.actual_parameters]
            name = cm.get(ai.action.name, ai.action.name)
            verb, args = recover_action(name, free)
            args = [cm.get(a.lower(), a) for a in args]
            verb = cm.get(verb.lower(), verb)
            line = f"({verb} {' '.join(args)})" if args else f"({verb})"
            f.write(line + "\n")
```

**Verification (mandatory):**

```python
def verify_canonical_plan(path, expected_verbs=AIRPORT_VERBS, case_map=None):
    errors = []
    with open(path) as f:
        for i, raw in enumerate(f, 1):
            s = raw.strip()
            if not s or s.startswith(";"):
                continue
            if not (s.startswith("(") and s.endswith(")")):
                errors.append((i, "missing parens", s)); continue
            inner = s[1:-1]
            if "," in inner:
                errors.append((i, "comma-separated args", s)); continue
            tokens = inner.split()
            if not tokens:
                errors.append((i, "empty action", s)); continue
            head = tokens[0]
            for t in tokens:
                want = (case_map or {}).get(t.lower())
                if want is not None:
                    if t != want:
                        errors.append((i, f"wrong case: got {t} want {want}", s))
                elif any(c.isupper() for c in t):
                    errors.append((i, f"unexpected uppercase token {t}", s))
            if head.lower() not in {v.lower() for v in expected_verbs} and (
                head.count("_") >= 2 or "seg_" in head
            ):
                errors.append((i, "schema-as-verb (split failed)", s))
    if errors:
        raise AssertionError(f"canonical plan verification failed: {errors[:5]}")
```

**On failure (what to do next):**
- `comma-separated args`: save loop built `f"{name}({', '.join(args)})"`.
  Rewrite to `f"({verb} {' '.join(args)})"` — parens outside, no commas.
  Re-run.
- `wrong case: got X want Y`: `save_plan_canonical` received the case
  map but did not route one of (verb, free params, regrouped
  constants) through it. Confirm all four lookups fire in the save
  loop. Re-emit, re-verify.
- `unexpected uppercase token`: a case helper is being applied without
  authority (no example, no prose spec, no case_map). Delete the
  helper and emit `str(p)` and `verb` verbatim; re-run.
- `schema-as-verb (split failed)`: `AIRPORT_VERBS` is missing the base
  verb used by this domain. Re-read the domain `:action` list, extend
  the verb list, re-run `save_plan_canonical`, re-verify.
- `missing parens`: the writer skipped formatting; check the loop wraps
  every line in `(...)`.

Only resubmit after verification returns without raising.

---

## Defensive two-form emit (optional, when example detection is ambiguous)

If you are uncertain whether a snippet in the task counts as an example,
write both forms to separate files and compare each first line against
the candidate example before choosing which to submit:

```python
save_plan_canonical(plan, "out_canonical.plan", case_map=case_map)       # Form 2 / 2′
save_plan(plan, "out_mirrored.plan",
          example_line=candidate_example, case_map=case_map,
          domain_path=domain_path)                                       # Form 1
# Then pick whichever first line matches candidate_example's fingerprint
# via verify_mirrors_example (with domain_path passed in); if neither
# matches, re-examine detection.
```

This costs little and protects against swings between the historical
failure modes (over-splitting vs under-splitting, over-casing vs
under-casing).

---

## If a reference `.plan` file is present in the task bundle

Treat it exactly like a task-example line (even higher confidence — it is
the format itself). Procedure:

```python
with open("reference.plan") as f:
    ref_lines = [l.strip() for l in f if l.strip() and not l.startswith(";")]
example_line = ref_lines[0]
# Then use format_like_example / verify_mirrors_example as above, and
# pass domain_path so the pre-grounding override fires if the reference
# plan happens to be from a non-pre-grounded family.
```

If per-line token counts diverge from your output, inspect the first
differing line in both files and align tokenization (missing split, extra
argument, reversed order). Re-save, re-verify.
