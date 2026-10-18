# Conveyor feasibility — grounded derivation

Use this reference when the handbook does not spell out a direct
`oven_model → required_speed` mapping, when `L_eff_cm` / dwell bounds must
be derived rather than read verbatim, OR when the handbook sentence used
arithmetic operators (`×`, `÷`, parentheses) that may have drifted during
PDF OCR. Skip when the handbook contains an explicit speed table keyed by
the oven model in use.

## The only sanctioned formulas

```
speed_max_cm_min = (L_eff_cm / t_min_s) * 60     # upper bound on speed
speed_min_cm_min = (L_eff_cm / t_max_s) * 60     # lower bound on speed
```

Any other formula — in particular anything that reduces to
`board_length_cm`, `board_length_cm / 60 * 60`, or similar — is fabrication
and must not be shipped.

## Grounding each input

Two inputs must be grounded in handbook text (or in oven_model geometry):

### `L_eff_cm` (effective heated length)

Branch 1 — handbook states it directly: use the stated value.

Branch 2 — handbook gives zone length and the oven_model encodes zone count.
Oven model strings typically start with a `<N>Z` prefix (e.g. `8Z_IR+Conv`,
`10Z_Convection`). Parse N and multiply:

```python
import re

def l_eff_from_oven_model(oven_model: str, zone_length_cm: float) -> float | None:
    m = re.match(r"(\d+)Z", oven_model)
    if m is None:
        return None
    zone_count = int(m.group(1))
    return zone_count * zone_length_cm
```

Branch 3 — neither branch succeeds: `L_eff_cm = None`.

### Dwell bound (`t_min_s` or `t_max_s`)

Branch 1 — handbook states a direct conveyor-dwell / time-in-oven bound: use it.

Branch 2 — handbook ties dwell to TAL (e.g. "dwell must cover the TAL
window"): then `t_min_s = cfg["tal_min_s"]`, `t_max_s = cfg["tal_max_s"]`.
Only valid when the handbook explicitly makes this link — do not assume it.

Branch 3 — neither branch succeeds: dwell bound is `None`.

## Operator-precedence / dimensional check (OCR drift guard)

PDF OCR routinely drops or misreads `×`, `÷`, parentheses, and superscripts.
A grounding-comment check confirms the *source sentence* is quoted; it does
NOT confirm the *operator arrangement* in code matches the handbook. After
translating any handbook formula to code, run a dimensional check with
sample values.

### Dimensional-balance table

Every input carries a unit; the formula output must reduce to the expected
unit on both sides. For `required_min_speed_cm_min` the expected output is
`cm/min`.

| Input | Unit |
|---|---|
| `L_eff_cm` | cm |
| `t_min_s`, `t_max_s` | s |
| `zone_length_cm` | cm |
| `boards_per_min` | boards/min |
| `board_length_cm` | cm/board |
| `loading_factor` | dimensionless |

Check: `(L_eff_cm / t_max_s) * 60` → `cm / s × s/min` → `cm/min` ✓.

### Worked example — ambiguous OCR operator

Handbook sentence (quoted correctly): *"the minimum conveyor speed is given
by boards per minute times board length divided by the loading factor."*
OCR drops the explicit "divided by" symbol in some extractions; the agent
must distinguish:

```python
# Arrangement A — loading_factor as divisor
speed_A = (boards_per_min * board_length_cm) / loading_factor
# units: (boards/min × cm/board) / 1 = cm/min  ✓

# Arrangement B — loading_factor as multiplier
speed_B = boards_per_min * board_length_cm * loading_factor
# units: (boards/min × cm/board) × 1 = cm/min  ✓  (also balances!)
```

Both arrangements produce `cm/min`, so units alone don't disambiguate.
Secondary test: instantiate with representative values and check which
magnitude is *plausible*. If `loading_factor ∈ [0.5, 1.0]`, arrangement A
yields a *larger* required speed (dividing by < 1 scales up); arrangement B
yields a smaller one. Combine with the pre-ship pass-rate heuristic: if
every run clears trivially under one arrangement, swap and re-check.

### Hard rule

If the dimensional check does not balance in your coded formula, the
operator placement is drifted — re-read the handbook source for the exact
sentence, consider both "divide by" and "multiply by" arrangements for each
dimensionless parameter, and record both candidate magnitudes before shipping.

## Compute, with explicit null-fallback

```python
def required_min_speed_cm_min(L_eff_cm, t_max_s):
    if L_eff_cm is None or t_max_s is None:
        # ungrounded input — do not fabricate
        return None
    # dimensional check: cm / s * 60(s/min) = cm/min  ✓
    return (L_eff_cm / t_max_s) * 60

def feasibility_record(oven_model, cfg, actual_speed_cm_min):
    L_eff = l_eff_from_oven_model(oven_model, cfg.get("zone_length_cm")) \
            if cfg.get("L_eff_cm") is None else cfg["L_eff_cm"]
    t_max = cfg.get("t_max_s")
    req   = required_min_speed_cm_min(L_eff, t_max)
    if req is None:
        reason = []
        if L_eff is None: reason.append("L_eff_cm")
        if t_max is None: reason.append("t_max_s")
        return {"required_min_speed_cm_min": None,
                "meets": False,
                "note": f"ungrounded: {','.join(reason)}"}
    return {"required_min_speed_cm_min": round(req, 2),
            "meets": bool(actual_speed_cm_min >= req)}
```

## Verification

Three post-write checks:

```python
# 1. Dimensional-balance check — instantiate with sample values.
sample_L_eff = 240.0   # cm
sample_t_max = 90.0    # s
sample_speed = required_min_speed_cm_min(sample_L_eff, sample_t_max)
assert sample_speed is not None and 50 < sample_speed < 500, (
    f"required_min_speed sample value {sample_speed} cm/min is outside the "
    f"plausible 50–500 range for typical reflow ovens — operator "
    f"precedence may be drifted; re-check the handbook arrangement."
)

# 2. Sanity-check magnitude on actual records.
req_values = [r["required_min_speed_cm_min"] for r in records
              if r["required_min_speed_cm_min"] is not None]
pass_rate = sum(r["meets"] for r in records) / max(len(records), 1)
if req_values and max(req_values) < 50 and pass_rate > 0.95:
    print("[warn] required_min_speed looks suspiciously permissive — "
          "swap divisor/multiplier arrangement and re-derive")
if req_values and min(req_values) > 500 and pass_rate < 0.05:
    print("[warn] required_min_speed looks suspiciously restrictive — "
          "swap divisor/multiplier arrangement and re-derive")

# 3. Null-fallback consistency.
for r in records:
    if r["required_min_speed_cm_min"] is None:
        assert r["meets"] is False, "null speed must imply meets=False"
```

**If check 1 fires:** the formula produces an implausible magnitude for
typical sample inputs. The operator arrangement is drifted — re-read the
handbook source, swap each dimensionless parameter between divisor and
multiplier, and re-run until the sample magnitude lands in the plausible
range AND matches an arrangement that balances units.

**If check 2 warns:** re-open the handbook. Search for "heated length",
"zone length", "time-in-oven", "dwell", "loading factor". Try the
alternative operator arrangement (divisor ↔ multiplier for `loading_factor`
or any similar dimensionless parameter) and compare pass rates.

**If check 3 fires:** fix the record — a null required_min_speed cannot be
paired with `meets=True`.

**If your own narrative contains "this seems suspicious" or "probably all
runs pass this":** that is itself a stop signal — treat it as a check-1/2
failure and re-derive before writing output.
