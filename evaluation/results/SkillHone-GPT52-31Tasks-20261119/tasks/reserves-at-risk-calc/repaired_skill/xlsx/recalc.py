#!/usr/bin/env python3
"""skills/xlsx/recalc.py

Excel formula recalculation + error scanning.

Why this exists:
- openpyxl preserves formulas but does not evaluate them.
- Many spreadsheet tasks require delivering a workbook with *cached values*
  populated (so graders that read with data_only=True can see results).

Strategy:
- If LibreOffice (`soffice`) is available, perform a headless "round-trip"
  conversion to XLSX. LibreOffice will open the workbook, recalculate, and
  export a fresh XLSX with updated cached values.
- If LibreOffice is not available, fall back to scanning the workbook for
  Excel error strings via openpyxl (no recalculation).

Output:
- Prints JSON with:
  - status: "success" | "errors_found"
  - total_errors
  - total_formulas (when openpyxl is available)
  - error_summary (when errors found)

This script is intentionally dependency-light: only stdlib is required for
LibreOffice recalculation; openpyxl is optional for scanning/counting.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

try:
    from openpyxl import load_workbook
except ModuleNotFoundError as e:  # pragma: no cover
    load_workbook = None  # type: ignore[assignment]
    _OPENPYXL_IMPORT_ERROR = e
else:
    _OPENPYXL_IMPORT_ERROR = None


EXCEL_ERRORS = ("#VALUE!", "#DIV/0!", "#REF!", "#NAME?", "#NULL!", "#NUM!", "#N/A")


def _count_formulas(filename: str) -> Optional[int]:
    if load_workbook is None:
        return None

    wb = load_workbook(filename, data_only=False)
    try:
        n = 0
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows():
                for cell in row:
                    v = cell.value
                    if isinstance(v, str) and v.startswith("="):
                        n += 1
        return n
    finally:
        wb.close()


def scan_excel_errors(filename: str, *, note: Optional[str] = None) -> dict:
    """Scan an XLSX for Excel error strings.

    This does NOT recalculate formulas. It inspects cached values and any
    literal error cells.
    """
    if load_workbook is None:
        return {
            "error": (
                "openpyxl is required to scan for Excel errors but is not installed: "
                f"{_OPENPYXL_IMPORT_ERROR}"
            )
        }

    path = Path(filename)
    if not path.exists():
        return {"error": f"File {filename} does not exist"}

    wb = load_workbook(filename, data_only=True)
    try:
        error_details: dict[str, list[str]] = {err: [] for err in EXCEL_ERRORS}
        total_errors = 0

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows():
                for cell in row:
                    v = cell.value
                    if v is None:
                        continue

                    if isinstance(v, str):
                        hit = None
                        if v in error_details:
                            hit = v
                        else:
                            # Be tolerant: sometimes errors appear embedded in text.
                            for err in EXCEL_ERRORS:
                                if err in v:
                                    hit = err
                                    break

                        if hit:
                            error_details[hit].append(f"{sheet_name}!{cell.coordinate}")
                            total_errors += 1

        out: dict = {
            "status": "success" if total_errors == 0 else "errors_found",
            "total_errors": total_errors,
            "error_summary": {},
        }
        if note:
            out["note"] = note

        for err_type, locations in error_details.items():
            if locations:
                out["error_summary"][err_type] = {
                    "count": len(locations),
                    "locations": locations[:20],
                }

        out["total_formulas"] = _count_formulas(filename)
        return out
    finally:
        wb.close()


def _as_lo_user_install_dir(path: Path) -> str:
    """Return a LibreOffice -env:UserInstallation URI (with trailing slash)."""
    uri = path.absolute().as_uri()
    return uri if uri.endswith("/") else (uri + "/")


def _recalc_with_libreoffice(
    filename: str,
    *,
    timeout: int,
    soffice_path: Optional[str] = None,
) -> dict:
    path = Path(filename)
    if not path.exists():
        return {"ok": False, "error": f"File {filename} does not exist"}

    soffice = soffice_path or shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return {"ok": False, "error": "LibreOffice ('soffice') not found on PATH."}

    abs_path = path.absolute()

    with tempfile.TemporaryDirectory(prefix="xlsx-recalc-") as td:
        td_path = Path(td)
        outdir = td_path / "out"
        outdir.mkdir(parents=True, exist_ok=True)

        # Isolate the LO profile to avoid first-run prompts and cross-run state.
        profile_dir = td_path / "lo_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_uri = _as_lo_user_install_dir(profile_dir)

        cmd = [
            soffice,
            "--headless",
            "--nologo",
            "--nodefault",
            "--norestore",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(outdir),
            str(abs_path),
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"LibreOffice timed out after {timeout} seconds",
                "hint": "Try increasing the timeout (e.g., 60).",
            }

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
            return {
                "ok": False,
                "error": "LibreOffice convert-to failed",
                "detail": tail,
            }

        expected = outdir / abs_path.name
        if expected.exists():
            out_file = expected
        else:
            candidates = sorted(outdir.glob("*.xlsx"))
            if not candidates:
                return {
                    "ok": False,
                    "error": "LibreOffice reported success but produced no .xlsx output",
                }
            if len(candidates) == 1:
                out_file = candidates[0]
            else:
                # Prefer same stem.
                same_stem = [p for p in candidates if p.stem == abs_path.stem]
                out_file = same_stem[0] if same_stem else candidates[0]

        # Replace original with recalculated export (atomic-ish).
        tmp_replace = abs_path.with_suffix(abs_path.suffix + ".recalc.part")
        shutil.copy2(out_file, tmp_replace)
        tmp_replace.replace(abs_path)

    return {"ok": True, "note": "LibreOffice recalculation completed"}


def recalc(filename: str, timeout: int = 30, *, soffice_path: Optional[str] = None) -> dict:
    """Recalculate formulas (if possible) and scan for Excel errors."""
    path = Path(filename)
    if not path.exists():
        return {"error": f"File {filename} does not exist"}

    # Recalculate (best-effort)
    soffice = soffice_path or shutil.which("soffice") or shutil.which("libreoffice")
    note_parts: list[str] = []

    if soffice:
        lo = _recalc_with_libreoffice(str(path), timeout=timeout, soffice_path=soffice_path)
        if not lo.get("ok"):
            # If LO is present but fails, surface the LO error.
            err = {k: v for k, v in lo.items() if k != "ok"}
            if "error" not in err:
                err["error"] = "LibreOffice recalculation failed"
            return err
        if lo.get("note"):
            note_parts.append(str(lo["note"]))
    else:
        note_parts.append("LibreOffice not available; scanned cached values only")

    if load_workbook is None:
        # We successfully recalculated (or not), but cannot scan without openpyxl.
        return {
            "status": "success",
            "total_errors": None,
            "total_formulas": None,
            "note": (
                "; ".join(note_parts)
                + "; openpyxl not installed so errors/formulas were not scanned"
            ),
        }

    scan_note = "; ".join(note_parts) if note_parts else None
    return scan_excel_errors(str(path), note=scan_note)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 skills/xlsx/recalc.py <excel_file> [timeout_seconds] [--soffice /path/to/soffice]")
        print("\nRecalculates formulas in an Excel file using LibreOffice (if available) and scans for Excel errors.")
        sys.exit(1)

    filename = sys.argv[1]

    soffice_path = None
    timeout = 30

    args = sys.argv[2:]
    if args and args[0].isdigit():
        timeout = int(args[0])
        args = args[1:]

    if args:
        if len(args) == 2 and args[0] == "--soffice":
            soffice_path = args[1]
        else:
            print(json.dumps({"error": f"Unrecognized arguments: {' '.join(args)}"}, indent=2))
            raise SystemExit(2)

    result = recalc(filename, timeout, soffice_path=soffice_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
