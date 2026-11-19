---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---

When to invoke:
1. Whenever the task involves reflow-related questions from thermocouple data, MES data or defect data AND handbook-defined regions/windows/limits.
2. When you must extract numeric limits / temperature regions / timing windows / margins / feasibility rules from handbook.pdf.
3. When you must compute run-level metrics from time–temperature thermocouple traces in a deterministic way.

This skill is designed to make the agent:
- retrieve definitions/limits from the handbook (with citations), and
- compute metrics with predictable tie-breaks and interpolation.


## Tooling guardrails (prevents common execution failures)

1. **Terminal tools may accept only ONE command per call.**
   - If you need multiple steps, either:
     - chain sub-commands with `&&` or `;` **inside one shell line**, or
     - run multiple tool calls.
   - Do **not** paste multiple independent commands separated by blank lines.

2. **Use ASCII-only shell commands.**
   - If you see errors like `ls: invalid option -- ...` with odd/invisible characters, retype the command; avoid copying formatted text that may contain Unicode lookalikes.

3. **Prefer a single Python heredoc per call.**
   - Run one `python - <<'PY' ... PY` block per tool call.
   - If you need additional shell steps, put them in a *separate* tool call, or wrap everything in `bash -lc '...multi-line...'`.


## Quick input inspection (safe one-liner)

```sh
ls -al /app/data && for f in /app/data/*.csv; do echo ""; echo "=== $(basename \"$f\") ==="; head -n 6 "$f"; done
```


## Handbook PDF extraction (deterministic, citation-friendly)

Goal: build a compact `cfg` object from `handbook.pdf` and carry **page-anchored quotes** into your reasoning. Do **not** guess numeric limits.

### 1) Check available PDF tooling (ONE command)

```sh
python - <<'PY'
import importlib.util, shutil, sys
mods = ["pdfplumber", "pypdf", "PyPDF2", "fitz"]
for m in mods:
    print(f"{m}: {'OK' if importlib.util.find_spec(m) else 'NO'}")
print("pdftotext:", shutil.which("pdftotext"))
print("python:", sys.version.split()[0])
PY
```

### 2) Extract searchable text

Prefer Python extraction so you can keep **page numbers**.

`pypdf` example (print only matching snippets, not the whole book):

```sh
python - <<'PY'
from pypdf import PdfReader
import re
path = "/app/data/handbook.pdf"
needle = re.compile(r"(preheat|ramp rate|\bc/s\b|tal|time above liquidus|liquidus|peak|conveyor|dwell)", re.I)
reader = PdfReader(path)
for i, page in enumerate(reader.pages, start=1):
    text = (page.extract_text() or "")
    if needle.search(text):
        # print a short, bounded snippet for auditability
        lines = [ln.strip() for ln in text.splitlines() if needle.search(ln)]
        print(f"\n--- page {i} ---")
        for ln in lines[:12]:
            print(ln[:200])
PY
```

If no Python PDF library is available but `pdftotext` exists, convert once and then search the `.txt` file.

#### If NO PDF libraries/tools are available (offline fallback)

Some execution environments have **no** PDF Python packages and **no** `pdftotext`, and you may also be unable to `pip install` / `apt-get`. In that case, you can still extract enough text for limits/definitions by:
- scanning PDF **streams**,
- inflating `FlateDecode` content with `zlib`, and
- decoding **literal strings** `(...)` and (optionally) **hex strings** `<...>`.

Use a bounded keyword search (print only short matched contexts):

