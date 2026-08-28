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
MATERIALIZED_DIRECTORY_ALIASES = {
    Path(".claude/skills"): Path(".agents/skills"),
    Path(
        "docs/examples/task-md/real-skillsbench/citation-check-network/environment"
    ): Path("docs/examples/task-md/real-skillsbench/citation-check/environment"),
    Path("docs/examples/task-md/real-skillsbench/citation-check-network/oracle"): Path(
        "docs/examples/task-md/real-skillsbench/citation-check/oracle"
    ),
    Path(
        "docs/examples/task-md/real-skillsbench/citation-check-network/verifier"
    ): Path("docs/examples/task-md/real-skillsbench/citation-check/verifier"),
}


def _source_files() -> list[tuple[Path, Path]]:
    process = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    index_modes = _git_index_modes()
    selected: list[tuple[Path, Path]] = []
    aliases: list[tuple[Path, Path]] = []
    for raw in process.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.name == ".env" or any(
            part in DENIED_PARTS for part in relative.parts
        ):
            continue
        if index_modes.get(relative) == "120000":
            target = MATERIALIZED_DIRECTORY_ALIASES.get(relative)
            if target is None:
                raise RuntimeError(f"unsafe release source path: {relative}")
            aliases.append((relative, target))
            continue
        source = (ROOT / relative).resolve(strict=True)
        if not source.is_relative_to(ROOT.resolve()) or not source.is_file():
            raise RuntimeError(f"unsafe release source path: {relative}")
        selected.append((relative, source))
    for alias, target in aliases:
        target_root = (ROOT / target).resolve(strict=True)
        if not target_root.is_relative_to(ROOT.resolve()) or not target_root.is_dir():
            raise RuntimeError(f"unsafe release alias target: {alias} -> {target}")
        target_files = [
            (relative, source)
            for relative, source in selected
            if relative.is_relative_to(target)
        ]
        if not target_files:
            raise RuntimeError(f"empty release alias target: {alias} -> {target}")
        selected.extend(
            (alias / relative.relative_to(target), source)
            for relative, source in target_files
        )
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


def _index_mode(relative: Path, index_modes: dict[Path, str]) -> str | None:
    mode = index_modes.get(relative)
    if mode is not None:
        return mode
    for alias, target in MATERIALIZED_DIRECTORY_ALIASES.items():
        if relative.is_relative_to(alias):
            source_relative = target / relative.relative_to(alias)
            return index_modes.get(source_relative)
    return None


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
            permissions = (
                0o755 if _index_mode(relative, index_modes) == "100755" else 0o644
            )
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
