---
name: reflow-machine-maintenance-guidance
description: This skill should be considered when you need to answer reflow machine maintenance questions or provide detailed guidance based on thermocouple data, MES data or defect data and reflow technical handbooks. This skill covers how to obtain important concepts, calculations, definitions, thresholds, and others from the handbook and how to do cross validations between handbook and datasets.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks.

**Primary rule:** the handbook is authoritative for definitions, regions, inequalities (e.g., TAL at/above vs above), and numeric limits. Do not assume default industry values.

Based on the questions, first retrieve related info from the handbook and corresponding datasets. Frequently asked concepts include: preheat, soak, reflow, cooling, ramp, slope (°C/s), liquidus and wetting time, ramp rate limits, time above liquidus (TAL), peak temperature limits/margins, conveyor speed, dwell/time-in-oven, heated length/zone lengths, thermocouple placement (cold spot / worst case / representative TC), and audit/compliance criteria.

If the handbook provides multiple applicable constraints, implement all and treat a run as compliant only if it satisfies every applicable constraint.

## Common equations and deterministic methods

### Ramp (slope)
- Segment slope: `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`.
- Max ramp for a region: `max(s_i)` over segments fully inside the handbook-defined region.
- Region filtering patterns:
  - Temperature-band: include segments where **both endpoints** satisfy `tmin <= T <= tmax` (unless handbook states otherwise).
  - Zone-band: include if `zone_id in zones`.
  - Time-band: include if endpoints fall within the time band.

### Time above threshold (TAL / wetting)
Compute time above a threshold using linear interpolation at crossings. Use the handbook’s inequality:
- If handbook says “at or above liquidus” → use `>=` (inclusive).
- If handbook says “above liquidus” → use `>` (strict).
- If not explicit → default to inclusive (`>=`) to avoid undercounting plateau segments.

Reference implementation (inclusive-capable):

```python
def time_above_threshold_s(df_tc, thr, inclusive=True):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0

    def above(v):
        return v >= thr if inclusive else v > thr

    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue

        a0, a1 = above(y0), above(y1)
        if a0 and a1:
            total += (t1 - t0)
            continue
        if (not a0) and (not a1):
            continue
        if y1 == y0:
            continue

        frac = (thr - y0) / (y1 - y0)
        tcross = t0 + frac * (t1 - t0)
        if a0 and (not a1):
            total += (tcross - t0)
        elif (not a0) and a1:
            total += (t1 - tcross)

    return total
```

### Peak temperature
Per TC: `peak_tc = max(temp_c)`.
Handbook may define peak limits as absolute min/max or as a margin above liquidus; only use `liquidus + margin` if the handbook explicitly defines that derivation.

### Representative thermocouple
Follow handbook guidance first (e.g., “coldest solder joint”, “largest thermal mass”, “hottest point”).
Fallback if unspecified:
- One-sided upper limits (e.g., ramp <= limit): choose **maximum** metric across TCs (worst-case).
- One-sided lower limits (e.g., peak >= min): choose **minimum** metric across TCs (worst-case).
- Windowed limits (e.g., TAL within [min, max]): choose the **most critical** TC deterministically:
  - if any violating, pick the largest violation magnitude; else pick the smallest margin to the nearest boundary; tie by smallest `tc_id`.

### Conveyor speed and dwell/time-in-oven (correct min/max mapping)
Let `time_in_oven = L_eff_cm / speed_cm_s`.
- If handbook sets a **maximum allowed time** in oven `t_max_s`, that implies a **minimum speed**:
  - `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`
- If handbook sets a **minimum required dwell time** `t_min_s`, that implies a **maximum speed**:
  - `speed_max_cm_min = (L_eff_cm / t_min_s) * 60`
- If handbook provides explicit speed min/max, use them directly.

When interpreting MES conveyor speed, do not guess units; convert only when units are explicit (e.g., m/min to cm/min). If units cannot be determined, treat speed as unknown.