```sh
python - <<'PY'
import re, zlib
from pathlib import Path

pdf_path = Path("/app/data/handbook.pdf")
data = pdf_path.read_bytes()

stream_re = re.compile(rb"stream\r?\n")
endstream_re = re.compile(rb"\r?\nendstream")

# 1) collect raw streams + their dict headers
streams = []
for m in stream_re.finditer(data):
    start = m.end()
    m2 = endstream_re.search(data, start)
    if not m2:
        continue
    end = m2.start()
    ds = data.rfind(b"<<", max(0, m.start() - 800), m.start())
    de = data.rfind(b">>", max(0, m.start() - 800), m.start())
    hdr = data[ds : de + 2] if (ds != -1 and de != -1 and de > ds) else b""
    streams.append((hdr, data[start:end]))

# 2) decompress FlateDecode streams when present
def decomp(hdr: bytes, raw: bytes) -> bytes:
    if b"FlateDecode" in hdr:
        for wbits in (None, zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 32):
            try:
                return zlib.decompress(raw) if wbits is None else zlib.decompress(raw, wbits)
            except Exception:
                pass
        return b""
    return raw

# 3) extract PDF strings: literal (...) + hex <...> (skipping dictionaries << >>)
_ws = set(b" \n\r\t\f\x00")

def parse_pdf_strings(buf: bytes) -> list[bytes]:
    out: list[bytes] = []
    i = 0
    n = len(buf)
    while i < n:
        c = buf[i : i + 1]
        if c == b"(":
            i += 1
            depth = 1
            s = bytearray()
            while i < n and depth > 0:
                ch = buf[i : i + 1]
                if ch == b"\\":
                    if i + 1 >= n:
                        i += 1
                        continue
                    nxt = buf[i + 1 : i + 2]
                    # octal escapes
                    if nxt in b"01234567":
                        j = i + 1
                        oct_digits = bytearray()
                        while j < n and len(oct_digits) < 3 and buf[j : j + 1] in b"01234567":
                            oct_digits.append(buf[j])
                            j += 1
                        try:
                            s.append(int(oct_digits.decode("ascii"), 8))
                        except Exception:
                            pass
                        i = j
                        continue
                    # common escapes
                    mapping = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"", b"f": b""}
                    if nxt in mapping:
                        s.extend(mapping[nxt])
                        i += 2
                        continue
                    s.extend(nxt)
                    i += 2
                    continue
                if ch == b"(":
                    depth += 1
                    s.extend(ch)
                    i += 1
                    continue
                if ch == b")":
                    depth -= 1
                    if depth > 0:
                        s.extend(ch)
                    i += 1
                    continue
                s.extend(ch)
                i += 1
            out.append(bytes(s))
            continue
        if c == b"<":
            # skip dictionaries << >>
            if i + 1 < n and buf[i + 1 : i + 2] == b"<":
                i += 1
                continue
            j = i + 1
            hx = bytearray()
            while j < n and buf[j : j + 1] != b">":
                if buf[j : j + 1] in _ws:
                    j += 1
                    continue
                hx.append(buf[j])
                j += 1
            i = j + 1 if j < n else n
            try:
                hx2 = re.sub(rb"[^0-9A-Fa-f]", b"", bytes(hx))
                if len(hx2) % 2 == 1:
                    hx2 = hx2[:-1]
                bts = bytes.fromhex(hx2.decode("ascii")) if hx2 else b""
                # handle BOM-marked UTF-16
                if bts.startswith(b"\xfe\xff"):
                    out.append(bts[2:].decode("utf-16-be", "ignore").encode("utf-8"))
                elif bts.startswith(b"\xff\xfe"):
                    out.append(bts[2:].decode("utf-16-le", "ignore").encode("utf-8"))
                else:
                    out.append(bts)
            except Exception:
                pass
            continue
        i += 1
    return out

def extract_text(hdr: bytes, raw: bytes) -> str:
    buf = decomp(hdr, raw)
    parts = parse_pdf_strings(buf)
    txt = b" ".join(parts).decode("latin1", errors="replace")
    txt = re.sub(r"\s+", " ", txt)
    return txt

needle = re.compile(r"(preheat|ramp|rate of rise|\bc/s\b|tal|wetting|liquidus|peak|conveyor|dwell)", re.I)

for i, (hdr, raw) in enumerate(streams):
    txt = extract_text(hdr, raw)
    if not needle.search(txt):
        continue
    # print a bounded context around the first match in this stream
    m = needle.search(txt)
    a = max(0, m.start() - 220)
    b = min(len(txt), m.end() + 420)
    print(f"\n--- stream {i} ---")
    print(txt[a:b])
PY
```

### 3) Normalize into a config object (NO hard-coded instance values)

Store *only* what you can justify from the handbook (plus citations):

```python
cfg = {
  # temperature region for the ramp calculation:
  # either {"type":"temp_band", "tmin":..., "tmax":...}
  # or {"type":"zone_band", "zones":[...]}
  # or {"type":"time_band", "t_start_s":..., "t_end_s":...}
  "preheat_region": None,

  "ramp_limit_c_per_s": None,

  # Typically comes from MES; the handbook defines how to use it.
  "tal_threshold_c_source": "solder_liquidus_c",
  "tal_min_s": None,
  "tal_max_s": None,

  "peak_margin_c": None,

  # Structured conveyor feasibility rule(s)
  "conveyor_rule": None,

  # Optional: how to pick the representative thermocouple
  # e.g., {"for_ramp":"max", "for_tal":"min", "for_peak":"min"}
  "tc_selection": None,
}
```

If you cannot find a value, keep it `None` and propagate `null` in outputs.


### Interpreting handbook preheat wording for ramp-rate calculations

Handbooks often describe preheat in wording that can be read two ways. Pick the interpretation that best matches the *exact* handbook sentence (and cite it).

