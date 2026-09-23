"""Content-addressed workspace snapshots used to observe file writes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable

from skillsbench_replay.schema import CommandEvent, FileDelta, FileState


DEFAULT_IGNORES = {".git", ".pytest_cache", "__pycache__", ".DS_Store"}


@dataclass(frozen=True)
class WorkspaceSnapshot:
    root: str
    files: Dict[str, FileState]

    @classmethod
    def capture(
        cls,
        root: str | Path,
        *,
        ignore_names: Iterable[str] = DEFAULT_IGNORES,
    ) -> "WorkspaceSnapshot":
        base = Path(root).resolve()
        ignored = set(ignore_names)
        files: Dict[str, FileState] = {}
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(base)
            if any(part in ignored for part in relative.parts):
                continue
            if not path.is_file() or path.is_symlink():
                continue
            digest = _sha256(path)
            files[relative.as_posix()] = FileState(
                path=relative.as_posix(),
                sha256=digest,
                size=path.stat().st_size,
            )
        return cls(root=str(base), files=files)

    def diff(self, after: "WorkspaceSnapshot") -> list[FileDelta]:
        deltas: list[FileDelta] = []
        for path in sorted(set(self.files) | set(after.files)):
            before_state = self.files.get(path)
            after_state = after.files.get(path)
            if before_state is None:
                change = "added"
            elif after_state is None:
                change = "deleted"
            elif before_state.sha256 != after_state.sha256:
                change = "modified"
            else:
                continue
            deltas.append(
                FileDelta(
                    path=path,
                    change=change,
                    before_sha256=before_state.sha256 if before_state else None,
                    after_sha256=after_state.sha256 if after_state else None,
                )
            )
        return deltas

    def manifest(self) -> Dict[str, str]:
        return {path: state.sha256 for path, state in self.files.items()}


def attach_observed_writes(
    event: CommandEvent,
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
) -> CommandEvent:
    deltas = before.diff(after)
    event.observed_writes = tuple(
        delta.path for delta in deltas if delta.change in {"added", "modified"}
    )
    observed_deletes = tuple(
        delta.path for delta in deltas if delta.change == "deleted"
    )
    if observed_deletes:
        event.inferred_deletes = tuple(
            dict.fromkeys((*event.inferred_deletes, *observed_deletes))
        )
    return event


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
