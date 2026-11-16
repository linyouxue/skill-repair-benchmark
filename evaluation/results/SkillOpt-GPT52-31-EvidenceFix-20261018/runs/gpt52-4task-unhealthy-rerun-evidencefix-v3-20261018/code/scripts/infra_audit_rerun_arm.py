#!/usr/bin/env python3
"""Archive+requeue+rerun true infra-contaminated SkillOpt tasks for one arm.

Uses the same is_infra_contaminated logic as run_hyperparam_suite_supervisor.py.
Does not touch clean pass/fail results. Max 3 launch attempts.
"""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    wait_arm_idle,
)
import shutil

LOG_DIR = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite"
LOG_PATH = LOG_DIR / "infra_rerun.log"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def kill_run(run_id: str) -> None:
    for pattern in (
        f"run_method.py --run-id {run_id}",
        f"parallel_phase.py --run-id {run_id}",
    ):
        subprocess.run(["pkill", "-f", pattern], check=False)
    time.sleep(2)
    if pgrep_run(run_id):
        subprocess.run(["pkill", "-9", "-f", f"--run-id {run_id}"], check=False)
        time.sleep(1)
    log(f"killed workers for {run_id}; remaining={len(pgrep_run(run_id))}")


def classify_arm(run_id: str) -> dict[str, list[str]]:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    true_infra: list[str] = []
    clean_done: list[str] = []
    missing: list[str] = []
    for t in load_tasks():
        d = so / t
        mr = d / "method_result.json"
        if not mr.is_file():
            missing.append(t)
            continue
        if is_infra_contaminated(d):
            true_infra.append(t)
        else:
            clean_done.append(t)
    return {"true_infra": true_infra, "clean_done": clean_done, "missing": missing}


def write_queue(run_id: str, pending: list[str], done: list[str]) -> None:
    qdir = ROOT / "experiments" / run_id / "queue"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "skillopt.txt").write_text(
        "\n".join(pending) + ("\n" if pending else ""), encoding="utf-8"
    )
    (qdir / "skillopt.done").write_text(
        "\n".join(done) + ("\n" if done else ""), encoding="utf-8"
    )
    (qdir / "skillopt.failures").write_text("", encoding="utf-8")
    log(f"{run_id}: queue pending={len(pending)} done={len(done)}")


def archive_infra(run_id: str, targets: list[str]) -> Path | None:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    so.mkdir(parents=True, exist_ok=True)
    if not targets:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = so / f"_archived_infra_{stamp}"
    archive.mkdir(parents=True, exist_ok=True)
    moved = 0
    for task in targets:
        src = so / task
        if not src.exists():
            continue
        dest = archive / task
        if dest.exists():
            dest = archive / f"{task}__again"
        shutil.move(str(src), str(dest))
        moved += 1
    log(f"{run_id}: archived infra x{moved} -> {archive.name}")
    return archive


def passed_count(run_id: str, tasks: list[str]) -> int:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    n = 0
    for t in tasks:
        p = so / t / "method_result.json"
        if not p.is_file():
            continue
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("task_passed") is True:
                n += 1
        except Exception:
            continue
    return n


def run_arm(
    run_id: str,
    n: int,
    L: int,
    R: int,
    workers: int,
    max_attempts: int,
    include_missing: bool,
) -> dict[str, Any]:
    log(f"===== INFRA RERUN start run={run_id} n={n} L={L} R={R} workers={workers} =====")
    ensure_docker()
    kill_run(run_id)

    cls = classify_arm(run_id)
    log(
        f"{run_id}: pre true_infra={len(cls['true_infra'])} "
        f"clean_done={len(cls['clean_done'])} missing={len(cls['missing'])}"
    )
    log(f"{run_id}: true_infra tasks={cls['true_infra']}")

    pending = list(cls["true_infra"])
    if include_missing:
        pending = list(dict.fromkeys(pending + cls["missing"]))
        if cls["missing"]:
            log(f"{run_id}: also missing={cls['missing']}")

    if not pending:
        log(f"{run_id}: nothing to rerun")
        refresh_liveboard()
        return {
            "rerun": [],
            "leftover_infra": [],
            "leftover_missing": [],
            "clean_done": cls["clean_done"],
            "done": method_done_count(run_id),
            "passed": passed_count(run_id, cls["clean_done"]),
        }

    initial_targets = list(pending)
    archive_infra(run_id, cls["true_infra"])
    # after archive, those are missing; rebuild pending from classify
    cls = classify_arm(run_id)
    pending = list(cls["true_infra"])
    if include_missing:
        pending = list(dict.fromkeys(pending + cls["missing"]))
    write_queue(run_id, pending, cls["clean_done"])

    for attempt in range(1, max_attempts + 1):
        cls = classify_arm(run_id)
        pending = list(cls["true_infra"])
        if include_missing:
            pending = list(dict.fromkeys(pending + cls["missing"]))
        if not pending:
            log(f"{run_id}: cleared")
            break

        if cls["true_infra"]:
            archive_infra(run_id, cls["true_infra"])
            cls = classify_arm(run_id)
            pending = list(cls["true_infra"])
            if include_missing:
                pending = list(dict.fromkeys(pending + cls["missing"]))

        write_queue(run_id, pending, cls["clean_done"])
        if not pending:
            break

        ensure_docker()
        log(f"{run_id}: launch attempt={attempt}/{max_attempts} queue={len(pending)} {pending}")
        proc = launch_parallel(run_id, n, L, R, workers)
        while proc.poll() is None:
            refresh_liveboard()
            time.sleep(60)
        log(f"{run_id}: parallel_phase exited rc={proc.returncode} attempt={attempt}")
        wait_arm_idle(run_id)

        cls = classify_arm(run_id)
        log(
            f"{run_id}: post-attempt{attempt} infra={cls['true_infra']} "
            f"missing={cls['missing']} clean={len(cls['clean_done'])}"
        )
        if not cls["true_infra"] and not (include_missing and cls["missing"]):
            log(f"{run_id}: infra cleared")
            break

    refresh_liveboard()
    final = classify_arm(run_id)
    summary = {
        "rerun_targets_initial": initial_targets,
        "leftover_infra": final["true_infra"],
        "leftover_missing": final["missing"],
        "clean_done": final["clean_done"],
        "done": method_done_count(run_id),
        "passed": passed_count(run_id, load_tasks()),
    }
    log(f"{run_id}: FINAL {json.dumps(summary)}")
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--L", type=int, required=True)
    p.add_argument("--R", type=int, required=True)
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--include-missing", action="store_true")
    p.add_argument("--classify-only", action="store_true")
    args = p.parse_args()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    if args.classify_only:
        print(json.dumps(classify_arm(args.run_id), indent=2))
        return 0

    run_arm(
        args.run_id,
        args.n,
        args.L,
        args.R,
        args.workers,
        args.max_attempts,
        args.include_missing,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
