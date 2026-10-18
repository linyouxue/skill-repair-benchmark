#!/usr/bin/env python3
"""Drive a single SkillOpt arm to completion with relaunch + liveboard refresh."""
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
LOG = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite" / "n3r5_rerun.log"

RUN_ID = "core25-gpt52-skillopt-n3L4R5-20260920T093750Z"
N, L, R = 3, 4, 5
WORKERS = 5


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


def pending() -> list[str]:
    so = ROOT / "experiments" / RUN_ID / "methods" / "skillopt"
    return [t for t in load_tasks() if not (so / t / "method_result.json").is_file()]


def done() -> list[str]:
    so = ROOT / "experiments" / RUN_ID / "methods" / "skillopt"
    return [t for t in load_tasks() if (so / t / "method_result.json").is_file()]


def write_queue() -> list[str]:
    pend = pending()
    d = done()
    q = ROOT / "experiments" / RUN_ID / "queue"
    q.mkdir(parents=True, exist_ok=True)
    (q / "skillopt.txt").write_text("\n".join(pend) + ("\n" if pend else ""), encoding="utf-8")
    (q / "skillopt.done").write_text("\n".join(d) + ("\n" if d else ""), encoding="utf-8")
    (q / "skillopt.failures").write_text("", encoding="utf-8")
    return pend


def pgrep() -> list[str]:
    out = subprocess.check_output(["ps", "aux"], text=True)
    return [
        ln
        for ln in out.splitlines()
        if f"--run-id {RUN_ID}" in ln
        and ("run_method.py" in ln or "parallel_phase.py" in ln)
    ]


def kill_run() -> None:
    for pattern in (
        f"run_method.py --run-id {RUN_ID}",
        f"parallel_phase.py --run-id {RUN_ID}",
    ):
        subprocess.run(["pkill", "-f", pattern], check=False)
    time.sleep(2)
    if pgrep():
        subprocess.run(["pkill", "-9", "-f", f"--run-id {RUN_ID}"], check=False)
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


def arm_env() -> dict[str, str]:
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
    env["SKILLOPT_EVA_DIAGNOSIS_N"] = str(N)
    env["SKILLOPT_EVA_EDIT_BUDGET_L"] = str(L)
    env["SKILLOPT_EVA_REPAIR_ROUNDS_R"] = str(R)
    env.pop("SKILLOPT_EVA_SMOKE", None)
    env.pop("DEBUG", None)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def refresh() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_liveboard.py"), "--suite", str(SUITE)],
        cwd=str(ROOT),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch() -> subprocess.Popen:
    ensure_docker()
    env = arm_env()
    log_path = ROOT / "experiments" / RUN_ID / "logs" / "rerun_phase.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    fh.write(f"\n===== {datetime.now().isoformat()} workers={WORKERS} =====\n")
    fh.flush()
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "parallel_phase.py"),
        "--run-id",
        RUN_ID,
        "--phase",
        "skillopt",
        "--workers",
        str(WORKERS),
    ]
    log(f"launch {RUN_ID} n={N} L={L} R={R} workers={WORKERS}")
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT)


def main() -> int:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def loop() -> None:
        while True:
            time.sleep(180)
            try:
                refresh()
                log("liveboard refreshed")
            except Exception as exc:  # noqa: BLE001
                log(f"refresh error: {exc!r}")

    threading.Thread(target=loop, daemon=True).start()
    log(f"n3L4R5 rerun start run={RUN_ID}")
    refresh()
    for attempt in range(1, 12):
        pend = write_queue()
        if not pend:
            log("complete: 25/25 results present")
            refresh()
            return 0
        kill_run()
        proc = launch()
        ticks = 0
        while proc.poll() is None:
            ticks += 1
            if ticks % 2 == 0:
                log(f"wait procs={len(pgrep())} pending={len(pending())} attempt={attempt}")
            time.sleep(30)
        log(f"phase exited rc={proc.returncode} attempt={attempt}")
        time.sleep(5)
        if not pending():
            log("complete after phase exit")
            refresh()
            return 0
        if not pgrep() and pending():
            log(f"workers dead; will relaunch pending={pending()}")
    log(f"stopped with leftovers={pending()}")
    refresh()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
