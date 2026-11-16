#!/usr/bin/env python3
"""Unattended suite supervisor: run SkillOpt arms sequentially with infra retries.

Order (from configs/gpt52_hyperparam_suite.json):
  1) n3L4R2  2) n5L4R2  3) n3L4R5

For each arm:
  - ensure Docker is up
  - wait if workers already running, else launch parallel_phase
  - wait until queue empty and no run_method processes
  - archive+requeue infrastructure-contaminated tasks (up to max sweeps)
  - refresh liveboard

Also refreshes the suite liveboard every --refresh-sec seconds in a side thread.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "configs" / "gpt52_hyperparam_suite.json"
LOG_DIR = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite"
LOG_PATH = LOG_DIR / "supervisor.log"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_suite() -> dict[str, Any]:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def load_tasks() -> list[str]:
    path = ROOT / "configs" / "core25_tasks.txt"
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def docker_ok() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
    except Exception:
        return False


def ensure_docker(timeout_sec: int = 180) -> None:
    if docker_ok():
        return
    log("Docker down; trying to start Docker Desktop…")
    subprocess.run(["open", "-a", "Docker"], check=False)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if docker_ok():
            log("Docker is up")
            return
        time.sleep(3)
    log("WARNING: Docker still down after wait; continuing anyway")


def pgrep_run(run_id: str) -> list[str]:
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        return []
    hits = []
    for line in out.splitlines():
        if "grep" in line:
            continue
        if f"--run-id {run_id}" in line and (
            "run_method.py" in line or "parallel_phase.py" in line
        ):
            hits.append(line)
    return hits


def kill_run(run_id: str) -> None:
    # Kill run_method and parallel_phase for this run_id only.
    for pattern in (
        f"run_method.py --run-id {run_id}",
        f"parallel_phase.py --run-id {run_id}",
    ):
        subprocess.run(["pkill", "-f", pattern], check=False)
    time.sleep(2)
    leftover = pgrep_run(run_id)
    if leftover:
        subprocess.run(["pkill", "-9", "-f", f"--run-id {run_id}"], check=False)
        time.sleep(1)
    log(f"killed workers for {run_id}; remaining={len(pgrep_run(run_id))}")


def arm_env(n: int, L: int, R: int) -> dict[str, str]:
    env = os.environ.copy()
    # Load .env lightly
    env_path = ROOT / ".env"
    if env_path.is_file():
        for ln in env_path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env["PATH"] = "/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:" + env.get(
        "PATH", ""
    )
    env["UV_CACHE_DIR"] = env.get("UV_CACHE_DIR") or "/private/tmp/skillopt-eva-uv-cache"
    env["SKILLOPT_EVA_DIAGNOSIS_N"] = str(n)
    env["SKILLOPT_EVA_EDIT_BUDGET_L"] = str(L)
    env["SKILLOPT_EVA_REPAIR_ROUNDS_R"] = str(R)
    env.pop("SKILLOPT_EVA_SMOKE", None)
    env.pop("DEBUG", None)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def launch_parallel(run_id: str, n: int, L: int, R: int, workers: int) -> subprocess.Popen:
    ensure_docker()
    env = arm_env(n, L, R)
    log_path = ROOT / "experiments" / run_id / "logs" / "supervisor_phase.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    fh.write(f"\n===== launch {datetime.now().isoformat()} n={n} L={L} R={R} workers={workers} =====\n")
    fh.flush()
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "parallel_phase.py"),
        "--run-id",
        run_id,
        "--phase",
        "skillopt",
        "--workers",
        str(workers),
    ]
    log(f"launch {run_id} n={n} L={L} R={R} workers={workers}")
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT)


def queue_remaining(run_id: str) -> int:
    q = ROOT / "experiments" / run_id / "queue" / "skillopt.txt"
    if not q.is_file():
        return 0
    return sum(1 for ln in q.read_text(encoding="utf-8").splitlines() if ln.strip())


def method_done_count(run_id: str) -> int:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    if not so.is_dir():
        return 0
    return sum(
        1
        for p in so.glob("*/method_result.json")
        if not p.parent.name.startswith("_")
    )


def wait_arm_idle(run_id: str, poll_sec: int = 30) -> None:
    """Wait until no workers and queue empty (or all 25 results exist)."""
    tasks = load_tasks()
    stable = 0
    ticks = 0
    while True:
        procs = pgrep_run(run_id)
        rem = queue_remaining(run_id)
        done = method_done_count(run_id)
        log(f"wait {run_id}: procs={len(procs)} queue={rem} done={done}/{len(tasks)}")
        ticks += 1
        # ~every 3 minutes at poll_sec=30
        if ticks % 6 == 0:
            refresh_liveboard()
        if not procs and (rem == 0 or done >= len(tasks)):
            stable += 1
            if stable >= 2:  # two consecutive idle polls
                return
        else:
            stable = 0
        # If workers died with remaining queue work, exit wait so caller can relaunch.
        if not procs and rem > 0 and done < len(tasks):
            log(f"wait {run_id}: workers dead with remaining queue; returning for relaunch")
            return
        time.sleep(poll_sec)


def is_infra_contaminated(task_dir: Path) -> bool:
    mr = task_dir / "method_result.json"
    if not mr.is_file():
        # partial dir counts as needing redo if non-empty
        return task_dir.is_dir() and any(task_dir.iterdir())
    try:
        data = json.loads(mr.read_text(encoding="utf-8"))
    except Exception:
        return True
    if data.get("termination_reason") == "infrastructure_error":
        return True
    if data.get("error_category") in {"infrastructure", "infrastructure_error"}:
        return True
    for r in (1, 2, 3, 4, 5, 6):
        g = task_dir / f"workspace/round_{r}/gate_result.json"
        if not g.is_file():
            continue
        try:
            gg = json.loads(g.read_text(encoding="utf-8"))
        except Exception:
            return True
        if gg.get("termination_reason") == "infrastructure_error":
            return True
        err = str(gg.get("error") or "").lower()
        if any(
            s in err
            for s in (
                "openhands install failed",
                "session_new timed out",
                "huggingface",
                "could not connect",
                "docker compose command failed",
                "infrastructure",
            )
        ):
            return True
    return False


def archive_and_requeue_infra(run_id: str) -> list[str]:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    so.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive = so / f"_archived_infra_{stamp}"
    archive.mkdir(parents=True, exist_ok=True)
    targets: list[str] = []
    for task in load_tasks():
        d = so / task
        if not d.exists():
            continue
        if is_infra_contaminated(d):
            targets.append(task)
    if not targets:
        log(f"{run_id}: no infra-contaminated tasks")
        return []
    for task in targets:
        src = so / task
        dest = archive / task
        if dest.exists():
            dest = archive / f"{task}__again"
        shutil.move(str(src), str(dest))
    # rebuild queue/done
    qdir = ROOT / "experiments" / run_id / "queue"
    qdir.mkdir(parents=True, exist_ok=True)
    done = [
        t
        for t in load_tasks()
        if (so / t / "method_result.json").is_file()
    ]
    pending = [t for t in load_tasks() if t not in done]
    # put infra retries first
    ordered = [t for t in targets if t in pending] + [t for t in pending if t not in targets]
    (qdir / "skillopt.done").write_text("\n".join(done) + ("\n" if done else ""), encoding="utf-8")
    (qdir / "skillopt.txt").write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    (qdir / "skillopt.failures").write_text("", encoding="utf-8")
    log(f"{run_id}: archived infra tasks x{len(targets)} -> {archive.name}; requeue={len(ordered)}")
    return targets


def refresh_liveboard() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_liveboard.py"), "--suite", str(SUITE_PATH)],
        cwd=str(ROOT),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def clear_partials(run_id: str) -> None:
    """Remove incomplete method dirs (no method_result) so phase can restart cleanly."""
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    if not so.is_dir():
        return
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive = so / f"_archived_partial_{stamp}"
    moved = 0
    for d in list(so.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if not (d / "method_result.json").is_file():
            archive.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(archive / d.name))
            moved += 1
    if moved:
        log(f"{run_id}: archived {moved} partial dirs")


def run_arm(arm: dict[str, Any], workers: int, max_infra_sweeps: int) -> None:
    run_id = arm["run_id"]
    n, L, R = int(arm["n"]), int(arm["L"]), int(arm["R"])
    label = arm["label"]
    log(f"===== ARM {label} start run={run_id} n={n} L={L} R={R} =====")
    ensure_docker()

    # If nothing running and work remains, launch.
    for sweep in range(max_infra_sweeps + 1):
        ensure_docker()
        done = method_done_count(run_id)
        rem = queue_remaining(run_id)
        procs = pgrep_run(run_id)
        tasks_n = len(load_tasks())
        log(f"{label} sweep={sweep}: done={done}/{tasks_n} queue={rem} procs={len(procs)}")

        if done >= tasks_n and rem == 0 and not procs:
            # full results present — check infra
            infra = archive_and_requeue_infra(run_id)
            refresh_liveboard()
            if not infra:
                log(f"{label} clean complete")
                return
            # need another launch for infra retries
            rem = queue_remaining(run_id)

        if not procs and (rem > 0 or done < tasks_n):
            # rebuild queue for missing results
            if rem == 0 and done < tasks_n:
                clear_partials(run_id)
                qdir = ROOT / "experiments" / run_id / "queue"
                qdir.mkdir(parents=True, exist_ok=True)
                so = ROOT / "experiments" / run_id / "methods" / "skillopt"
                missing = [
                    t
                    for t in load_tasks()
                    if not (so / t / "method_result.json").is_file()
                ]
                done_list = [t for t in load_tasks() if t not in missing]
                (qdir / "skillopt.txt").write_text(
                    "\n".join(missing) + ("\n" if missing else ""), encoding="utf-8"
                )
                (qdir / "skillopt.done").write_text(
                    "\n".join(done_list) + ("\n" if done_list else ""), encoding="utf-8"
                )
                log(f"{label}: rebuilt queue missing={len(missing)}")
            proc = launch_parallel(run_id, n, L, R, workers)
            # wait until phase process exits OR idle
            while True:
                refresh_liveboard()
                if proc.poll() is not None:
                    log(f"{label}: parallel_phase exited rc={proc.returncode}")
                    break
                if not pgrep_run(run_id) and queue_remaining(run_id) == 0:
                    # children gone, parent maybe zombie — wait a bit
                    time.sleep(10)
                    if proc.poll() is not None:
                        break
                time.sleep(60)
            wait_arm_idle(run_id)
        else:
            # already running — wait
            wait_arm_idle(run_id)

        infra = archive_and_requeue_infra(run_id)
        refresh_liveboard()
        if not infra:
            log(f"{label} complete with no infra left")
            return
        log(f"{label}: infra retry needed x{len(infra)}")

    log(f"{label}: reached max_infra_sweeps={max_infra_sweeps}; stopping arm")


def start_liveboard_refresher(refresh_sec: int) -> threading.Thread:
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(refresh_sec):
            try:
                refresh_liveboard()
                log(f"liveboard refreshed (every {refresh_sec}s)")
            except Exception as exc:  # noqa: BLE001
                log(f"liveboard refresh error: {exc!r}")

    t = threading.Thread(target=loop, name="liveboard-refresh", daemon=True)
    t.stop_event = stop  # type: ignore[attr-defined]
    t.start()
    return t


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--max-infra-sweeps", type=int, default=3)
    parser.add_argument("--kill-other-arms-first", action="store_true")
    parser.add_argument("--refresh-sec", type=int, default=180)
    args = parser.parse_args()

    suite = load_suite()
    arms = suite["arms"]
    log(f"supervisor start suite={suite.get('suite_id')} arms={[a['label'] for a in arms]}")

    refresher = start_liveboard_refresher(args.refresh_sec)
    refresh_liveboard()

    if args.kill_other_arms_first and len(arms) >= 1:
        # Keep first arm (n3) running; kill the rest so they don't contend.
        for arm in arms[1:]:
            kill_run(arm["run_id"])
            clear_partials(arm["run_id"])
            # reset their queues to full pending of missing results
            qdir = ROOT / "experiments" / arm["run_id"] / "queue"
            qdir.mkdir(parents=True, exist_ok=True)
            so = ROOT / "experiments" / arm["run_id"] / "methods" / "skillopt"
            missing = [
                t
                for t in load_tasks()
                if not (so / t / "method_result.json").is_file()
            ]
            (qdir / "skillopt.txt").write_text(
                "\n".join(missing) + ("\n" if missing else ""), encoding="utf-8"
            )
            (qdir / "skillopt.done").write_text("", encoding="utf-8")
            (qdir / "skillopt.failures").write_text("", encoding="utf-8")
            log(f"reset queue for {arm['label']}: {len(missing)} tasks")

    for arm in arms:
        try:
            run_arm(arm, workers=args.workers, max_infra_sweeps=args.max_infra_sweeps)
        except Exception as exc:  # noqa: BLE001
            log(f"ARM ERROR {arm.get('label')}: {exc!r}")
            refresh_liveboard()
            # continue to next arm rather than dying entirely
            continue

    refresh_liveboard()
    log("supervisor: all arms finished")
    stop = getattr(refresher, "stop_event", None)
    if stop is not None:
        stop.set()
    return 0


if __name__ == "__main__":
    # Ignore SIGHUP so lunch/disconnect is safer when launched under nohup/background.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    raise SystemExit(main())
