#!/usr/bin/env python3
"""Continue unfinished SkillOpt tasks only (skip existing infra results for later).

Order: n3L4R5 remaining → n5L4R2 remaining.
Does NOT archive/requeue infrastructure failures.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "configs" / "gpt52_hyperparam_suite.json"
LOG_DIR = ROOT / "experiments" / "liveboards" / "gpt52-hyperparam-suite"
LOG_PATH = LOG_DIR / "continue_non_infra.log"


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
    log("Docker down; starting Docker Desktop…")
    subprocess.run(["open", "-a", "Docker"], check=False)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if docker_ok():
            log("Docker is up")
            return
        time.sleep(3)
    log("WARNING: Docker still down after wait")


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


def unfinished_tasks(run_id: str) -> tuple[list[str], list[str]]:
    """Return (pending_without_result, done_with_result). Infra results count as done for now."""
    tasks = load_tasks()
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    pending: list[str] = []
    done: list[str] = []
    for t in tasks:
        if (so / t / "method_result.json").is_file():
            done.append(t)
        else:
            pending.append(t)
    return pending, done


def clear_partials(run_id: str, pending: list[str]) -> None:
    so = ROOT / "experiments" / run_id / "methods" / "skillopt"
    if not so.is_dir():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = so / f"_archived_partial_{stamp}"
    moved = 0
    for t in pending:
        d = so / t
        if d.is_dir() and not (d / "method_result.json").is_file():
            archive.mkdir(parents=True, exist_ok=True)
            dest = archive / t
            if dest.exists():
                dest = archive / f"{t}__again"
            shutil.move(str(d), str(dest))
            moved += 1
    if moved:
        log(f"{run_id}: archived {moved} partial dirs")


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


def launch_parallel(run_id: str, n: int, L: int, R: int, workers: int) -> subprocess.Popen:
    ensure_docker()
    env = arm_env(n, L, R)
    log_path = ROOT / "experiments" / run_id / "logs" / "continue_phase.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    fh.write(
        f"\n===== continue launch {datetime.now().isoformat()} n={n} L={L} R={R} workers={workers} =====\n"
    )
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


def refresh_liveboard() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_liveboard.py"), "--suite", str(SUITE_PATH)],
        cwd=str(ROOT),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_idle(run_id: str, poll_sec: int = 30) -> None:
    tasks_n = len(load_tasks())
    ticks = 0
    stable = 0
    while True:
        procs = pgrep_run(run_id)
        pending, done = unfinished_tasks(run_id)
        q = ROOT / "experiments" / run_id / "queue" / "skillopt.txt"
        rem = (
            sum(1 for ln in q.read_text(encoding="utf-8").splitlines() if ln.strip())
            if q.is_file()
            else 0
        )
        log(f"wait {run_id}: procs={len(procs)} queue={rem} done={len(done)}/{tasks_n} pending_no_result={len(pending)}")
        ticks += 1
        if ticks % 6 == 0:
            refresh_liveboard()
        if not procs and (rem == 0 or not pending):
            stable += 1
            if stable >= 2:
                return
        else:
            stable = 0
        if not procs and rem > 0 and pending:
            log(f"wait {run_id}: workers dead with remaining work; returning for relaunch")
            return
        time.sleep(poll_sec)


def run_arm_unfinished(arm: dict[str, Any], workers: int) -> None:
    run_id = arm["run_id"]
    label = arm["label"]
    n, L, R = int(arm["n"]), int(arm["L"]), int(arm["R"])
    pending, done = unfinished_tasks(run_id)
    log(f"===== CONTINUE {label} pending_no_result={len(pending)} keep_results={len(done)} =====")
    if not pending:
        log(f"{label}: nothing unfinished (infra kept for later)")
        return

    kill_run(run_id)
    clear_partials(run_id, pending)
    pending, done = unfinished_tasks(run_id)
    write_queue(run_id, pending, done)
    if not pending:
        return

    # relaunch until pending empty (worker death recovery), but never touch infra results
    for attempt in range(1, 6):
        pending, done = unfinished_tasks(run_id)
        if not pending:
            log(f"{label}: unfinished cleared")
            return
        write_queue(run_id, pending, done)
        ensure_docker()
        proc = launch_parallel(run_id, n, L, R, workers)
        while proc.poll() is None:
            refresh_liveboard()
            time.sleep(60)
        log(f"{label}: parallel_phase exited rc={proc.returncode} attempt={attempt}")
        wait_idle(run_id)
        pending, done = unfinished_tasks(run_id)
        if not pending:
            log(f"{label}: unfinished cleared")
            refresh_liveboard()
            return
        log(f"{label}: still pending={pending}; retry launch")
    log(f"{label}: stopped with pending left={unfinished_tasks(run_id)[0]}")


def start_refresher(refresh_sec: int) -> None:
    def loop() -> None:
        while True:
            time.sleep(refresh_sec)
            try:
                refresh_liveboard()
                log(f"liveboard refreshed (every {refresh_sec}s)")
            except Exception as exc:  # noqa: BLE001
                log(f"liveboard refresh error: {exc!r}")

    threading.Thread(target=loop, name="liveboard-refresh", daemon=True).start()


def main() -> int:
    workers = 5
    suite = load_suite()
    # Unfinished = no method_result yet. Keep existing infra results untouched for later batch retry.
    # Finish current arm n3L4R5 first, then n5L4R2 leftovers.
    by_label = {a["label"]: a for a in suite["arms"]}
    order = [by_label["n3L4R5"], by_label["n5L4R2"]]
    log(f"continue-non-infra start workers={workers} order={[a['label'] for a in order]}")
    start_refresher(180)
    refresh_liveboard()
    for arm in order:
        try:
            run_arm_unfinished(arm, workers=workers)
        except Exception as exc:  # noqa: BLE001
            log(f"ARM ERROR {arm.get('label')}: {exc!r}")
            refresh_liveboard()
    refresh_liveboard()
    log("continue-non-infra: finished")
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    raise SystemExit(main())
