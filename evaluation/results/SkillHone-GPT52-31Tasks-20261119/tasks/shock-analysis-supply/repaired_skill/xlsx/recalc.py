#!/usr/bin/env python3
"""xlsx recalc + error scan.

Why this exists
---------------
Python libraries such as openpyxl can *write* formulas into .xlsx files, but
(unlike Excel / LibreOffice Calc) they do not evaluate formulas. Many automated
workflows therefore need a "recalculate then verify" step.

This script attempts to:
  1) Recalculate formulas using LibreOffice in headless mode (if available)
     by round-tripping the file through `--convert-to xlsx`.
  2) Scan the (possibly updated) workbook for Excel error values (#REF!, etc.)
  3) Count the number of formulas for context.

The script is designed to be self-contained in minimal environments:
- It will prefer system-installed `openpyxl`, but can also import it from
  vendored wheels in `skills/xlsx/vendor/*.whl`.
- If LibreOffice (`soffice` / `libreoffice`) is not available, it will still
  perform the scan and report that recalculation was skipped.

Usage
-----
  python3 skills/xlsx/recalc.py <excel_file.xlsx> [timeout_seconds]

Output
------
JSON on stdout. The historical keys are preserved:
  - status: "success" | "errors_found"
  - total_errors
  - total_formulas
  - error_summary (only when errors are found)

Additional diagnostic keys:
  - recalc: { attempted, engine, success, error? }
  - numeric_stats: lightweight magnitude summary for numeric cells
"""

from __future__ import annotations

import json
import posixpath
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET


EXCEL_ERRORS = ["#VALUE!", "#DIV/0!", "#REF!", "#NAME?", "#NULL!", "#NUM!", "#N/A"]


def _is_number(v) -> bool:
    # bool is a subclass of int in Python, exclude it
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _bootstrap_vendor_wheels() -> None:
    """Add vendored wheels to sys.path (if present)."""

    here = Path(__file__).resolve().parent
    vendor_dir = here / "vendor"
    if not vendor_dir.is_dir():
        return

    # Prepend wheels so they take precedence over any broken global installs.
    for whl in sorted(vendor_dir.glob("*.whl")):
        sys.path.insert(0, str(whl))


_bootstrap_vendor_wheels()

try:
    from openpyxl import load_workbook  # type: ignore
except ModuleNotFoundError as e:  # pragma: no cover
    load_workbook = None  # type: ignore
    _OPENPYXL_IMPORT_ERROR = e
else:
    _OPENPYXL_IMPORT_ERROR = None


def _which_libreoffice() -> str | None:
    """Return an executable path for LibreOffice/soffice if present."""

    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _trim(s: str | None, limit: int = 4000) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) <= limit:
        return s
    return s[: limit - 20] + "\n…(truncated)…"


