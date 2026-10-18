#!/usr/bin/env python3
"""Parallel Core-25 phase runner with N workers.

Usage:
  python scripts/parallel_phase.py --run-id RUN --phase baseline --workers 5
  python scripts/parallel_phase.py --run-id RUN --phase skillopt --workers 5
  python scripts/parallel_phase.py --run-id RUN --phase skillopt-lite --workers 5
"""
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_FILE = ROOT / "configs" / "core25_tasks.txt"


def load_tasks(tasks_file: Path | None = None) -> list[str]:
    path = tasks_file or DEFAULT_TASKS_FILE
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def result_path(run_id: str, phase: str, task: str) -> Path:
    run = ROOT / "experiments" / run_id
    if phase == "baseline":
        return run / "baseline" / "original-skill" / task / "benchmark_result.json"
    return run / "methods" / phase / task / "method_result.json"


def build_queue(run_id: str, phase: str, tasks_file: Path | None = None) -> Path:
    qdir = ROOT / "experiments" / run_id / "queue"
    qdir.mkdir(parents=True, exist_ok=True)
    queue_file = qdir / f"{phase}.txt"
    done_file = qdir / f"{phase}.done"
    fail_file = qdir / f"{phase}.failures"
    pending: list[str] = []
    done: list[str] = []
    for task in load_tasks(tasks_file):
        if result_path(run_id, phase, task).is_file():
            done.append(task)
        else:
            pending.append(task)
    queue_file.write_text("\n".join(pending) + ("\n" if pending else ""), encoding="utf-8")
    done_file.write_text("\n".join(done) + ("\n" if done else ""), encoding="utf-8")
    if not fail_file.exists():
        fail_file.write_text("", encoding="utf-8")
    print(f"[queue] phase={phase} remaining={len(pending)} done={len(done)}", flush=True)
    return queue_file


def claim(queue_file: Path) -> str | None:
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    if not queue_file.exists():
        queue_file.write_text("", encoding="utf-8")
    with queue_file.open("r+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        lines = [ln.strip() for ln in fh.read().splitlines() if ln.strip()]
        if not lines:
            return None
        task = lines[0]
        rest = "\n".join(lines[1:])
        fh.seek(0)
        fh.truncate()
        fh.write(rest + ("\n" if rest else ""))
        fh.flush()
        return task


def clean_model_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "TATU_MODEL",
        "BENCHMARK_MODEL",
        "SKILLOPT_MODEL",
        "AI360_MODEL",
        "AI360_API_KEY",
        "AI360_BASE_URL",
        "DEBUG",
    ):
        env.pop(key, None)
    env["PATH"] = "/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    env["UV_CACHE_DIR"] = env.get("UV_CACHE_DIR") or "/private/tmp/skillopt-eva-uv-cache"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_task(run_id: str, phase: str, task: str, worker_id: int) -> int:
    log_dir = ROOT / "experiments" / run_id / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{phase}_{task}.w{worker_id}.log"
    workers_log = log_dir / "workers.log"
    with workers_log.open("a", encoding="utf-8") as wl:
        wl.write(f"[w{worker_id}][{phase}] start {task} {time.strftime('%H:%M:%S')}\n")
    if phase == "baseline":
        cmd = [
            "/opt/homebrew/bin/uv",
            "run",
            "--locked",
            "python",
            str(ROOT / "scripts" / "run_original_baseline.py"),
            "--run-id",
            run_id,
            "--task",
            task,
        ]
    else:
        cmd = [
            "/opt/homebrew/bin/uv",
            "run",
            "--locked",
            "python",
            str(ROOT / "scripts" / "run_method.py"),
            "--run-id",
            run_id,
            "--method",
            phase,
            "--task",
            task,
        ]
    with log_path.open("w", encoding="utf-8") as lf:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT / "skill-repair-benchmark"),
            env=clean_model_env(),
            stdout=lf,
            stderr=subprocess.STDOUT,
            check=False,
        )
    status = proc.returncode
    qdir = ROOT / "experiments" / run_id / "queue"
    with (log_dir / "workers.log").open("a", encoding="utf-8") as wl:
        if status == 0:
            wl.write(f"[w{worker_id}][{phase}] ok {task} {time.strftime('%H:%M:%S')}\n")
            with (qdir / f"{phase}.done").open("a", encoding="utf-8") as df:
                df.write(task + "\n")
        else:
            wl.write(f"[w{worker_id}][{phase}] FAIL {task} status={status} {time.strftime('%H:%M:%S')}\n")
            with (qdir / f"{phase}.failures").open("a", encoding="utf-8") as ff:
                ff.write(f"{task} status={status} log={log_path}\n")
    # refresh liveboard best-effort; never kill the worker if fork/docker is saturated
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "export_liveboard.py"), "--run-id", run_id],
            cwd=str(ROOT),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        with (log_dir / "workers.log").open("a", encoding="utf-8") as wl:
            wl.write(f"[w{worker_id}][{phase}] liveboard_skip {task} {exc!r}\n")
    return status


def worker_main(run_id: str, phase: str, worker_id: int, queue_file: Path) -> None:
    while True:
        task = claim(queue_file)
        if not task:
            break
        run_task(run_id, phase, task, worker_id)
    log_dir = ROOT / "experiments" / run_id / "logs"
    with (log_dir / "workers.log").open("a", encoding="utf-8") as wl:
        wl.write(f"[w{worker_id}][{phase}] idle {time.strftime('%H:%M:%S')}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", required=True, choices=["baseline", "skillopt", "skillopt-lite"])
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument(
        "--tasks-file",
        type=Path,
        default=DEFAULT_TASKS_FILE,
        help="Task id list; defaults to Core-25",
    )
    args = parser.parse_args()

    queue_file = build_queue(args.run_id, args.phase, args.tasks_file)
    procs: list[subprocess.Popen] = []
    for wid in range(1, args.workers + 1):
        # spawn worker as separate python process for true parallelism
        p = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--run-id",
                args.run_id,
                "--phase",
                args.phase,
                "--workers",
                "0",
                "--tasks-file",
                str(args.tasks_file),
                f"--_worker-id={wid}",
                f"--_queue-file={queue_file}",
            ],
            cwd=str(ROOT),
            env=clean_model_env(),
        )
        procs.append(p)
        print(f"[spawn] worker={wid} pid={p.pid}", flush=True)

    rc = 0
    for p in procs:
        p.wait()
        if p.returncode:
            rc = p.returncode
    print(f"[phase] {args.phase} complete", flush=True)
    return rc


def worker_entry() -> int:
    # Internal worker mode via private flags.
    argv = sys.argv[1:]
    run_id = None
    phase = None
    worker_id = None
    queue_file = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--run-id":
            run_id = argv[i + 1]
            i += 2
        elif a == "--phase":
            phase = argv[i + 1]
            i += 2
        elif a.startswith("--_worker-id="):
            worker_id = int(a.split("=", 1)[1])
            i += 1
        elif a.startswith("--_queue-file="):
            queue_file = Path(a.split("=", 1)[1])
            i += 1
        else:
            i += 1
    assert run_id and phase and worker_id and queue_file
    worker_main(run_id, phase, worker_id, queue_file)
    return 0


if __name__ == "__main__":
    if any(a.startswith("--_worker-id=") for a in sys.argv):
        raise SystemExit(worker_entry())
    raise SystemExit(main())
