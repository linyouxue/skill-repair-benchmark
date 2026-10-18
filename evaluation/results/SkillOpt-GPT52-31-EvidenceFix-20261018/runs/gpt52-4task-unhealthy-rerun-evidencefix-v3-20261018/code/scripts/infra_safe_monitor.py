#!/usr/bin/env python3
"""Safe infra monitor: finish n3L4R5 infra (max 3 attempts), then after
continue-non-infra finishes, audit+rerun n5L4R2. Never rewrites queue while
workers for that run_id are alive.
"""
from __future__ import annotations

import json
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_hyperparam_suite_supervisor import (  # noqa: E402
    ensure_docker,
    is_infra_contaminated,
    launch_parallel,
    load_tasks,
    method_done_count,
    pgrep_run,
    refresh_liveboard,
)

LOG = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite" / "infra_rerun.log"
CONTINUE_LOG = (
    ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite" / "continue_non_infra.log"
)


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def classify(run_id: str) -> tuple[list[str], list[str], list[str]]:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    ti, cl, ms = [], [], []
    for t in load_tasks():
        d = so / t
        if not (d / "method_result.json").is_file():
            ms.append(t)
            continue
        (ti if is_infra_contaminated(d) else cl).append(t)
    return ti, cl, ms


def archive_partials(run_id: str, tasks: list[str]) -> None:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arch = so / f"_archived_partial_{stamp}"
    moved = 0
    for t in tasks:
        d = so / t
        if d.is_dir() and not (d / "method_result.json").is_file():
            arch.mkdir(parents=True, exist_ok=True)
            dest = arch / t
            if dest.exists():
                dest = arch / f"{t}__again"
            shutil.move(str(d), str(dest))
            moved += 1
    if moved:
        log(f"{run_id}: archived {moved} partials -> {arch.name}")


def archive_infra(run_id: str, tasks: list[str]) -> None:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    if not tasks:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arch = so / f"_archived_infra_{stamp}"
    arch.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        src = so / t
        if not src.exists():
            continue
        dest = arch / t
        if dest.exists():
            dest = arch / f"{t}__again"
        shutil.move(str(src), str(dest))
    log(f"{run_id}: archived infra x{len(tasks)} -> {arch.name}")


def write_queue(run_id: str, pending: list[str], done: list[str]) -> None:
    q = ROOT / "experiments" / run_id / "queue"
    q.mkdir(parents=True, exist_ok=True)
    (q / "skillopt.txt").write_text(
        "\n".join(pending) + ("\n" if pending else ""), encoding="utf-8"
    )
    (q / "skillopt.done").write_text(
        "\n".join(done) + ("\n" if done else ""), encoding="utf-8"
    )
    (q / "skillopt.failures").write_text("", encoding="utf-8")
    log(f"{run_id}: queue pending={len(pending)} done={len(done)}")


def wait_idle(run_id: str, poll: int = 60) -> None:
    stable = 0
    while True:
        procs = pgrep_run(run_id)
        ti, cl, ms = classify(run_id)
        qf = ROOT / "experiments" / run_id / "queue" / "skillopt.txt"
        rem = (
            sum(1 for ln in qf.read_text().splitlines() if ln.strip())
            if qf.is_file()
            else 0
        )
        log(
            f"wait {run_id}: procs={len(procs)} queue={rem} "
            f"clean={len(cl)} infra={len(ti)} missing={len(ms)}"
        )
        if int(time.time()) % 180 < poll:
            refresh_liveboard()
        if not procs:
            stable += 1
            if stable >= 2:
                return
        else:
            stable = 0
        time.sleep(poll)