def _recalc_in_place_with_libreoffice(xlsx_path: Path, timeout: int) -> dict:
    """Recalculate by converting xlsx->xlsx via LibreOffice.

    This approach is more portable than relying on user-installed macros.
    """

    engine = _which_libreoffice()
    if not engine:
        return {
            "attempted": False,
            "engine": None,
            "success": False,
            "error": "LibreOffice not found (no 'soffice' or 'libreoffice' in PATH).",
        }

    if xlsx_path.suffix.lower() != ".xlsx":
        return {
            "attempted": False,
            "engine": "libreoffice",
            "success": False,
            "error": "Only .xlsx files are supported for in-place recalculation.",
        }

    with tempfile.TemporaryDirectory(prefix="xlsx-recalc-") as td:
        tmp = Path(td)
        outdir = tmp / "out"
        profile = tmp / "profile"
        outdir.mkdir(parents=True, exist_ok=True)
        profile.mkdir(parents=True, exist_ok=True)

        cmd = [
            engine,
            "--headless",
            "--nologo",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--invisible",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(outdir),
            str(xlsx_path),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {
                "attempted": True,
                "engine": "libreoffice",
                "success": False,
                "error": f"LibreOffice timed out after {timeout} seconds.",
            }
        except FileNotFoundError as e:
            return {
                "attempted": True,
                "engine": "libreoffice",
                "success": False,
                "error": f"LibreOffice executable not found: {e}",
            }

        if proc.returncode != 0:
            return {
                "attempted": True,
                "engine": "libreoffice",
                "success": False,
                "returncode": proc.returncode,
                "stdout": _trim(proc.stdout),
                "stderr": _trim(proc.stderr),
                "error": _trim(proc.stderr) or _trim(proc.stdout) or f"LibreOffice exited with code {proc.returncode}.",
            }

        # LibreOffice usually writes the same basename into outdir.
        out_file = outdir / xlsx_path.name
        if not out_file.exists():
            candidates = sorted(outdir.glob("*.xlsx"))
            if len(candidates) == 1:
                out_file = candidates[0]
            else:
                return {
                    "attempted": True,
                    "engine": "libreoffice",
                    "success": False,
                    "stdout": _trim(proc.stdout),
                    "stderr": _trim(proc.stderr),
                    "error": "LibreOffice did not produce an output .xlsx file.",
                }

        shutil.copyfile(out_file, xlsx_path)
        return {"attempted": True, "engine": "libreoffice", "success": True}


def _a1_from_rc(row: int, col: int) -> str:
    """Convert 1-based (row,col) to an A1 coordinate."""

    # Minimal implementation to avoid importing more openpyxl utilities.
    letters = ""
    c = col
    while c:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def _safe_sheet_title_from_path(name: str) -> str:
    """Extract a friendly sheet title from xl/worksheets/sheetN.xml."""

    base = posixpath.basename(name)
    if base.lower().endswith(".xml"):
        base = base[:-4]
    return base


def _iter_sheet_result_cells(zf: zipfile.ZipFile, sheet_path: str) -> tuple[str, dict[tuple[int, int], str]]:
    """Return (sheet_title, {(row,col): v_string}) for cached results that are Excel errors."""

    # We parse *only* the worksheet XML and keep cells that contain string values
    # matching Excel error codes.
    try:
        xml_bytes = zf.read(sheet_path)
    except KeyError:
        return _safe_sheet_title_from_path(sheet_path), {}

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return _safe_sheet_title_from_path(sheet_path), {}

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    # Preload shared strings if present.
    shared: list[str] = []
    try:
        ss_bytes = zf.read("xl/sharedStrings.xml")
    except KeyError:
        ss_bytes = None
    if ss_bytes:
        try:
            ss_root = ET.fromstring(ss_bytes)
            for si in ss_root.findall("m:si", ns):
                # shared string items can have multiple <t> pieces
                parts = [t.text or "" for t in si.findall(".//m:t", ns)]
                shared.append("".join(parts))
        except ET.ParseError:
            shared = []

    # Determine which cell 't' types represent strings.
    error_cells: dict[tuple[int, int], str] = {}
    for c in root.findall(".//m:c", ns):
        r = c.get("r")
        if not r:
            continue
        # r is A1 ref; parse to (row,col)
        col_letters = ""
        row_digits = ""
        for ch in r:
            if "A" <= ch <= "Z" or "a" <= ch <= "z":
                col_letters += ch
            elif ch.isdigit():
                row_digits += ch
        if not col_letters or not row_digits:
            continue
        col_letters = col_letters.upper()
        col = 0
        for ch in col_letters:
            col = col * 26 + (ord(ch) - 64)
        row = int(row_digits)

        t = c.get("t")  # s=str in sharedStrings, str=inline string, etc.
        v_el = c.find("m:v", ns)
        if v_el is None or v_el.text is None:
            continue
        raw = v_el.text

        # Resolve value string depending on type.
        if t == "s":
            try:
                idx = int(raw)
                val = shared[idx] if 0 <= idx < len(shared) else ""
            except ValueError:
                val = ""
        else:
            val = raw

        if isinstance(val, str):
            for err in EXCEL_ERRORS:
                if val == err or err in val:
                    error_cells[(row, col)] = err
                    break

    return _safe_sheet_title_from_path(sheet_path), error_cells


def _find_sheet_xml_paths(zf: zipfile.ZipFile) -> list[str]:
    return sorted([n for n in zf.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")])


def _scan_errors_fast_xml(xlsx_path: Path) -> tuple[int, dict[str, list[str]]]:
    """Fast scan for cached Excel error strings by parsing worksheet XML.

    This avoids iterating over huge max_row/max_column grids via openpyxl.
    Note: it can only detect *cached* error values stored in the file.
    """

    details: dict[str, list[str]] = {e: [] for e in EXCEL_ERRORS}
    total = 0

    with zipfile.ZipFile(xlsx_path) as zf:
        for sheet_path in _find_sheet_xml_paths(zf):
            sheet_title, cells = _iter_sheet_result_cells(zf, sheet_path)
            for (r, c), err in cells.items():
                details[err].append(f"{sheet_title}!{_a1_from_rc(r, c)}")
                total += 1

    return total, details


def _scan_errors_openpyxl(xlsx_path: Path) -> tuple[int, dict[str, list[str]]]:
    wb = load_workbook(xlsx_path, data_only=True, read_only=True)  # type: ignore[misc]

    details: dict[str, list[str]] = {e: [] for e in EXCEL_ERRORS}
    total = 0

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str):
                    for err in EXCEL_ERRORS:
                        if err == v or err in v:
                            details[err].append(f"{ws.title}!{cell.coordinate}")
                            total += 1
                            break

    wb.close()
    return total, details


def _numeric_stats_openpyxl(
    xlsx_path: Path, *, max_cells: int = 200_000
) -> dict[str, object]:
    """Summarize numeric magnitudes.

    This is a lightweight sanity check to catch unit mistakes (e.g., billions vs
    units, percent vs fraction) without knowing anything about the workbook
    schema.

    It intentionally uses openpyxl with a cell cap to avoid pathological sheets.
    """

    wb = load_workbook(xlsx_path, data_only=True, read_only=True)  # type: ignore[misc]

    count = 0
    min_v: float | None = None
    max_v: float | None = None
    sum_abs = 0.0

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if _is_number(v):
                    fv = float(v)
                    if min_v is None or fv < min_v:
                        min_v = fv
                    if max_v is None or fv > max_v:
                        max_v = fv
                    sum_abs += abs(fv)
                    count += 1
                    if count >= max_cells:
                        wb.close()
                        return {
                            "attempted": True,
                            "success": True,
                            "method": "openpyxl",
                            "max_cells": max_cells,
                            "truncated": True,
                            "count": count,
                            "min": min_v,
                            "max": max_v,
                            "mean_abs": (sum_abs / count) if count else None,
                        }

    wb.close()
    return {
        "attempted": True,
        "success": True,
        "method": "openpyxl",
        "max_cells": max_cells,
        "truncated": False,
        "count": count,
        "min": min_v,
        "max": max_v,
        "mean_abs": (sum_abs / count) if count else None,
    }


def _count_formulas_fast_xml(xlsx_path: Path) -> int:
    """Count formulas by parsing worksheet XML for <f> tags."""

    n = 0
    with zipfile.ZipFile(xlsx_path) as zf:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for sheet_path in _find_sheet_xml_paths(zf):
            try:
                root = ET.fromstring(zf.read(sheet_path))
            except Exception:
                continue
            # Count all <f> formula elements
            n += len(root.findall(".//m:f", ns))
    return n


def _scan_errors(xlsx_path: Path) -> tuple[int, dict[str, list[str]]]:
    # Prefer the XML scanner for speed and robustness against sheets with huge
    # used ranges. Fall back to openpyxl if something goes wrong.
    try:
        return _scan_errors_fast_xml(xlsx_path)
    except Exception:
        return _scan_errors_openpyxl(xlsx_path)


def _count_formulas(xlsx_path: Path) -> int:
    try:
        return _count_formulas_fast_xml(xlsx_path)
    except Exception:
        wb = load_workbook(xlsx_path, data_only=False, read_only=True)  # type: ignore[misc]
        n = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    v = cell.value
                    if isinstance(v, str) and v.startswith("="):
                        n += 1
        wb.close()
        return n


def _numeric_stats(xlsx_path: Path) -> dict[str, object]:
    # This is best-effort; never fail the whole scan because of it.
    try:
        return _numeric_stats_openpyxl(xlsx_path)
    except Exception as e:  # pragma: no cover
        return {"attempted": True, "success": False, "error": _trim(str(e))}


def recalc(filename: str, timeout: int = 30) -> dict:
    path = Path(filename)
    if not path.exists():
        return {"error": f"File {filename} does not exist"}

    if _OPENPYXL_IMPORT_ERROR is not None:
        return {
            "error": "openpyxl is required to scan .xlsx files but is not available.",
            "detail": str(_OPENPYXL_IMPORT_ERROR),
        }

    recalc_info = _recalc_in_place_with_libreoffice(path, timeout)

    # Always scan after (attempted) recalculation.
    total_errors, error_details = _scan_errors(path)
    total_formulas = _count_formulas(path)

    result: dict = {
        "status": "success" if total_errors == 0 else "errors_found",
        "total_errors": total_errors,
        "total_formulas": total_formulas,
        "recalc": recalc_info,
        "numeric_stats": _numeric_stats(path),
    }

    if total_errors:
        result["error_summary"] = {
            err: {"count": len(locs), "locations": locs[:20]} for err, locs in error_details.items() if locs
        }

    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 skills/xlsx/recalc.py <excel_file.xlsx> [timeout_seconds]")
        print("\nRecalculates formulas (if LibreOffice is available) and scans for Excel errors.")
        print("\nReturns JSON with error details:")
        print("  - status: 'success' or 'errors_found'")
        print("  - total_errors: Total number of Excel errors found")
        print("  - total_formulas: Number of formulas in the file")
        print("  - error_summary: Breakdown by error type with locations")
        print("  - recalc: Details about whether recalculation was attempted")
        sys.exit(1)

    filename = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    print(json.dumps(recalc(filename, timeout), indent=2))


if __name__ == "__main__":
    main()
