#!/usr/bin/env python3
"""Atomically claim the next task from a queue file. Prints task id or exits 2 if empty."""
from __future__ import annotations

import fcntl
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: claim_queue_task.py QUEUE_FILE", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("r+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        lines = [ln.strip() for ln in fh.read().splitlines() if ln.strip()]
        if not lines:
            return 2
        task = lines[0]
        rest = "\n".join(lines[1:])
        if rest:
            rest += "\n"
        fh.seek(0)
        fh.truncate()
        fh.write(rest)
        fh.flush()
    print(task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
