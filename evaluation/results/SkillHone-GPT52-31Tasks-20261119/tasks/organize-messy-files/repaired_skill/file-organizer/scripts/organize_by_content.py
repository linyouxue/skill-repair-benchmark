#!/usr/bin/env python3
"""Organize files into folders based on extracted text content.

This script is intentionally generic and reusable. It does NOT encode any
trial-specific paths or dataset-specific keyword lists. It provides a small
framework for:

  * discovering candidate files
  * extracting text from PDFs/DOCX/PPTX (best-effort)
  * classifying into user-provided categories via simple keyword scoring
  * moving each file into exactly one category folder

Typical workflow:
  1) Write a categories.json config for *this* dataset / task
  2) Run with --dry-run to inspect the planned moves
  3) Re-run without --dry-run to execute

Usage example:
  python3 skills/file-organizer/scripts/organize_by_content.py \
    --src /path/to/input \
    --dest /path/to/output \
    --categories categories.json \
    --dry-run

categories.json format:
{
  "categories": [
    {
      "name": "topic_a",
      "folder": "topic_a",
      "keywords": ["keyword phrase", "singleword"],
      "negative_keywords": ["avoid phrase"]
    }
  ],

  // If no category reaches min_score, files go here.
  // For tasks that require every file to be in one of the given categories,
  // set default_folder to one of those category folders.
  "default_folder": "uncategorized",

  "extensions": [".pdf", ".docx", ".pptx"],

  // 0 means no limit
  "max_files": 0,

  // Cap extracted text per file
  "max_chars": 200000,

  // Minimum score to accept a category
  "min_score": 1,

  // PDF extraction: first/last page to read (keeps runs fast on large PDFs)
  "pdf_first_page": 1,
  "pdf_last_page": 2
}

Conflict handling:
- By default this script errors if the destination already contains a file with
  the same name (to avoid unintended renames).
- You can opt into renaming-on-conflict or skipping via --conflict-strategy.

Notes:
- The keyword approach is intentionally simple. For harder classification tasks,
  enrich the keywords or use this script to generate a draft mapping that you
  then spot-check.
- For DOCX/PPTX, this script reads XML from the OOXML zip directly to avoid
  extra dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable, NamedTuple, Optional
import xml.etree.ElementTree as ET


class Category(NamedTuple):
    """A classification target.

    Note: This is intentionally a NamedTuple (not a dataclass) so the module can
    be loaded via importlib loaders that do not pre-register the module in
    sys.modules.
    """

    name: str
    folder: str
    keywords: tuple[str, ...]
    negative_keywords: tuple[str, ...] = ()


def _run(cmd: list[str], timeout_s: int = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 999, "", f"{e.__class__.__name__}: {e}"


def extract_text_pdf(path: Path, *, max_chars: int, first_page: int, last_page: int) -> str:
    # Prefer pdftotext when available; it's fast and robust.
    rc, out, _err = _run(
        [
            "pdftotext",
            "-f",
            str(first_page),
            "-l",
            str(last_page),
            str(path),
            "-",  # stdout
        ]
    )
    if rc != 0:
        return ""
    return out.replace("\r", "")[:max_chars]


def _ooxml_text_from_zip(z: zipfile.ZipFile, member_paths: Iterable[str], max_chars: int) -> str:
    parts: list[str] = []
    total = 0
    for mp in member_paths:
        try:
            xml_bytes = z.read(mp)
        except KeyError:
            continue
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            continue
        for el in root.iter():
            if el.tag.endswith("}t") and el.text:
                parts.append(el.text)
                total += len(el.text) + 1
                if total >= max_chars:
                    return " ".join(parts)[:max_chars]
    return " ".join(parts)[:max_chars]


def extract_text_docx(path: Path, *, max_chars: int) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            return _ooxml_text_from_zip(z, ["word/document.xml"], max_chars)
    except zipfile.BadZipFile:
        return ""


def extract_text_pptx(path: Path, *, max_chars: int) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            slide_members = sorted(
                [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
            )
            notes_members = sorted(
                [
                    n
                    for n in z.namelist()
                    if n.startswith("ppt/notesSlides/notesSlide") and n.endswith(".xml")
                ]
            )
            return _ooxml_text_from_zip(z, slide_members + notes_members, max_chars)
    except zipfile.BadZipFile:
        return ""


def extract_text(
    path: Path,
    *,
    max_chars: int,
    pdf_first_page: int,
    pdf_last_page: int,
) -> str:
    suf = path.suffix.lower()
    if suf == ".pdf":
        return extract_text_pdf(
            path,
            max_chars=max_chars,
            first_page=pdf_first_page,
            last_page=pdf_last_page,
        )
    if suf == ".docx":
        return extract_text_docx(path, max_chars=max_chars)
    if suf == ".pptx":
        return extract_text_pptx(path, max_chars=max_chars)
    return ""


def score_category(text: str, cat: Category) -> int:
    # Simple keyword matching; counts occurrences (case-insensitive) with word-ish boundaries.
    # We avoid regex injection by escaping keywords.
    t = text.lower()
    score = 0

    for kw in cat.keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l:
            score += t.count(kw_l)
        else:
            score += len(re.findall(rf"\b{re.escape(kw_l)}\b", t))

    for nkw in cat.negative_keywords:
        nkw_l = nkw.lower().strip()
        if not nkw_l:
            continue
        if " " in nkw_l:
            score -= t.count(nkw_l)
        else:
            score -= len(re.findall(rf"\b{re.escape(nkw_l)}\b", t))

    return score


def iter_files(src: Path, extensions: set[str]) -> list[Path]:
    files: list[Path] = []
    for p in src.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            files.append(p)
    return sorted(files)


def safe_move(
    src: Path,
    dest_dir: Path,
    *,
    conflict_strategy: str,
) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    if dest.exists():
        if conflict_strategy == "skip":
            return None
        if conflict_strategy == "rename":
            stem = src.stem
            suf = src.suffix
            i = 1
            while True:
                cand = dest_dir / f"{stem}__dup{i}{suf}"
                if not cand.exists():
                    dest = cand
                    break
                i += 1
        else:
            raise FileExistsError(f"Destination already exists: {dest}")

    shutil.move(str(src), str(dest))
    return dest


def load_categories(cfg_path: Path) -> tuple[list[Category], dict]:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cats: list[Category] = []
    for c in cfg.get("categories", []):
        cats.append(
            Category(
                name=str(c["name"]),
                folder=str(c.get("folder") or c["name"]),
                keywords=tuple(map(str, c.get("keywords", []))),
                negative_keywords=tuple(map(str, c.get("negative_keywords", []))),
            )
        )
    return cats, cfg


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path, help="Source directory containing files")
    ap.add_argument(
        "--dest",
        required=True,
        type=Path,
        help="Destination base directory (category folders created here)",
    )
    ap.add_argument("--categories", required=True, type=Path, help="JSON config for categories")
    ap.add_argument("--dry-run", action="store_true", help="Print planned moves without moving")
    ap.add_argument(
        "--conflict-strategy",
        choices=["error", "rename", "skip"],
        default="error",
        help=(
            "What to do if a destination filename already exists: "
            "error (default) | rename (adds __dupN) | skip"
        ),
    )
    args = ap.parse_args(argv)

    cats, cfg = load_categories(args.categories)
    if not cats:
        print("ERROR: categories.json must define at least one category", file=sys.stderr)
        return 2

    default_folder = str(cfg.get("default_folder") or "uncategorized")
    extensions = set(map(str.lower, cfg.get("extensions") or [".pdf", ".docx", ".pptx"]))
    max_files = int(cfg.get("max_files") or 0)
    max_chars = int(cfg.get("max_chars") or 200000)
    min_score = int(cfg.get("min_score") or 1)
    pdf_first_page = int(cfg.get("pdf_first_page") or 1)
    pdf_last_page = int(cfg.get("pdf_last_page") or max(pdf_first_page, 1))

    if not args.src.exists():
        print(f"ERROR: src does not exist: {args.src}", file=sys.stderr)
        return 2

    files = iter_files(args.src, extensions)
    if max_files > 0:
        files = files[:max_files]

    moves: list[tuple[Path, str, int]] = []

    for f in files:
        text = extract_text(
            f,
            max_chars=max_chars,
            pdf_first_page=pdf_first_page,
            pdf_last_page=pdf_last_page,
        )
        # If extraction fails (e.g., scanned PDFs), fall back to filename so the
        # user can still get a draft mapping.
        if not text:
            text = f.name

        best_folder = default_folder
        best_score = -10**9
        for c in cats:
            sc = score_category(text, c)
            if sc > best_score:
                best_score = sc
                best_folder = c.folder

        if best_score < min_score:
            best_folder = default_folder

        moves.append((f, best_folder, best_score))

    # Report planned moves.
    for f, folder, sc in moves:
        print(f"{f} -> {folder} (score={sc})")

    # Simple summary.
    summary: dict[str, int] = {}
    for _f, folder, _sc in moves:
        summary[folder] = summary.get(folder, 0) + 1
    for folder in sorted(summary):
        print(f"SUMMARY {folder}: {summary[folder]}")

    if args.dry_run:
        return 0

    # Execute moves.
    for f, folder, _ in moves:
        try:
            moved_to = safe_move(
                f,
                args.dest / folder,
                conflict_strategy=args.conflict_strategy,
            )
        except FileExistsError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print(
                "Hint: rerun with --conflict-strategy rename/skip, or choose a different destination.",
                file=sys.stderr,
            )
            return 3
        _ = moved_to

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