- **Target-at-exit wording (common):** “in the preheat section, the goal is to preheat the assembly **to temperatures … between X°C and Y°C** …”.
  - This typically means: during preheat the assembly is being heated **up to** a cutoff, and by the end of preheat it should be within that target range.
  - For ramp-rate calculations, treat **Y°C** as the preheat cutoff and compute the maximum **positive** slope on segments that occur while the trace is at/below that cutoff (include boundary-crossing segments so you don’t underestimate right at the cutoff).
  - Use the “until cutoff” approach (e.g., `max_pos_slope_until_temp(df_tc, tmax_preheat_c=Y)`), and only use `[X,Y]` as a band if the handbook clearly says the ramp requirement applies *within* that band.

- **Operate-within-band wording (less common):** “preheat is **between X°C and Y°C**” / “maintain the assembly between X°C and Y°C for …”.
  - This indicates a true **temperature band** window.
  - Compute the maximum **positive** slope on segments that overlap the band `[X, Y]` (include boundary-crossing segments).
  - Use `max_slope_in_temp_band(df_tc, tmin=X, tmax=Y)`.

If the handbook is ambiguous, prefer the interpretation that matches the intent of the limit. A “minimize rate of rise” / thermal-shock limit usually applies from ambient through preheat, so the **cutoff** method is often the safer default.


## Handbook “where to look” checklist

Search the handbook for these common sections/tables:
- Thermal profile overview: defines “preheat”, “soak”, “reflow”, “cooling”.
- Ramp rate guidance: “ramp”, “slope”, “°C/s”, “C/s”.
- Liquidus & wetting time: “liquidus”, “time above liquidus”, “TAL”, “wetting”.
- Peak temperature guidance: “peak”, “minimum peak”, “margin above liquidus”.
- Conveyor / dwell feasibility: “conveyor speed”, “dwell time”, “heated length”, “time-in-oven”.
- Thermocouple placement: “cold spot”, “worst case”, “representative sensor”.

If the handbook provides multiple applicable constraints, implement all and use the stricter constraint (document the choice in code comments).


## Deterministic thermocouple computation recipes

### 1) Sorting and de-dup rules

Always sort samples by time before any computation:

```python
df_tc = df_tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```

Ignore segments where `dt <= 0` (non-monotonic timestamps).

### 2) Segment slope (ramp rate)

Finite-difference slope on consecutive samples:
- `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`
- the “max ramp” is `max(s_i)` over the region.

**Spec note:** “maximum temperature ramp rate” typically means the maximum **positive** slope during heating. When computing a max ramp for a heating region (e.g., preheat), clamp negative slopes to 0 (or ignore them) before taking the max. Otherwise, a run with only cooling segments in the region could produce a misleading negative “max”.

Region filtering patterns:
- Temperature band region: include segments that overlap the band `tmin..tmax`.
  - Simple rule: include the segment if it intersects the band (avoid dropping boundary-crossing segments).
- Zone band region: filter by `zone_id in zones`.
- Time band region: filter by `t_start_s <= time_s <= t_end_s`.

Robust implementations:

**A) Temperature-band example (use only if the handbook explicitly defines the ramp window as a band):**

```python
def max_slope_in_temp_band(df_tc, tmin, tmax):
    g = df_tc.sort_values("time_s", kind="mergesort")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0:
            continue
        y0, y1 = y[i-1], y[i]
        # keep any segment that overlaps the band
        if max(y0, y1) < tmin or min(y0, y1) > tmax:
            continue
        s = (y1 - y0) / dt
        # "Max ramp" in heating contexts is the max **positive** slope.
        # Ignore cooling segments so runs without preheat heating don't produce negative ramps.
        if s < 0:
            continue
        best = s if best is None else max(best, s)
    return best  # None if no valid segments
```

**B) Preheat-to-cutoff example (use only when the handbook explicitly defines preheat as starting near ambient and ending at a cutoff temperature):**

```python
def max_pos_slope_until_temp(df_tc, tmax_preheat_c):
    """Max positive slope while the trace is at or below the preheat cutoff.

    Use this only if the handbook defines preheat as starting near ambient and
    ending at a cutoff temperature.

    Segments are included if either endpoint is <= tmax_preheat_c.
    This captures boundary-crossing segments (avoids underestimation).
    """
    g = df_tc.sort_values("time_s", kind="mergesort")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            continue
        y0, y1 = y[i - 1], y[i]
        # include segments that occur before/at the preheat cutoff
        if min(y0, y1) > tmax_preheat_c:
            continue
        s = (y1 - y0) / dt
        if s < 0:
            continue
        best = s if best is None else max(best, s)
    return best
```

### 3) Time above threshold with linear interpolation

For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation:

