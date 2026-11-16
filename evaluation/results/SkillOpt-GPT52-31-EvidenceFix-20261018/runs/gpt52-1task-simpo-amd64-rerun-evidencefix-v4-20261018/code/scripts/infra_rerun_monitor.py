#!/usr/bin/env python3
"""Monitor infra reruns: finish n3L4R5 (up to 3 attempts), then after continue
finishes n5 missing work, audit+rerun n5L4R2 infra.
"""
from __future__ import annotations

import json
import os
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
CONTINUE_LOG = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite" / "continue_non_infra.log"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
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


def classify(run_id: str) -> dict[str, list[str]]:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    true_infra, clean, missing = [], [], []
    for t in load_tasks():
        d = so / t
        if not (d / "method_result.json").is_file():
            missing.append(t)
            continue
        if is_infra_contaminated(d):
            true_infra.append(t)
        else:
            clean.append(t)
    return {"true_infra": true_infra, "clean_done": clean, "missing": missing}


def archive_and_queue(run_id: str, targets: list[str], clean: list[str]) -> None:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    if targets:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = so / f"_archived_infra_{stamp}"
        archive.mkdir(parents=True, exist_ok=True)
        for t in targets:
            src = so / t
            if not src.exists():
                continue
            dest = archive / t
            if dest.exists():
                dest = archive / f"{t}__again"
            shutil.move(str(src), str(dest))
        log(f"{run_id}: archived {len(targets)} -> {archive.name}")
    # after archive, pending = targets + any still missing
    cls = classify(run_id)
    pending = list(dict.fromkeys(cls["true_infra"] + cls["missing"]))
    # restrict pending to original target set union missing from those targets
    # Actually: pending should be anything not clean
    pending = [t for t in load_tasks() if t not in set(cls["clean_done"])]
    qdir = ROOT / "experiments" / run_id / "queue"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "skillopt.txt").write_text(
        "\n".join(pending) + ("\n" if pending else ""), encoding="utf-8"
    )
    (qdir / "skillopt.done").write_text(
        "\n".join(cls["clean_done"]) + ("\n" if cls["clean_done"] else ""),
        encoding="utf-8",
    )
    (qdir / "skillopt.failures").write_text("", encoding="utf-8")
    log(f"{run_id}: queue pending={len(pending)} done={len(cls['clean_done'])}")


def wait_idle(run_id: str, poll: int = 45) -> None:
    stable = 0
    while True:
        procs = pgrep_run(run_id)
        cls = classify(run_id)
        q = ROOT / "experiments" / run_id / "queue" / "skillopt.txt"
        rem = (
            sum(1 for ln in q.read_text().splitlines() if ln.strip())
            if q.is_file()
            else 0
        )
        log(
            f"wait {run_id}: procs={len(procs)} queue={rem} "
            f"clean={len(cls['clean_done'])} infra={len(cls['true_infra'])} "
            f"missing={len(cls['missing'])}"
        )
        refresh_liveboard()
        if not procs and rem == 0:
            stable += 1
            if stable >= 2:
                return
        elif not procs and rem > 0:
            log(f"wait {run_id}: workers dead with queue remaining")
            return
        else:
            stable = 0
        time.sleep(poll)


def sweep_arm(run_id: str, n: int, L: int, R: int, max_attempts: int = 3) -> dict:
    log(f"===== sweep {run_id} n={n} L={L} R={R} =====")
    ensure_docker()
    for attempt in range(1, max_attempts + 1):
        cls = classify(run_id)
        pending = cls["true_infra"] + cls["missing"]
        if not pending:
            log(f"{run_id}: clean — no infra/missing")
            break
        log(f"{run_id}: attempt={attempt} pending_infra={cls['true_infra']} missing={cls['missing']}")
        # don't kill if already our workers running with matching queue
        procs = pgrep_run(run_id)
        if not procs:
            if cls["true_infra"]:
                archive_and_queue(run_id, cls["true_infra"], cls["clean_done"])
            else:
                archive_and_queue(run_id, [], cls["clean_done"])
            cls2 = classify(run_id)
            pending2 = [t for t in load_tasks() if t not in set(cls2["clean_done"])]
            if not pending2:
                break
            ensure_docker()
            proc = launch_parallel(run_id, n, L, R, 5)
            while proc.poll() is None:
                time.sleep(60)
                if int(time.time()) % 180 < 60:
                    refresh_liveboard()
            log(f"{run_id}: parallel_phase rc={proc.returncode} attempt={attempt}")
        wait_idle(run_id)
        cls = classify(run_id)
        if not cls["true_infra"] and not cls["missing"]:
            log(f"{run_id}: cleared after attempt {attempt}")
            break
        log(f"{run_id}: leftovers infra={cls['true_infra']} missing={cls['missing']}")
    final = classify(run_id)
    refresh_liveboard()
    return final


