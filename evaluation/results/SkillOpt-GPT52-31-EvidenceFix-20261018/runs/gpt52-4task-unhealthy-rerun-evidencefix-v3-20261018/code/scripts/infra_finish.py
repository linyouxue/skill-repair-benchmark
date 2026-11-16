#!/usr/bin/env python3
"""Finish remaining infra/missing SkillOpt tasks without fighting other jobs.

Runs n3L4R5 pending first (16), then n5L4R2 pending (if any).
No infra archive sweeps — just drive queue to empty with worker relaunch.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "configs" / "gpt52_hyperparam_suite.json"
LOG = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite" / "infra_finish.log"

ARMS = [
    {
        "label": "n3L4R5",
        "run_id": "core25-gpt52-skillopt-n3L4R5-20260919",
        "n": 3,
        "L": 4,
        "R": 5,
    },
    {
        "label": "n5L4R2",
        "run_id": "core25-gpt52-skillopt-n5L4R2-20260919",
        "n": 5,
        "L": 4,
        "R": 2,
    },
]


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_tasks() -> list[str]:
    return [
        ln.strip()
        for ln in (ROOT / "configs" / "core25_tasks.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def pending_for(run_id: str) -> list[str]:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    return [t for t in load_tasks() if not (so / t / "method_result.json").is_file()]


def done_for(run_id: str) -> list[str]:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    return [t for t in load_tasks() if (so / t / "method_result.json").is_file()]


def write_queue(run_id: str) -> list[str]:
    pending = pending_for(run_id)
    done = done_for(run_id)
    q = ROOT / "experiments" / run_id / "queue"
    q.mkdir(parents=True, exist_ok=True)
    (q / "skillopt.txt").write_text("\n".join(pending) + ("\n" if pending else ""), encoding="utf-8")
    (q / "skillopt.done").write_text("\n".join(done) + ("\n" if done else ""), encoding="utf-8")
    (q / "skillopt.failures").write_text("", encoding="utf-8")
    return pending


def pgrep_run(run_id: str) -> list[str]:
    out = subprocess.check_output(["ps", "aux"], text=True)
    hits = []
    for line in out.splitlines():
        if f"--run-id {run_id}" in line and (
            "run_method.py" in line or "parallel_phase.py" in line
        ):
            hits.append(line)
    return hits


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


def docker_ok() -> bool:
    return (
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def ensure_docker() -> None:
    if docker_ok():
        return
    log("Docker down; opening Docker Desktop")
    subprocess.run(["open", "-a", "Docker"], check=False)
    for _ in range(60):
        if docker_ok():
            log("Docker up")
            return
        time.sleep(3)
    log("WARNING: Docker still down")


def arm_env(n: int, L: int, R: int) -> dict[str, str]:
    env = os.environ.copy()
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


def refresh_liveboard() -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "export_liveboard.py"),
            "--suite",
            str(SUITE),
        ],
        cwd=str(ROOT),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch(run_id: str, n: int, L: int, R: int, workers: int) -> subprocess.Popen:
    ensure_docker()
    env = arm_env(n, L, R)
    log_path = ROOT / "experiments" / run_id / "logs" / "infra_finish_phase.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    fh.write(f"\n===== {datetime.now().isoformat()} workers={workers} =====\n")
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


def run_arm(arm: dict, workers: int = 5, max_relaunches: int = 8) -> None:
    run_id = arm["run_id"]
    label = arm["label"]
    pending = write_queue(run_id)
    log(f"===== {label} pending={len(pending)} =====")
    if not pending:
        log(f"{label}: nothing pending")
        return
    kill_run(run_id)
    for attempt in range(1, max_relaunches + 1):
        pending = write_queue(run_id)
        if not pending:
            log(f"{label}: cleared")
            return
        proc = launch(run_id, arm["n"], arm["L"], arm["R"], workers)
        ticks = 0
        while proc.poll() is None:
            ticks += 1
            if ticks % 3 == 0:
                refresh_liveboard()
            rem = len(pending_for(run_id))
            procs = len(pgrep_run(run_id))
            if ticks % 2 == 0:
                log(f"wait {label}: procs={procs} pending={rem} attempt={attempt}")
            time.sleep(30)
        log(f"{label}: phase exited rc={proc.returncode} attempt={attempt}")
        time.sleep(5)
        pending = pending_for(run_id)
        if not pending and not pgrep_run(run_id):
            log(f"{label}: cleared")
            refresh_liveboard()
            return
        if not pgrep_run(run_id) and pending:
            log(f"{label}: workers dead; relaunch pending={pending}")
    log(f"{label}: stopped with leftovers={pending_for(run_id)}")


def main() -> int:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def refresher() -> None:
        while True:
            time.sleep(180)
            try:
                refresh_liveboard()
                log("liveboard refreshed (every 180s)")
            except Exception as exc:  # noqa: BLE001
                log(f"refresh error: {exc!r}")

    threading.Thread(target=refresher, daemon=True).start()
    log("infra_finish start")
    refresh_liveboard()
    for arm in ARMS:
        try:
            run_arm(arm)
        except Exception as exc:  # noqa: BLE001
            log(f"ARM ERROR {arm['label']}: {exc!r}")
    refresh_liveboard()
    log("infra_finish done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