```python
def time_above_threshold_s(df_tc, thr):
    g = df_tc.sort_values("time_s", kind="mergesort")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0
    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue

        # fully above
        if y0 > thr and y1 > thr:
            total += (t1 - t0)
            continue

        # crossing: interpolate crossing time
        crosses = (y0 <= thr < y1) or (y1 <= thr < y0)
        if crosses and (y1 != y0):
            frac = (thr - y0) / (y1 - y0)
            tcross = t0 + frac * (t1 - t0)
            if y0 <= thr and y1 > thr:
                total += (t1 - tcross)
            else:
                total += (tcross - t0)
    return total
```

### 4) Deterministic sensor selection (tie-breaks)

When reducing multiple thermocouples to one run-level result, use stable rules:

- If selecting **maximum** metric (e.g., ramp limit violations): choose **largest value**, tie-break by **smallest `tc_id`**.
- If selecting **minimum** metric (e.g., “coldest” TAL or peak): choose **smallest value**, tie-break by **smallest `tc_id`**.

Example implementation:

```python
# items: list of objects with fields .tc_id (str) and .value (float)

# max metric
best = sorted(items, key=lambda x: (-x.value, x.tc_id))[0]

# min metric
best = sorted(items, key=lambda x: (x.value, x.tc_id))[0]
```

### 5) Peak and margin

Per TC:
- `peak_tc = max(temp_c)`

Run-level “coldest” behavior (common handbook guidance):
- `min_peak_run = min(peak_tc)` (tie by tc_id)

Requirement:
- `required_peak = liquidus + peak_margin`

### 6) Conveyor feasibility (speed bounds)

Handbooks vary; represent feasibility rules as a structured object.

Common physics (time in oven):
- `time_in_oven_s = 60 * L_eff_cm / speed_cm_min`

So:
- Minimum required dwell time `t_min_s` across effective heated length `L_eff_cm` implies a **maximum** speed:
  - `speed_max_cm_min = (L_eff_cm / t_min_s) * 60`
- Maximum allowed time-in-oven `t_max_s` implies a **minimum** speed:
  - `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`
- If both exist, allowed speed range is `[speed_min_cm_min, speed_max_cm_min]`.

Output mapping tip:
- If the output schema only has `required_min_speed_cm_min`, populate it with `speed_min_cm_min` when available, else `null`.
- Still compute `meets` using **all** applicable bounds (min and/or max) from the handbook.

If parameters are missing, output:
- `required_min_speed_cm_min = null`
- `meets = false` (unless the task explicitly allows "unknown")


## Selecting the best run per board_family (quality + efficiency)

When asked to pick a “best” run per `board_family` using MES + defect data, define an explicit, reproducible rule and keep tie-breaks deterministic.

One general-purpose ranking (customize to the task’s wording):
1. Prefer runs that are compliant on required checks (e.g., ramp/TAL/peak/speed) if the task defines compliance.
2. Prefer lower defect rate.
   - Example: `defect_rate = total_defects / units` where `units` comes from MES (boards/panels) if available.
   - If `units` is unavailable, fall back to `total_defects`.
3. Prefer higher throughput (e.g., `boards_per_min`).
4. Prefer lower `downtime_s`.
5. Final tie-break: `run_id` ascending.

`runner_up_run_ids` should include the other runs for that family, sorted ascending, unless the task specifies a different ordering.


## Output construction guardrails

1) Sorting
- Lists: sort by primary ID (run_id / board_family) lexicographically.
- Dicts keyed by ID: emit in sorted key order.

2) Rounding and NaNs
- Round floats to 2 decimals.
- Never emit NaN/Inf; use `null`.

```python
import math

def r2(x):
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(round(float(x), 2))
```

3) Missing thermocouple data
- If a run has no TC records (or no valid segments for a metric), set numeric outputs to `null`.
- If the task states missing TC implies failure for a requirement, follow the task.


## Minimal end-to-end scaffold

```python
import os, json, math
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

defects = pd.read_csv(os.path.join(DATA_DIR, "test_defects.csv"))

runs["run_id"] = runs["run_id"].astype(str)
tc["run_id"]   = tc["run_id"].astype(str)
tc["tc_id"]    = tc["tc_id"].astype(str)

defects["run_id"] = defects["run_id"].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")

defects = defects.sort_values(["run_id"], kind="mergesort")

# 1) Retrieve cfg from handbook: regions, limits, windows, margins, feasibility rules
cfg = {...}

# 2) Compute per-run metrics deterministically with stable tie-breaks and interpolation
# 3) Build JSON objects with sorted IDs and 2dp rounding
# 4) Write outputs into /app/output
```

---

Sanity checks before writing outputs
- ID fields are strings.
- Arrays sorted lexicographically.
- Floats rounded to 2 decimals.
- No NaN/Inf in JSON.
- Sensor selection uses deterministic tie-breaks.
- Any “time above threshold” uses interpolation (not naive threshold counting).
