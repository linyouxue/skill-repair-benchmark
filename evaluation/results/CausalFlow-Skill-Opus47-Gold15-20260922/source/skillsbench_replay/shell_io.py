"""Conservative file-access hints from terminal command text.

This module provides hints, not syscall-level truth. Every inferred access is
therefore represented as a ``may`` edge by the graph builder. Snapshot deltas
can later upgrade writes to observed evidence.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable, Optional, Tuple


REDIRECT_RE = re.compile(r"(?<!\d)(?:>>?|2>>?|&>)\s*([^\s;&|]+)")
INPUT_REDIRECT_RE = re.compile(r"(?<!<)<(?!<)\s*([^\s;&|]+)")
PATHISH_RE = re.compile(r"^(?:\.?\.?/|/|~?/)?[^\s]+(?:\.[A-Za-z0-9][A-Za-z0-9._-]*|/)$")
COMMAND_KEYS = ("command", "cmd", "script", "shell_command")
READ_COMMANDS = {
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "wc",
    "sort",
    "uniq",
    "cut",
    "paste",
    "diff",
    "cmp",
}
SEARCH_COMMANDS = {"grep", "rg", "find"}
WRITE_COMMANDS = {"touch", "mkdir", "truncate"}
DELETE_COMMANDS = {"rm", "rmdir", "unlink"}
COPY_COMMANDS = {"cp", "mv", "install"}
SHELL_KINDS = {"execute", "terminal", "shell", "bash", "command", "run", "other"}
LOCAL_SAFE_PROGRAMS = (
    READ_COMMANDS
    | SEARCH_COMMANDS
    | WRITE_COMMANDS
    | COPY_COMMANDS
    | {"echo", "printf", "tr", "sed", "awk", "python", "python3"}
)


@dataclass(frozen=True)
class ShellAccess:
    reads: Tuple[str, ...]
    writes: Tuple[str, ...]
    deletes: Tuple[str, ...]
    warnings: Tuple[str, ...]


def extract_command(arguments: object, title: str) -> tuple[Optional[str], str]:
    if isinstance(arguments, dict):
        for key in COMMAND_KEYS:
            value = arguments.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip(), f"arguments.{key}"
    stripped = title.strip()
    if stripped and _looks_like_command(stripped):
        return stripped, "title_fallback"
    return None, "missing"


def _looks_like_command(value: str) -> bool:
    if "\n" in value or any(
        marker in value for marker in (" >", " |", " &&", " --", "/")
    ):
        return True
    try:
        first = shlex.split(value)[0]
    except (ValueError, IndexError):
        return False
    return first in LOCAL_SAFE_PROGRAMS | DELETE_COMMANDS | {
        "ls",
        "pwd",
        "cd",
        "git",
        "uv",
        "pip",
        "npm",
    }


def infer_shell_access(command: str) -> ShellAccess:
    warnings: list[str] = []
    analysis_command = command
    first_line = command.splitlines()[0] if command.splitlines() else command
    if "<<" in first_line and "\n" in command:
        # The heredoc payload is data for the leading shell command, not more
        # shell syntax. Parsing Python/source text as shell arguments invents
        # paths such as ``next(iter(M.items``.
        analysis_command = first_line
        warnings.append("heredoc body not statically analyzed")
    try:
        tokens = shlex.split(analysis_command, posix=True)
    except ValueError as exc:
        return ShellAccess((), (), (), (f"shell parse failed: {exc}",))
    if not tokens:
        return ShellAccess((), (), (), ())

    writes = [
        _clean_path(match.group(1)) for match in REDIRECT_RE.finditer(analysis_command)
    ]
    writes = [path for path in writes if path]
    reads = [
        _clean_path(match.group(1))
        for match in INPUT_REDIRECT_RE.finditer(analysis_command)
    ]
    reads = [path for path in reads if path]
    deletes: list[str] = []

    # Analyze every simple command separated by common shell control tokens.
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in {";", "&&", "||", "|"}:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(token)

    for segment in segments:
        if not segment:
            continue
        program_index = _program_index(segment)
        if program_index is None:
            continue
        program = PurePosixPath(segment[program_index]).name
        args = [
            token for token in segment[program_index + 1 :] if not token.startswith("-")
        ]
        paths = [_clean_path(token) for token in args]
        paths = [path for path in paths if path]

        if program in READ_COMMANDS:
            reads.extend(paths)
        elif program in SEARCH_COMMANDS:
            # grep/rg's first positional token is usually a pattern.
            reads.extend(paths[1:] if len(paths) > 1 else paths)
        elif program in {"python", "python3", "bash", "sh", "zsh"}:
            if paths:
                reads.append(paths[0])
            warnings.append(f"{program} may access files not visible in command text")
        elif program in COPY_COMMANDS and len(paths) >= 2:
            reads.extend(paths[:-1])
            writes.append(paths[-1])
            if program == "mv":
                deletes.extend(paths[:-1])
        elif program in WRITE_COMMANDS:
            writes.extend(paths)
        elif program in DELETE_COMMANDS:
            deletes.extend(paths)
        elif program == "tee":
            writes.extend(paths)
        elif program == "sed":
            if paths:
                reads.append(paths[-1])
                if any(token == "-i" or token.startswith("-i") for token in segment):
                    writes.append(paths[-1])
        elif program == "awk" and paths:
            reads.append(paths[-1])
        elif program not in {"echo", "printf", "tr", "ls", "pwd", "cd"}:
            warnings.append(f"unknown command semantics: {program}")

    write_set = _dedupe(writes)
    return ShellAccess(
        reads=tuple(path for path in _dedupe(reads) if path not in write_set),
        writes=tuple(write_set),
        deletes=tuple(_dedupe(deletes)),
        warnings=tuple(_dedupe(warnings)),
    )


def local_replay_safety_reason(command: str) -> Optional[str]:
    """Return why a command is unsafe for the test-only host replay runner."""

    if any(marker in command for marker in ("`", "$(", "<<", "\n")):
        return "contains unsupported shell expansion or heredoc"
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return f"shell parse failed: {exc}"
    if not tokens:
        return "empty command"
    if any(token in {";", "&&", "||", "|"} for token in tokens):
        return "multiple shell commands require Docker replay"
    for token in tokens:
        cleaned = _clean_path(token)
        if cleaned and (
            cleaned.startswith("/") or ".." in PurePosixPath(cleaned).parts
        ):
            return f"path escapes replay workspace: {cleaned}"
    program_index = _program_index(tokens)
    if program_index is None:
        return "missing executable"
    program = PurePosixPath(tokens[program_index]).name
    if program not in LOCAL_SAFE_PROGRAMS:
        return f"program not allowlisted for local replay: {program}"
    if program in DELETE_COMMANDS:
        return "deletion commands require Docker replay"
    return None


def _program_index(tokens: list[str]) -> Optional[int]:
    for index, token in enumerate(tokens):
        if "=" in token and not token.startswith(("/", "./", "../")):
            key = token.split("=", 1)[0]
            if key.replace("_", "").isalnum():
                continue
        return index
    return None


def _clean_path(token: str) -> Optional[str]:
    value = token.strip("'\"(),[]{}")
    if not value or value in {"-", ".", ".."}:
        return None
    if (
        value.startswith(("http://", "https://"))
        or "=" in value
        and not value.startswith(("./", "../", "/"))
    ):
        return None
    if any(char in value for char in ("$", "{", "}", "*", "?")):
        return None
    if not PATHISH_RE.match(value):
        return None
    return PurePosixPath(value).as_posix()


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
