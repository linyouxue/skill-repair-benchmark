"""Replay recorded shell calls inside a SkillsBench task container.

The original ACP agent executes every tool call in a fresh ``bash -lc``
process.  Replaying all commands as one concatenated shell script is not
equivalent: environment changes leak between calls, ``exit`` affects later
calls, and a truncated heredoc can swallow the next command.  This standalone
driver preserves the original process boundary and records return codes plus a
content-addressed final workspace manifest for fidelity checks.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from openrouter_acp_agent import (
    PYTHON_AUDIT_DIR,
    PYTHON_AUDIT_SOURCE,
    workspace_manifest as agent_workspace_manifest,
)


MAX_CAPTURE_CHARS = 12_000


def workspace_manifest(root: Path) -> dict[str, str]:
    return agent_workspace_manifest(str(root))


def _run_command(
    command: str,
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> tuple[int | None, str, str, bool]:
    # ``pkill -f`` searches the full process command line.  Passing the replayed
    # command itself as ``bash -lc <command>`` makes the replay shell match its
    # own pattern, although the original ACP terminal receives the command over
    # its terminal channel and therefore does not expose it in argv.  Feed only
    # those process-matching commands over stdin so the replay preserves the
    # original process-discovery semantics without changing ordinary commands.
    stdin_command = "pkill -f" in command
    process = subprocess.Popen(
        ["/bin/bash", "-l"] if stdin_command else ["/bin/bash", "-lc", command],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.PIPE if stdin_command else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(
            command + "\n" if stdin_command else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        trailing_stdout, trailing_stderr = process.communicate()
        stdout = trailing_stdout or ""
        stderr = trailing_stderr or ""
        return None, stdout, stderr, True
    return process.returncode, stdout, stderr, False


def _drop_privileges(uid: int, gid: int, home: str) -> None:
    """Match BenchFlow's non-root ``agent`` execution boundary.

    The replay driver is started by a root-owned orchestration shell so the
    same container can later run the official verifier as root.  Privilege is
    dropped only in this child process; every recorded shell call therefore
    runs with the same uid/gid and HOME as the original ACP agent.
    """

    os.environ.update(
        {
            "HOME": home,
            "USER": "agent",
            "LOGNAME": "agent",
        }
    )
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commands", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, default=120)
    parser.add_argument("--command-timeouts", type=Path)
    parser.add_argument("--run-uid", type=int)
    parser.add_argument("--run-gid", type=int)
    parser.add_argument("--run-home", default="/home/agent")
    args = parser.parse_args()

    if (args.run_uid is None) != (args.run_gid is None):
        raise SystemExit("--run-uid and --run-gid must be supplied together")

    commands = json.loads(args.commands.read_text())
    if not isinstance(commands, list) or not all(
        isinstance(command, str) for command in commands
    ):
        raise SystemExit("commands file must contain a JSON string array")
    timeouts = (json.loads(args.command_timeouts.read_text())
                if args.command_timeouts else [args.command_timeout] * len(commands))
    if (not isinstance(timeouts, list) or len(timeouts) != len(commands)
            or not all(isinstance(value, (int, float)) and 0 < value < float("inf")
                       for value in timeouts)):
        raise SystemExit("command timeouts must be positive numbers, one per command")

    if args.run_uid is not None and args.run_gid is not None:
        _drop_privileges(args.run_uid, args.run_gid, args.run_home)

    executions: list[dict[str, Any]] = []
    os.makedirs(PYTHON_AUDIT_DIR, exist_ok=True)
    Path(PYTHON_AUDIT_DIR, "sitecustomize.py").write_text(PYTHON_AUDIT_SOURCE)
    for index, command in enumerate(commands):
        started = time.perf_counter()
        audit_log = Path(PYTHON_AUDIT_DIR, f"replay-{uuid.uuid4().hex}.jsonl")
        command_env = os.environ.copy()
        existing_pythonpath = command_env.get("PYTHONPATH", "")
        command_env["PYTHONPATH"] = (
            PYTHON_AUDIT_DIR
            if not existing_pythonpath
            else f"{PYTHON_AUDIT_DIR}{os.pathsep}{existing_pythonpath}"
        )
        command_env["CAUSALFLOW_AUDIT_ROOT"] = str(args.workspace.resolve())
        command_env["CAUSALFLOW_AUDIT_LOG"] = str(audit_log)
        return_code, stdout, stderr, timed_out = _run_command(
            command,
            cwd=args.workspace,
            env=command_env,
            timeout=timeouts[index],
        )
        if timed_out:
            record = {
                "index": index,
                "return_code": None,
                "timed_out": True,
                "seconds": time.perf_counter() - started,
                "stdout_tail": stdout[-MAX_CAPTURE_CHARS:],
                "stderr_tail": stderr[-MAX_CAPTURE_CHARS:],
            }
        else:
            record = {
                "index": index,
                "return_code": return_code,
                "timed_out": False,
                "seconds": time.perf_counter() - started,
                "stdout_tail": stdout[-MAX_CAPTURE_CHARS:],
                "stderr_tail": stderr[-MAX_CAPTURE_CHARS:],
            }
        executions.append(record)
        try:
            audit_log.unlink()
        except OSError:
            pass
        print(
            f"replay_command={index} return_code={record['return_code']} "
            f"timed_out={record['timed_out']}",
            flush=True,
        )

    args.result.write_text(json.dumps(executions, ensure_ascii=False, indent=2))
    args.manifest.write_text(
        json.dumps(workspace_manifest(args.workspace), sort_keys=True, indent=2)
    )
    # Individual command failures are part of the recorded trajectory, not a
    # reason to suppress the official verifier.  The host compares the full
    # return-code vector after verification.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