def continue_finished() -> bool:
    # Process gone OR log says finished
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        out = ""
    alive = any(
        "continue_non_infra.py" in ln and "grep" not in ln for ln in out.splitlines()
    )
    if CONTINUE_LOG.is_file():
        text = CONTINUE_LOG.read_text(encoding="utf-8")
        if "continue-non-infra: finished" in text:
            return True
    # If process alive, not finished
    if alive:
        return False
    # process dead — treat as finished (or crashed); caller will still classify n5
    return True


def continue_owns_n5() -> bool:
    return bool(pgrep_run("core25-gpt52-skillopt-n5L4R2-20260919")) or (
        not continue_finished()
        and CONTINUE_LOG.is_file()
        and "CONTINUE n5L4R2" in CONTINUE_LOG.read_text(encoding="utf-8")
        and "continue-non-infra: finished" not in CONTINUE_LOG.read_text(encoding="utf-8")
    )


def main() -> int:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    n3 = "core25-gpt52-skillopt-n3L4R5-20260919"
    n5 = "core25-gpt52-skillopt-n5L4R2-20260919"

    # Phase 1: n3 infra (workers may already be running from manual launch)
    log("monitor: phase1 n3L4R5 infra")
    final_n3 = sweep_arm(n3, 3, 4, 5, max_attempts=3)
    log(f"monitor: n3L4R5 final {json.dumps(final_n3)}")

    # Phase 2: wait for continue to release n5
    log("monitor: waiting for continue-non-infra to finish n5L4R2 missing work")
    while not continue_finished():
        # if continue still running n5, do not touch
        cls = classify(n5)
        log(
            f"monitor: continue alive; n5 clean={len(cls['clean_done'])} "
            f"infra={len(cls['true_infra'])} missing={len(cls['missing'])} "
            f"procs={len(pgrep_run(n5))}"
        )
        refresh_liveboard()
        time.sleep(90)

    # Ensure continue workers gone
    for _ in range(30):
        if not pgrep_run(n5):
            break
        # if continue finished but workers linger briefly
        time.sleep(10)
    # If continue died mid-run, wait until idle
    if pgrep_run(n5):
        log("monitor: n5 still has workers after continue exit; waiting idle")
        wait_idle(n5)

    log("monitor: phase2 n5L4R2 infra audit+rerun")
    cls = classify(n5)
    log(f"monitor: n5 pre-rerun {json.dumps(cls)}")
    final_n5 = sweep_arm(n5, 5, 4, 2, max_attempts=3)
    log(f"monitor: n5L4R2 final {json.dumps(final_n5)}")

    # Write summary appendix
    report = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite" / "infra_audit_report.md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = f"""

## Rerun results ({stamp})

### n3L4R5
- leftover_infra: {final_n3['true_infra']}
- leftover_missing: {final_n3['missing']}
- clean_done: {len(final_n3['clean_done'])}/25
- method_done: {method_done_count(n3)}/25

### n5L4R2
- leftover_infra: {final_n5['true_infra']}
- leftover_missing: {final_n5['missing']}
- clean_done: {len(final_n5['clean_done'])}/25
- method_done: {method_done_count(n5)}/25
"""
    with report.open("a", encoding="utf-8") as fh:
        fh.write(summary)
    refresh_liveboard()
    log("monitor: ALL DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
