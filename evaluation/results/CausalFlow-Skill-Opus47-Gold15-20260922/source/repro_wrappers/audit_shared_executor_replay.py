#!/usr/bin/env python3
"""Reconstruct a shared-executor rollout twice and check official equivalence.

The public executor does not export the submitted workspace or CausalFlow's
resource markers.  This audit therefore cannot claim byte identity with the
original rollout.  It recovers exact tool arguments from the LLM trajectory,
replays them twice in the same task image, and requires both fresh runs to
match the saved official reward/tests and each other's semantic manifest.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repro_wrappers.run_skillsbench_causalflow_repair import (  # noqa: E402
    _ctrf_counts,
    _recorded_return_codes,
    _run_branch,
)
from repro_wrappers.skillsbench_deployed_skills import (  # noqa: E402
    resolve_deployed_skills,
)
from skillsbench_replay.atif import load_run, materialize_replay_command  # noqa: E402
from skillsbench_replay.graph import infer_task_workspace  # noqa: E402


def _known_return_codes_match(parsed, replay: dict[str, Any]) -> bool:
    # The shell replay excludes task_tracker and other non-execute tools. Their
    # title fallbacks may be non-empty strings, but are not shell commands and
    # must not shift the expected exit-code sequence.
    execution_run = copy.copy(parsed)
    execution_run.events = [event for event in parsed.events
                            if event.kind == "execute" and event.command]
    expected = _recorded_return_codes(execution_run)
    actual = [
        item.get("return_code") for item in replay.get("command_executions") or []
    ]
    return len(expected) == len(actual) and all(
        code is None or code == actual[index]
        for index, code in enumerate(expected)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="exact deployed Skill bundle; defaults to run-dir/inputs/skills",
    )
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 2:
        raise SystemExit("--repeats must be at least 2")

    run_dir = args.run_dir.resolve()
    task_dir = args.task_dir.resolve()
    skills_root, skills_source = resolve_deployed_skills(
        run_dir, task_dir, args.skills_dir
    )
    parsed = load_run(run_dir)
    command_events = [
        event
        for event in parsed.events
        if event.kind == "execute" and event.command is not None
    ]
    omitted = [
        event.step_id
        for event in parsed.events
        if event.kind == "execute" and event.command is None
    ]
    exact_sources = {
        "result_marker",
        "llm_trajectory.arguments.command",
        "llm_trajectory.file_editor.create",
        "llm_trajectory.file_editor.str_replace",
    }
    non_exact = [
        event.step_id
        for event in command_events
        if event.argument_source not in exact_sources
    ]
    if omitted or non_exact or not command_events:
        raise SystemExit(
            "shared-executor replay requires every executable state-changing "
            f"tool call to have exact arguments; omitted={omitted} non_exact={non_exact}"
        )

    commands = [materialize_replay_command(event) for event in command_events]
    workspace = infer_task_workspace(task_dir)
    fresh_runs = [
        _run_branch(
            image=args.image,
            task_dir=task_dir,
            skills_root=skills_root,
            workspace=workspace,
            commands=commands,
            timeout=args.timeout,
            command_timeouts=[event.replay_timeout or min(args.timeout, 120)
                              for event in command_events],
        )
        for _ in range(args.repeats)
    ]
    saved_ctrf = _ctrf_counts(run_dir)
    per_run_checks = [
        {
            "reward_matches": run.get("reward") == parsed.reward,
            "ctrf_matches": saved_ctrf is None or run.get("ctrf") == saved_ctrf,
            "known_return_codes_match": _known_return_codes_match(parsed, run),
            "command_count_matches": len(run.get("command_executions") or [])
            == len(commands),
            "sandbox_identity_matches": (
                isinstance(run.get("execution_identity"), dict)
                and run["execution_identity"].get("agent_user") == "agent"
                and run["execution_identity"].get("verifier_user") == "root"
            ),
        }
        for run in fresh_runs
    ]
    manifests = [run.get("workspace_manifest") or {} for run in fresh_runs]
    fresh_manifests_match = all(manifest == manifests[0] for manifest in manifests[1:])
    official_equivalent = all(
        all(checks.values()) for checks in per_run_checks
    ) and fresh_manifests_match

    payload = {
        "experiment": "shared executor trajectory replay audit",
        "task": task_dir.name,
        "run_dir": str(run_dir),
        "input_provenance": (json.loads((run_dir / 'input-provenance.json').read_text())
                             if (run_dir / 'input-provenance.json').is_file()
                             else {'kind': 'original_logged_trajectory'}),
        "deployed_skills_dir": str(skills_root),
        "deployed_skills_source": skills_source,
        "image": args.image,
        "saved_reward": parsed.reward,
        "saved_ctrf": saved_ctrf,
        "command_count": len(commands),
        "terminal_wait_events": [event.to_dict() for event in parsed.events
                                 if event.kind == "terminal_wait"],
        "argument_sources": sorted(
            {event.argument_source for event in command_events}
        ),
        "fresh_runs": fresh_runs,
        "per_run_checks": per_run_checks,
        "fresh_manifests_match": fresh_manifests_match,
        "official_equivalent_replay": official_equivalent,
        "evidence_tier": (
            "official_equivalent_double_replay"
            if official_equivalent
            else "failed_replay_audit"
        ),
        "limitation": (
            "the public executor did not export the original submitted workspace "
            "or CausalFlow resource hashes, so this is not byte identity with the "
            "original rollout"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "task": task_dir.name,
        "official_equivalent_replay": official_equivalent,
        "saved_reward": parsed.reward,
        "fresh_rewards": [run.get("reward") for run in fresh_runs],
        "command_count": len(commands),
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if official_equivalent else 2


if __name__ == "__main__":
    raise SystemExit(main())