def sweep(run_id: str, n: int, L: int, R: int, max_attempts: int = 3) -> None:
    log(f"===== sweep {run_id} n={n} L={L} R={R} =====")
    for attempt in range(1, max_attempts + 1):
        ti, cl, ms = classify(run_id)
        pending = list(dict.fromkeys(ti + ms))
        if not pending:
            log(f"{run_id}: cleared")
            return
        procs = pgrep_run(run_id)
        if procs:
            log(f"{run_id}: workers already running ({len(procs)}); wait only")
            wait_idle(run_id)
        else:
            # prepare queue only when idle
            archive_infra(run_id, ti)
            archive_partials(run_id, ms)
            ti, cl, ms = classify(run_id)
            pending = list(dict.fromkeys(ti + ms))
            if not pending:
                log(f"{run_id}: cleared after archive")
                return
            write_queue(run_id, pending, cl)
            ensure_docker()
            log(f"{run_id}: launch attempt={attempt}/{max_attempts} queue={len(pending)}")
            proc = launch_parallel(run_id, n, L, R, 5)
            while proc.poll() is None:
                refresh_liveboard()
                time.sleep(90)
            log(f"{run_id}: phase rc={proc.returncode} attempt={attempt}")
            wait_idle(run_id)

        ti, cl, ms = classify(run_id)
        log(f"{run_id}: post-attempt infra={ti} missing={ms} clean={len(cl)}")
        if not ti and not ms:
            log(f"{run_id}: success")
            return
    ti, cl, ms = classify(run_id)
    log(f"{run_id}: max attempts reached leftovers infra={ti} missing={ms}")


def continue_done() -> bool:
    out = subprocess.check_output(["ps", "aux"], text=True)
    alive = any(
        "continue_non_infra.py" in ln and "grep" not in ln for ln in out.splitlines()
    )
    finished = CONTINUE_LOG.is_file() and (
        "continue-non-infra: finished" in CONTINUE_LOG.read_text(encoding="utf-8")
    )
    return finished or not alive


def passed_count(run_id: str) -> int:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    n = 0
    for t in load_tasks():
        p = so / t / "method_result.json"
        if not p.is_file():
            continue
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("task_passed") is True:
                n += 1
        except Exception:
            pass
    return n


def append_report(n3: str, n5: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ti3, cl3, ms3 = classify(n3)
    ti5, cl5, ms5 = classify(n5)
    report = (
        ROOT
        / "experiments"
        / "liveboards"
        / "gpt52-hyperparam-suite"
        / "infra_audit_report.md"
    )
    with report.open("a", encoding="utf-8") as fh:
        fh.write(
            f"""

## Rerun results ({stamp})

### n3L4R5
- clean_done: {len(cl3)}/25
- leftover_infra: {ti3}
- leftover_missing: {ms3}
- method_done: {method_done_count(n3)}/25
- passed_among_results: {passed_count(n3)}

### n5L4R2
- clean_done: {len(cl5)}/25
- leftover_infra: {ti5}
- leftover_missing: {ms5}
- method_done: {method_done_count(n5)}/25
- passed_among_results: {passed_count(n5)}
"""
        )


def main() -> int:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    n3 = "core25-gpt52-skillopt-n3L4R5-20260919"
    n5 = "core25-gpt52-skillopt-n5L4R2-20260919"

    log("safe-monitor: phase1 n3L4R5")
    sweep(n3, 3, 4, 5, max_attempts=3)

    log("safe-monitor: wait for continue-non-infra to finish (owns n5)")
    while not continue_done():
        ti, cl, ms = classify(n5)
        log(
            f"continue waiting; n5 clean={len(cl)} infra={len(ti)} "
            f"missing={len(ms)} procs={len(pgrep_run(n5))}"
        )
        refresh_liveboard()
        time.sleep(90)
    # settle if n5 workers linger briefly
    for _ in range(20):
        if not pgrep_run(n5):
            break
        log(f"n5 settle wait procs={len(pgrep_run(n5))}")
        time.sleep(15)

    log("safe-monitor: phase2 n5L4R2")
    sweep(n5, 5, 4, 2, max_attempts=3)

    append_report(n3, n5)
    refresh_liveboard()
    for rid, lab in [(n3, "n3L4R5"), (n5, "n5L4R2")]:
        ti, cl, ms = classify(rid)
        log(
            f"FINAL {lab}: clean={len(cl)} infra={ti} missing={ms} "
            f"passed={passed_count(rid)} done={method_done_count(rid)}"
        )
    log("safe-monitor: ALL DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
