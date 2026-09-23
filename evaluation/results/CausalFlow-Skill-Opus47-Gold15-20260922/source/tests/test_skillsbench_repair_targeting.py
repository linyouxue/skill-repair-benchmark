from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from repro_wrappers.run_skillsbench_causalflow_repair import (
    _build_image,
    _replay_fidelity_report,
    _target_event,
    _task_resource_limits,
)
from repro_wrappers.run_skillsbench_full_causalflow import (
    _counterfactual_outcome_succeeds,
    _counterfactual_replay_steps,
    _execution_coverage,
    _final_state_support_steps,
    _use_existing_image,
)
from repro_wrappers.run_skillsbench_causalflow_repair import _run_branch


def event(step_id, command, reads=(), writes=(), deletes=()):
    return SimpleNamespace(
        step_id=step_id,
        command=command,
        observed_reads=tuple(reads),
        inferred_reads=(),
        observed_writes=tuple(writes),
        inferred_writes=(),
        inferred_deletes=tuple(deletes),
    )


class SkillsBenchRepairTargetingTests(unittest.TestCase):
    def test_default_causal_gate_requires_full_success(self):
        self.assertFalse(
            _counterfactual_outcome_succeeds(
                0.8, baseline_reward=0.5, outcome_mode="full-success"
            )
        )
        self.assertTrue(
            _counterfactual_outcome_succeeds(
                1.0, baseline_reward=0.5, outcome_mode="full-success"
            )
        )

    def test_reward_improvement_gate_accepts_partial_gain_only(self):
        self.assertTrue(
            _counterfactual_outcome_succeeds(
                0.8, baseline_reward=0.5, outcome_mode="reward-improvement"
            )
        )
        self.assertFalse(
            _counterfactual_outcome_succeeds(
                0.5, baseline_reward=0.5, outcome_mode="reward-improvement"
            )
        )

    def test_branch_uses_fresh_writable_verifier_copy(self):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as raw_root:
            task_dir = Path(raw_root) / "task"
            verifier = task_dir / "verifier"
            skills = task_dir / "skills"
            verifier.mkdir(parents=True)
            skills.mkdir()
            build_script = verifier / "build.sh"
            build_script.write_text("#!/bin/bash\nexit 0\n")
            build_script.chmod(0o644)

            with patch(
                "repro_wrappers.run_skillsbench_causalflow_repair._task_resource_limits",
                return_value={"cpus": 1, "memory_mb": 512},
            ), patch(
                "repro_wrappers.run_skillsbench_causalflow_repair.container_proxy_env",
                return_value={},
            ), patch(
                "repro_wrappers.run_skillsbench_causalflow_repair.subprocess.run",
                return_value=completed,
            ) as run:
                _run_branch(
                    image="task:test",
                    task_dir=task_dir,
                    skills_root=skills,
                    workspace="/root",
                    commands=["echo ok"],
                    timeout=3,
                )

            docker_command = run.call_args.args[0]
            container_script = docker_command[-1]
            verifier_mounts = [
                value
                for value in docker_command
                if value.endswith("/task-verifier:/verifier")
            ]
            self.assertEqual(len(verifier_mounts), 1)
            self.assertNotIn(f"{verifier}:/verifier:ro", docker_command)
            self.assertEqual(build_script.stat().st_mode & 0o777, 0o644)
            self.assertIn("useradd -m -s /bin/bash agent", container_script)
            self.assertIn("chown -R agent:agent /root", container_script)
            self.assertIn("chmod 700 /verifier", container_script)
            self.assertIn('--run-uid "$agent_uid"', container_script)
            self.assertIn('--run-gid "$agent_gid"', container_script)
            self.assertIn('"verifier_user":"root"', container_script)

    def test_task_image_build_forwards_proxy_without_recording_value(self):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.container_proxy_env",
            return_value={"HTTPS_PROXY": "http://host.docker.internal:7897"},
        ), patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.subprocess.run",
            return_value=completed,
        ) as run:
            result = _build_image(Path("/tmp/task"), "task:test", 30)

        command = run.call_args.args[0]
        self.assertIn(
            "HTTPS_PROXY=http://host.docker.internal:7897", command
        )
        self.assertIn(
            "https_proxy=http://host.docker.internal:7897", command
        )
        self.assertTrue(result["build_proxy_forwarded"])
        self.assertEqual(result["build_backend"], "buildkit")
        self.assertEqual(run.call_args.kwargs["env"]["DOCKER_BUILDKIT"], "1")
        self.assertNotIn("host.docker.internal", repr(result))

    def test_branch_forwards_both_proxy_variable_casings(self):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch(
            "repro_wrappers.run_skillsbench_causalflow_repair._task_resource_limits",
            return_value={"cpus": 1, "memory_mb": 512},
        ), patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.container_proxy_env",
            return_value={"HTTP_PROXY": "http://host.docker.internal:7897"},
        ), patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.subprocess.run",
            return_value=completed,
        ) as run, patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.shutil.copytree",
        ):
            _run_branch(
                image="task:test",
                task_dir=Path("/tmp/task"),
                skills_root=Path("/tmp/task/skills"),
                workspace="/root",
                commands=["echo ok"],
                timeout=3,
            )

        docker_command = run.call_args.args[0]
        self.assertIn("HTTP_PROXY=http://host.docker.internal:7897", docker_command)
        self.assertIn("http_proxy=http://host.docker.internal:7897", docker_command)

    def test_timed_out_branch_is_recorded_and_container_is_removed(self):
        timeout = __import__("subprocess").TimeoutExpired(
            cmd=["docker", "run"], timeout=3, output="partial", stderr="slow"
        )
        removed = SimpleNamespace(returncode=0, stdout="removed\n", stderr="")
        with patch(
            "repro_wrappers.run_skillsbench_causalflow_repair._task_resource_limits",
            return_value={"cpus": 1, "memory_mb": 512},
        ), patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.container_proxy_env",
            return_value={},
        ), patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.subprocess.run",
            side_effect=[timeout, removed],
        ) as run, patch(
            "repro_wrappers.run_skillsbench_causalflow_repair.shutil.copytree",
        ):
            original_write_text = Path.write_text

            def write_text(path, data, *args, **kwargs):
                result = original_write_text(path, data, *args, **kwargs)
                if path.name == "replay-commands.json":
                    (path.parent / "container.cid").write_text("container-123")
                return result

            with patch.object(Path, "write_text", new=write_text):
                result = _run_branch(
                    image="task:test",
                    task_dir=Path("/tmp/task"),
                    skills_root=Path("/tmp/task/skills"),
                    workspace="/root",
                    commands=["echo ok"],
                    timeout=3,
                )

        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["return_code"])
        self.assertIn("branch timed out after 3 seconds", result["log_tail"])
        self.assertEqual(run.call_args_list[1].args[0], ["docker", "rm", "-f", "container-123"])

    def test_execution_coverage_keeps_rejected_empty_tool_calls_auditable(self):
        executed = SimpleNamespace(
            step_id=1,
            tool_call_id="call-1",
            kind="execute",
            title="echo ok",
            command="echo ok",
            status="completed",
            output="return_code=0",
        )
        rejected = SimpleNamespace(
            step_id=2,
            tool_call_id="call-2",
            kind="execute",
            title="[invalid run_shell call]",
            command=None,
            status="failed",
            output="Invalid run_shell arguments: expected a non-empty command",
        )
        skill = SimpleNamespace(
            step_id=3,
            tool_call_id="skill-1",
            kind="skill",
            title="activate_skill",
            command=None,
            status="completed",
            output="loaded_skills=1",
        )

        commands, coverage = _execution_coverage(
            SimpleNamespace(events=[executed, rejected, skill])
        )

        self.assertEqual(commands, [executed])
        self.assertEqual(coverage["execute_tool_events"], 2)
        self.assertEqual(coverage["executable_command_events"], 1)
        self.assertEqual(
            coverage["non_executable_execute_events"][0]["step_id"], 2
        )

    def test_existing_image_is_inspected_and_recorded(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout="sha256:abc123\n",
            stderr="",
        )
        with patch(
            "repro_wrappers.run_skillsbench_full_causalflow.subprocess.run",
            return_value=completed,
        ) as run:
            result = _use_existing_image("task:fixed")

        run.assert_called_once_with(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                "task:fixed",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result["image_id"], "sha256:abc123")
        self.assertTrue(result["skipped"])

    def test_existing_image_must_exist(self):
        completed = SimpleNamespace(returncode=1, stdout="", stderr="missing")
        with patch(
            "repro_wrappers.run_skillsbench_full_causalflow.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(SystemExit, "missing"):
                _use_existing_image("task:missing")

    def test_full_trace_counterfactual_replays_exact_prefix_and_full_suffix(self):
        parsed = SimpleNamespace(
            events=[
                event(1, "inspect"),
                event(2, "write", writes=("output.json",)),
                event(3, "check", reads=("output.json",)),
            ]
        )
        graph = SimpleNamespace(edges=[], nodes={})

        selected, prerequisites, downstream, label = (
            _counterfactual_replay_steps(
                parsed,
                graph,
                target_step=2,
                final_state_support_steps=[2],
                replay_mode="full-trace",
            )
        )

        self.assertEqual(selected, {1, 2, 3})
        self.assertEqual(prerequisites, [])
        self.assertEqual(downstream, [])
        self.assertEqual(label, "full_trace_exact_prefix_and_full_suffix")

    def test_final_state_support_keeps_each_paths_latest_writer(self):
        parsed = SimpleNamespace(
            events=[
                event(1, "write old a", writes=("a.py",)),
                event(2, "write b", writes=("b.py",)),
                event(3, "write new a", writes=("a.py",)),
                event(4, "delete c", deletes=("c.py",)),
            ]
        )
        graph = SimpleNamespace(edges=[], nodes={})

        self.assertEqual(_final_state_support_steps(parsed, graph), [2, 3])

    def test_replay_with_no_agent_writes_satisfies_hash_fidelity_vacuously(self):
        no_write_event = SimpleNamespace(
            step_id=1,
            command="ls /root",
            output="return_code=0\n",
            argument_source="result_marker",
            inferred_deletes=(),
            observed_writes=(),
            observed_write_hashes={},
        )
        parsed = SimpleNamespace(events=[no_write_event])
        replay = {
            "workspace_manifest": {},
            "command_executions": [{"return_code": 0}],
        }

        report = _replay_fidelity_report(parsed, replay)

        self.assertTrue(report["artifact_hashes_match"])
        self.assertEqual(report["expected_final_write_hashes"], {})
        self.assertEqual(report["artifact_hash_mismatches"], {})

    def test_task_resource_limits_match_frontmatter(self):
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            (task_dir / "task.md").write_text(
                "---\nsandbox:\n  cpus: 2\n  memory_mb: 4096\n---\nbody\n"
            )
            self.assertEqual(
                _task_resource_limits(task_dir),
                {"cpus": 2, "memory_mb": 4096},
            )

    def test_launcher_traces_back_to_script_writer(self):
        writer = event(1, "cat <<'PY' > /root/solve.py\n...\nPY", writes=("solve.py",))
        launcher = event(
            2,
            "python /root/solve.py",
            reads=("solve.py",),
            writes=("report.json",),
        )
        parsed = SimpleNamespace(events=[writer, launcher])

        self.assertIs(_target_event(parsed, ("report.json",)), writer)

    def test_compound_artifact_command_remains_the_target(self):
        command = "cat <<'PY' > solve.py\n...\nPY\npython solve.py"
        artifact = event(1, command, writes=("report.json",))
        parsed = SimpleNamespace(events=[artifact])

        self.assertIs(_target_event(parsed, ("report.json",)), artifact)

    def test_repeated_equal_launchers_use_the_newest_script_writer(self):
        old_writer = event(1, "cat > solve.py", writes=("solve.py",))
        old_launcher = event(2, "python /root/solve.py", writes=("report.json",))
        new_writer = event(3, "cat > solve.py", writes=("solve.py",))
        new_launcher = event(4, "python /root/solve.py", writes=("report.json",))
        parsed = SimpleNamespace(
            events=[old_writer, old_launcher, new_writer, new_launcher]
        )

        self.assertIs(_target_event(parsed, ("report.json",)), new_writer)

    def test_relative_artifact_write_matches_absolute_verifier_path(self):
        writer = event(1, "cat > solve.py", writes=("solve.py",))
        launcher = event(2, "python /root/solve.py", writes=("report.json",))
        parsed = SimpleNamespace(events=[writer, launcher])

        self.assertIs(_target_event(parsed, ("/root/report.json",)), writer)

    def test_bare_script_write_matches_absolute_launcher(self):
        writer = event(1, "cat > /root/solve.py", writes=("solve.py",))
        launcher = event(
            2,
            "python /root/solve.py",
            writes=("output/report.json",),
        )
        parsed = SimpleNamespace(events=[writer, launcher])

        self.assertIs(_target_event(parsed, ("/root/output/report.json",)), writer)

    def test_relative_file_matches_absolute_verifier_directory(self):
        writer = event(1, "cat > solve.py", writes=("solve.py",))
        launcher = event(
            2,
            "python /root/solve.py",
            writes=("output/report.md",),
        )
        parsed = SimpleNamespace(events=[writer, launcher])

        self.assertIs(_target_event(parsed, ("/root/output",)), writer)


if __name__ == "__main__":
    unittest.main()
