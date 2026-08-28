"""Build a clean benchmark-executor archive from Git-visible source files."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "benchmark-executor-release.zip"
ARCHIVE_ROOT = "benchmark-executor"
DENIED_PARTS = frozenset(
    {
        ".git",
        ".venv",
        ".cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "jobs",
        "results",
        "smoke-jobs",
    }
)
SECRET_PATTERNS = (
    re.compile(rb"sk-or-v1-[A-Za-z0-9]{20,}"),
    re.compile(rb"sk-[A-Fa-f0-9]{32,}"),
)


def _source_files() -> list[tuple[Path, Path]]:
    process = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    selected: list[tuple[Path, Path]] = []
    for raw in process.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.name == ".env" or any(
            part in DENIED_PARTS for part in relative.parts
        ):
            continue
        source = (ROOT / relative).resolve(strict=True)
        if not source.is_relative_to(ROOT.resolve()) or not source.is_file():
            raise RuntimeError(f"unsafe release source path: {relative}")
        selected.append((relative, source))
    return sorted(selected, key=lambda item: item[0].as_posix())


def _scan_for_secrets(files: list[tuple[Path, Path]]) -> None:
    for relative, source in files:
        body = source.read_bytes()
        if any(pattern.search(body) for pattern in SECRET_PATTERNS):
            raise RuntimeError(f"possible API key in release source: {relative}")


def _git_index_modes() -> dict[Path, str]:
    process = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    modes: dict[Path, str] = {}
    for raw in process.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, _object_id, stage = metadata.split()
        if stage == b"0":
            modes[Path(os.fsdecode(raw_path))] = mode.decode("ascii")
    return modes


def _archive_body(relative: Path, source: Path) -> bytes:
    body = source.read_bytes()
    if relative.suffix.lower() == ".sh" or body.startswith(b"#!"):
        return body.replace(b"\r\n", b"\n")
    return body


def _validate_archive(output: Path) -> None:
    invalid_entries: list[str] = []
    with zipfile.ZipFile(output) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            body = archive.read(info)
            is_script = info.filename.lower().endswith(".sh") or body.startswith(b"#!")
            if is_script and b"\r\n" in body:
                invalid_entries.append(f"{info.filename}: CRLF in script")
            if body.startswith(b"#!") and b"\r" in body.partition(b"\n")[0]:
                invalid_entries.append(f"{info.filename}: CR in shebang")
    if invalid_entries:
        details = "\n".join(invalid_entries)
        raise RuntimeError(f"release archive failed line-ending validation:\n{details}")


def _write_archive(
    output: Path,
    files: list[tuple[Path, Path]],
    index_modes: dict[Path, str],
) -> None:
    with zipfile.ZipFile(
        output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for relative, source in files:
            permissions = 0o755 if index_modes.get(relative) == "100755" else 0o644
            info = zipfile.ZipInfo.from_file(
                source, f"{ARCHIVE_ROOT}/{relative.as_posix()}"
            )
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(
                info,
                _archive_body(relative, source),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    _validate_archive(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    files = _source_files()
    _scan_for_secrets(files)
    if args.check_only:
        print(f"release check passed: {len(files)} files")
        return

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_archive(output, files, _git_index_modes())
    print(f"created {output} ({len(files)} files)")


if __name__ == "__main__":
    main()
