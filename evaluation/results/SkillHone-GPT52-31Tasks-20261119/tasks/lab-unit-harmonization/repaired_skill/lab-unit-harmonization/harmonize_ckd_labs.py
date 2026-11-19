#!/usr/bin/env python3
"""Harmonize clinical lab CSVs with mixed units and numeric formats.

This script is intentionally *stdlib-only* so it can run in constrained
execution environments.

Core capabilities (reusable across datasets):
- Drop rows with missing values in any numeric column
- Parse numbers robustly (scientific notation, EU decimals, thousands separators,
  whitespace, and stray unit symbols)
- Range-based unit harmonization using per-feature conversion candidates
- Emit CSV with consistent numeric formatting (two decimals) and no scientific
  notation

Important: This script does NOT embed instance-specific paths. Use CLI args.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_REFERENCE_JSON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "reference", "ckd_lab_features.json"
)

# Compare tokens case-insensitively via .lower().
MISSING_TOKENS_LOWER = {
    "nan",
    "null",
    "none",
    "na",
    "n/a",
}

# Allow digits, sign, decimal separators, and scientific notation.
_NUM_CLEAN_RE = re.compile(r"[^0-9eE+\-\.,]")

# Scientific notation with comma/dot in the mantissa.
_SCI_RE = re.compile(r"^([+-]?[0-9.,]+)[eE]([+-]?\d+)$")

# Thousands-grouping patterns.
_THOUSANDS_COMMA_GROUP_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+$")
_THOUSANDS_DOT_GROUP_RE = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+$")
_SINGLE_COMMA_THOUSANDS_RE = re.compile(r"^[+-]?\d+,\d{3}$")
_SINGLE_DOT_THOUSANDS_RE = re.compile(r"^[+-]?\d+\.\d{3}$")


@dataclass(frozen=True)
class Conversion:
    multiplier: float
    from_unit: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    min_val: float
    max_val: float
    unit: Optional[str] = None
    conversions: Tuple[Conversion, ...] = ()


def _is_missing(raw: Optional[str]) -> bool:
    if raw is None:
        return True
    s = str(raw).strip()
    if s == "":
        return True
    if s.lower() in MISSING_TOKENS_LOWER:
        return True
    return False


def _normalize_separators(s: str) -> List[str]:
    """Normalize decimal/thousands separators and return candidate strings.

    Returns *strings* ready to be float()-parsed.

    Design:
    - If both ',' and '.' appear, treat the rightmost as the decimal separator.
    - If only one type of separator appears, prefer interpreting it as a decimal
      separator, with a thousands-grouping fallback for patterns like 1,234.

    The ordering matters: earlier candidates are preferred.
    """

    out: List[str] = []

    def add(v: str) -> None:
        if v not in out:
            out.append(v)

    if "," in s and "." in s:
        # Disambiguate by assuming the rightmost separator is the decimal.
        if s.rfind(",") > s.rfind("."):
            # "1.234,56" -> "1234.56"
            add(s.replace(".", "").replace(",", "."))
        else:
            # "1,234.56" -> "1234.56"
            add(s.replace(",", ""))
        return out

    if "," in s:
        # Many datasets use ',' as a decimal separator. Prefer that.
        if _THOUSANDS_COMMA_GROUP_RE.match(s) and s.count(",") > 1:
            # "1,234,567" -> "1234567"
            add(s.replace(",", ""))
            return out

        # Single comma: "12,34" -> "12.34"; but allow thousands fallback for "1,234".
        if s.count(",") == 1:
            add(s.replace(",", "."))
            if _SINGLE_COMMA_THOUSANDS_RE.match(s):
                add(s.replace(",", ""))
            return out

        # Weird multi-comma cases: best effort -> strip commas.
        add(s.replace(",", ""))
        return out

    if "." in s:
        if _THOUSANDS_DOT_GROUP_RE.match(s) and s.count(".") > 1:
            # "1.234.567" -> "1234567"
            add(s.replace(".", ""))
            return out

        # Single dot: prefer decimal, but allow thousands fallback for "1.234".
        add(s)
        if s.count(".") == 1 and _SINGLE_DOT_THOUSANDS_RE.match(s):
            add(s.replace(".", ""))
        elif s.count(".") > 1:
            add(s.replace(".", ""))
        return out

    add(s)
    return out


def parse_number_candidates(raw: Optional[str]) -> List[float]:
    """Parse a numeric field and return candidate floats (best-first).

    Handles:
    - Scientific notation (e.g., 1.23e2, 3,338e+00)
    - European decimals (comma as decimal separator)
    - Thousands separators (e.g., 1,234.5 or 1.234,5)
    - Whitespace and stray unit symbols

    Returns an empty list if the value is missing or unparseable.
    """

    if _is_missing(raw):
        return []

    s0 = str(raw).strip()

    # Accounting-style negatives: (123.4) -> -123.4
    neg_paren = s0.startswith("(") and s0.endswith(")")
    if neg_paren:
        s0 = s0[1:-1].strip()

    # Remove all whitespace characters.
    s0 = re.sub(r"\s+", "", s0)

    # Strip unit symbols/letters but keep separators and exponent markers.
    s0 = _NUM_CLEAN_RE.sub("", s0)

    if s0 in {"", "+", "-"}:
        return []

    if neg_paren and not s0.startswith("-"):
        s0 = "-" + s0.lstrip("+")

    candidates_s: List[str] = []

    m = _SCI_RE.match(s0)
    if m:
        mantissa, exp = m.group(1), m.group(2)
        for mv in _normalize_separators(mantissa):
            candidates_s.append(f"{mv}e{exp}")
    else:
        candidates_s.extend(_normalize_separators(s0))

    out: List[float] = []
    seen: set[float] = set()

    for s in candidates_s:
        if s in {"", "+", "-"}:
            continue
        try:
            v = float(s)
        except ValueError:
            continue
        if math.isnan(v) or math.isinf(v):
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)

    return out


def parse_number(raw: Optional[str]) -> Optional[float]:
    """Backwards-compatible single-number parser.

    Returns the first candidate from parse_number_candidates() or None.
    """

    cands = parse_number_candidates(raw)
    return cands[0] if cands else None


def in_range(value: float, lo: float, hi: float, tolerance: float = 0.0) -> bool:
    """Range check with optional relative tolerance."""

    if tolerance <= 0.0:
        return lo <= value <= hi

    # Expand the interval by a relative tolerance to account for floating error.
    lo_t = lo * (1.0 - tolerance)
    hi_t = hi * (1.0 + tolerance)
    return lo_t <= value <= hi_t


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def choose_harmonized_value(
    value: float,
    spec: FeatureSpec,
    *,
    tolerance: float,
    extra_multipliers: Sequence[float],
) -> Optional[float]:
    """Return a converted value that lands in the expected range.

    Strategy:
    1) If already in range (with tolerance), keep.
    2) Try declared conversion multipliers (alternative -> target).
    3) Try a small, generic set of power-of-10 multipliers as a last resort.

    If no candidate yields an in-range value, return None.

    Note: When a candidate is within the tolerance-expanded range but slightly
    outside the exact [min, max] bounds (float drift / rounding), we clamp to
    the nearest bound to ensure clean output.
    """

    lo, hi = spec.min_val, spec.max_val

    if in_range(value, lo, hi, tolerance=tolerance):
        return clamp(value, lo, hi)

    # First try feature-specific conversions.
    for conv in spec.conversions:
        cand = value * conv.multiplier
        if in_range(cand, lo, hi, tolerance=tolerance):
            return clamp(cand, lo, hi)

    # Then try generic multipliers (do not override known conversions).
    for m in extra_multipliers:
        cand = value * m
        if in_range(cand, lo, hi, tolerance=tolerance):
            return clamp(cand, lo, hi)

    return None


def format_two_decimals(value: float) -> str:
    # Using an f-string avoids scientific notation for ordinary magnitudes.
    return f"{value:.2f}"


def load_feature_reference(path: str) -> Dict[str, FeatureSpec]:
    """Load a machine-readable feature reference JSON.

    Expected structure (see reference/ckd_lab_features.json):
      {"features": {"Key": {"min": ..., "max": ..., "unit": ..., "conversions": [...]}}}
    """

    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    features = obj.get("features")
    if not isinstance(features, dict):
        raise ValueError(f"Invalid reference JSON (missing 'features'): {path}")

    specs: Dict[str, FeatureSpec] = {}
    for key, meta in features.items():
        if not isinstance(meta, dict):
            continue
        if "min" not in meta or "max" not in meta:
            continue
        try:
            lo = float(meta["min"])
            hi = float(meta["max"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid min/max for {key}: {e}")

        unit = meta.get("unit")
        conversions_meta = meta.get("conversions") or []
        conversions: List[Conversion] = []
        if isinstance(conversions_meta, list):
            for c in conversions_meta:
                if not isinstance(c, dict) or "multiplier" not in c:
                    continue
                try:
                    mult = float(c["multiplier"])
                except (TypeError, ValueError):
                    continue
                conversions.append(
                    Conversion(
                        multiplier=mult,
                        from_unit=c.get("from_unit"),
                        note=c.get("note"),
                    )
                )

        specs[key] = FeatureSpec(
            key=key,
            min_val=lo,
            max_val=hi,
            unit=unit if isinstance(unit, str) else None,
            conversions=tuple(conversions),
        )

    return specs


def _read_csv_rows(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header")
        rows = [dict(r) for r in reader]
        return list(reader.fieldnames), rows


def _write_csv_rows(path: str, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    # Explicitly use LF line endings to avoid stray '\r' characters.
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def harmonize_csv(
    *,
    input_csv: str,
    output_csv: str,
    reference_json: str,
    id_column: str,
    tolerance: float,
    extra_multipliers: Sequence[float],
    strict_format: bool,
) -> None:
    # Load reference once.
    specs = load_feature_reference(reference_json)

    os.makedirs(os.path.dirname(os.path.abspath(output_csv)) or ".", exist_ok=True)

    processed = 0
    kept = 0
    dropped_missing = 0
    dropped_unharmonizable = 0

    # Stream input -> output to keep memory use low.
    with (
        open(input_csv, "r", encoding="utf-8", newline="") as fin,
        open(output_csv, "w", encoding="utf-8", newline="") as fout,
    ):
        reader = csv.DictReader(fin)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header")

        fieldnames = list(reader.fieldnames)

        if id_column not in fieldnames:
            raise ValueError(f"id_column '{id_column}' not found in CSV header")

        numeric_cols = [c for c in fieldnames if c != id_column]

        missing_spec_cols = [c for c in numeric_cols if c not in specs]
        if missing_spec_cols:
            # Reusable guidance: make this a warning, not a hard failure, because
            # some datasets include additional columns. In strict mode, fail.
            msg = (
                "Reference missing specs for columns: "
                + ", ".join(missing_spec_cols[:10])
                + (" ..." if len(missing_spec_cols) > 10 else "")
            )
            if strict_format:
                raise ValueError(msg)
            print("WARNING:", msg, file=sys.stderr)

        writer = csv.DictWriter(fout, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        for row in reader:
            processed += 1

            out: Dict[str, str] = {id_column: str(row.get(id_column, "")).strip()}
            harmonized: Dict[str, float] = {}

            drop_reason: Optional[str] = None

            for col in numeric_cols:
                spec = specs.get(col)
                raw_val = row.get(col)

                candidates = parse_number_candidates(raw_val)
                if not candidates:
                    drop_reason = "missing"
                    break

                if spec is None:
                    # No spec: keep parsed numeric as-is (best candidate).
                    harmonized[col] = candidates[0]
                    continue

                hv: Optional[float] = None
                for v in candidates:
                    hv = choose_harmonized_value(
                        v,
                        spec,
                        tolerance=tolerance,
                        extra_multipliers=extra_multipliers,
                    )
                    if hv is not None:
                        break

                if hv is None:
                    drop_reason = "unharmonizable"
                    break

                harmonized[col] = hv

            if drop_reason == "missing":
                dropped_missing += 1
                continue
            if drop_reason == "unharmonizable":
                dropped_unharmonizable += 1
                continue

            for col in numeric_cols:
                out[col] = format_two_decimals(harmonized[col])

            writer.writerow(out)
            kept += 1

    # Optional strict validation.
    if strict_format:
        pattern = re.compile(r"^-?\d+\.\d{2}$")

        with open(output_csv, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                if "\r" in line:
                    raise AssertionError(f"Carriage return found on line {i}")
                if "e+" in line or "e-" in line or "E+" in line or "E-" in line:
                    raise AssertionError(f"Scientific notation found on line {i}")

        # Validate cell formats for numeric columns.
        _, check_rows = _read_csv_rows(output_csv)
        for r_i, r in enumerate(check_rows, start=1):
            for col in numeric_cols:
                s = str(r.get(col, ""))
                if not pattern.match(s):
                    raise AssertionError(f"Bad numeric format at row {r_i} col {col}: {s!r}")

    print(
        f"Processed {processed} rows; kept {kept}; "
        f"dropped_missing={dropped_missing}; dropped_unharmonizable={dropped_unharmonizable}",
        file=sys.stderr,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="Path to input CSV")
    p.add_argument("--output", required=True, help="Path to output CSV")
    p.add_argument(
        "--reference",
        default=DEFAULT_REFERENCE_JSON,
        help=(
            "Path to feature reference JSON "
            f"(default: bundled {os.path.relpath(DEFAULT_REFERENCE_JSON)})"
        ),
    )
    p.add_argument("--id-column", default="patient_id", help="Identifier column name")
    p.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Relative tolerance when checking ranges (default: 0.05)",
    )
    p.add_argument(
        "--extra-multipliers",
        default="0.1,0.01,0.001,10,100,1000",
        help="Comma-separated fallback multipliers to try if no explicit conversion matches",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Fail on missing reference specs and validate output formatting",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    reference = str(args.reference)
    if not os.path.isfile(reference):
        raise SystemExit(f"Reference JSON not found: {reference}")

    extra: List[float] = []
    for part in str(args.extra_multipliers).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            extra.append(float(part))
        except ValueError:
            raise SystemExit(f"Invalid multiplier: {part!r}")

    harmonize_csv(
        input_csv=str(args.input),
        output_csv=str(args.output),
        reference_json=reference,
        id_column=str(args.id_column),
        tolerance=float(args.tolerance),
        extra_multipliers=extra,
        strict_format=bool(args.strict),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
