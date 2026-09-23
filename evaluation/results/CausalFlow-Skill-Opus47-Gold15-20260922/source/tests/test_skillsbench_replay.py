from __future__ import annotations

import json
import hashlib
import http.client
import os
import subprocess
import tempfile
import time
import unittest
import urllib.error
import base64
import struct
import zipfile
import zlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from replay_graph.schema import EdgeEvidence, EdgeStatus
from skillsbench_replay.atif import load_run, parse_atif
from skillsbench_replay.graph import (
    SkillsBenchGraphBuilder,
    infer_task_workspace,
    infer_verifier_reads,
    resource_ids_for_paths,
)
from skillsbench_replay.planner import LocalReplayRunner, ReplayPlanner
from skillsbench_replay.openrouter_acp_agent import (
    _run_command,
    content_digest,
    describe_openrouter_http_error,
    openrouter_chat,
    run_agent,
    run_shell,
    workspace_manifest,
)
from skillsbench_replay.schema import CommandEvent
from skillsbench_replay.semantic import SemanticDependency, add_semantic_dependencies
from skillsbench_replay.shell_io import infer_shell_access, local_replay_safety_reason
from skillsbench_replay.snapshot import WorkspaceSnapshot, attach_observed_writes
from repro_wrappers.run_skillsbench_openrouter_smoke import (
    OFFICIAL_SANDBOX_USER,
    container_proxy_env,
)
from repro_wrappers.run_skillsbench_openrouter_task import (
    replace_staged_dockerfile_with_existing_image,
    stage_task_with_network_proxy,
)
from repro_wrappers.subset25.summarize_skillsbench_full_result import summarize_payload
from repro_wrappers.prebuild_skillsbench_task import (
    docker_build_proxy_env,
    inject_agent_python_fallback,
    inject_apt_mirror_profile,
    inject_pip_index_arg,
)


def event(step_id: int, command: str) -> CommandEvent:
    access = infer_shell_access(command)
    return CommandEvent(
        step_id=step_id,
        atif_step_id=step_id,
        tool_call_id=f"call-{step_id}",
        kind="execute",
        title=command,
        command=command,
        argument_source="title_fallback",
        status="completed",
        inferred_reads=access.reads,
        inferred_writes=access.writes,
        inferred_deletes=access.deletes,
        replayable=True,
        warnings=access.warnings,
    )


class SkillsBenchReplayTests(unittest.TestCase):
    def test_json_digest_ignores_order_and_documented_volatile_metadata(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text(
                '{"ReportID":"one","CreatedAt":"today","value":{"b":2,"a":1}}'
            )
            second.write_text(
                '{"value":{"a":1,"b":2},"CreatedAt":"tomorrow","ReportID":"two"}'
            )

            self.assertEqual(content_digest(str(first)), content_digest(str(second)))
            self.assertTrue(content_digest(str(first)).startswith("json:"))

    def test_ooxml_digest_ignores_zip_and_core_property_timestamps(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first = root / "first.xlsx"
            second = root / "second.xlsx"
            core_template = (
                '<cp:coreProperties xmlns:cp="x" xmlns:dcterms="y">'
                '<dcterms:created xsi:type="dcterms:W3CDTF" xmlns:xsi="z">{}</dcterms:created>'
                '<dcterms:modified xsi:type="dcterms:W3CDTF" xmlns:xsi="z">{}</dcterms:modified>'
                '</cp:coreProperties>'
            )
            for path, date, zip_date in [
                (first, "2026-01-01T00:00:00Z", (2026, 1, 1, 0, 0, 0)),
                (second, "2026-02-02T00:00:00Z", (2026, 2, 2, 0, 0, 0)),
            ]:
                with zipfile.ZipFile(path, "w") as package:
                    for name, data in [
                        ("docProps/core.xml", core_template.format(date, date).encode()),
                        ("xl/worksheets/sheet1.xml", b"<sheet><v>42</v></sheet>"),
                    ]:
                        info = zipfile.ZipInfo(name, date_time=zip_date)
                        package.writestr(info, data)

            self.assertEqual(content_digest(str(first)), content_digest(str(second)))
            self.assertTrue(content_digest(str(first)).startswith("ooxml:"))

    def test_png_digest_compares_decoded_pixels_not_filter_or_compression(self):
        def chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        def write_png(path: Path, scanline: bytes, level: int) -> None:
            ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(scanline, level))
                + chunk(b"IEND", b"")
            )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first = root / "first.png"
            second = root / "second.png"
            pixels = bytes([10, 20, 30, 40, 50, 60])
            write_png(first, b"\x00" + pixels, 1)
            # Sub filtering stores each byte relative to the previous RGB pixel.
            write_png(second, b"\x01" + bytes([10, 20, 30, 30, 30, 30]), 9)

            self.assertEqual(content_digest(str(first)), content_digest(str(second)))
            self.assertTrue(content_digest(str(first)).startswith("png:"))

    def test_manifest_hashes_large_files_and_ignores_generated_logs_and_next(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            large = root / "output.nc"
            with large.open("wb") as handle:
                handle.truncate(21 * 1024 * 1024)
            (root / "search_log.txt").write_text("volatile")
            (root / ".next").mkdir()
            (root / ".next" / "trace").write_text("volatile")

            manifest = workspace_manifest(str(root))

            self.assertIn("output.nc", manifest)
            self.assertFalse(manifest["output.nc"].startswith("large:"))
            self.assertNotIn("search_log.txt", manifest)
            self.assertNotIn(".next/trace", manifest)

    def test_timeout_kills_background_descendants(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            sentinel = root / "survived.txt"
            _result, _stdout, _stderr, timed_out = _run_command(
                f"(sleep 0.4; echo survived > {sentinel}) & wait",
                raw_root,
                env=os.environ.copy(),
                timeout=0.05,
            )
            time.sleep(0.5)

            self.assertTrue(timed_out)
            self.assertFalse(sentinel.exists())

    def test_agent_shell_replaces_non_utf8_output(self):
        with tempfile.TemporaryDirectory() as raw_root:
            output, succeeded = run_shell("printf '\\340'", raw_root)

        self.assertTrue(succeeded)
        self.assertIn("stdout:\n�", output)

    def test_official_sandbox_user_is_non_root(self):
        self.assertEqual(OFFICIAL_SANDBOX_USER, "agent")

    def test_prebuild_injects_pip_arg_without_changing_install_command(self):
        original = (
            "# syntax=docker/dockerfile:1\n"
            "FROM python:3.12-slim\n"
            "RUN pip install numpy==1.26.4\n"
        )
        staged = inject_pip_index_arg(original)
        self.assertEqual(staged.count("ARG PIP_INDEX_URL"), 1)
        self.assertIn(
            "FROM python:3.12-slim\nARG PIP_INDEX_URL\n",
            staged,
        )
        self.assertIn("RUN pip install numpy==1.26.4\n", staged)

    def test_apt_mirror_profile_changes_only_debian_source_layer(self):
        original = (
            "FROM python:3.12-slim\n"
            "ARG PIP_INDEX_URL\n"
            "RUN apt-get update && apt-get install -y git\n"
        )
        staged = inject_apt_mirror_profile(original, "tuna")
        self.assertIn(
            "FROM python:3.12-slim\nARG PIP_INDEX_URL\nRUN if [ -f ",
            staged,
        )
        self.assertIn(
            "http://mirrors.tuna.tsinghua.edu.cn/debian-security",
            staged,
        )
        self.assertIn(
            "http://mirrors.tuna.tsinghua.edu.cn/debian",
            staged,
        )
        self.assertIn(
            "RUN apt-get update && apt-get install -y git\n",
            staged,
        )
        self.assertEqual(inject_apt_mirror_profile(original, "default"), original)

    def test_apt_mirror_profile_also_supports_ubuntu_ports(self):
        original = (
            "FROM ubuntu:24.04\n"
            "RUN apt-get update && apt-get install -y python3\n"
        )
        staged = inject_apt_mirror_profile(original, "tuna")
        self.assertIn(
            "http://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports", staged
        )
        self.assertIn(
            "RUN apt-get update && apt-get install -y python3\n", staged
        )

    def test_prebuild_translates_loopback_proxy_for_docker(self):
        with patch.dict(
            os.environ,
            {"HTTPS_PROXY": "http://127.0.0.1:7897"},
            clear=True,
        ):
            self.assertEqual(
                docker_build_proxy_env(),
                {"HTTPS_PROXY": "http://host.docker.internal:7897"},
            )

    def test_agent_python_fallback_is_conditional_and_runtime_only(self):
        original = "FROM ubuntu:24.04\nRUN echo task\n"
        staged = inject_agent_python_fallback(original)
        self.assertIn("if ! command -v python3", staged)
        self.assertIn("python3 ca-certificates", staged)
        self.assertIn("RUN echo task\n", staged)

    def test_existing_task_image_rewrite_records_provenance(self):
        with tempfile.TemporaryDirectory() as raw_root:
            task_dir = Path(raw_root) / "demo"
            environment = task_dir / "environment"
            environment.mkdir(parents=True)
            dockerfile = environment / "Dockerfile"
            original = (
                "FROM python:3.12-slim\n"
                "WORKDIR /root\n"
                "RUN echo task\n"
            )
            dockerfile.write_text(original)

            with patch(
                "repro_wrappers.run_skillsbench_openrouter_task.subprocess.run",
                return_value=SimpleNamespace(stdout="sha256:abc123\n"),
            ) as inspect:
                provenance = replace_staged_dockerfile_with_existing_image(
                    task_dir=task_dir,
                    image="causalflow-prebuild-demo:validated",
                )

            self.assertEqual(
                dockerfile.read_text(),
                "FROM causalflow-prebuild-demo:validated\nWORKDIR /root\n",
            )
            self.assertEqual(provenance["image_id"], "sha256:abc123")
            self.assertEqual(
                provenance["source_dockerfile_sha256"],
                hashlib.sha256(original.encode()).hexdigest(),
            )
            inspect.assert_called_once_with(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "{{.Id}}",
                    "causalflow-prebuild-demo:validated",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )

    def test_staged_apt_mirror_does_not_modify_source_task(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "tasks" / "demo"
            environment = source / "environment"
            environment.mkdir(parents=True)
            (source / "task.md").write_text(
                "---\nverifier:\n  type: test-script\n---\n# Demo\n"
            )
            original = (
                "FROM python:3.12-slim\n"
                "RUN apt-get update && apt-get install -y git\n"
            )
            (environment / "Dockerfile").write_text(original)

            staged = stage_task_with_network_proxy(
                source=source,
                skillsbench_root=root,
                jobs_label="apt-mirror-test",
                proxy_env={},
                forward_build_proxy=False,
                forward_verifier_proxy=False,
                apt_mirror_profile="tuna",
            )

            staged_text = (staged / "environment" / "Dockerfile").read_text()
            self.assertIn("mirrors.tuna.tsinghua.edu.cn/debian", staged_text)
            self.assertEqual((environment / "Dockerfile").read_text(), original)

    def test_container_proxy_translates_host_loopback(self):
        with patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://127.0.0.1:7897",
                "HTTPS_PROXY": "http://localhost:7897",
                "ALL_PROXY": "socks5://127.0.0.1:7898",
            },
            clear=True,
        ):
            proxies = container_proxy_env()
        self.assertEqual(
            proxies["HTTP_PROXY"], "http://host.docker.internal:7897"
        )
        self.assertEqual(
            proxies["HTTPS_PROXY"], "http://host.docker.internal:7897"
        )
        self.assertEqual(
            proxies["ALL_PROXY"], "socks5://host.docker.internal:7898"
        )

    def test_staged_network_proxy_covers_build_and_verifier(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "tasks" / "demo"
            environment = source / "environment"
            environment.mkdir(parents=True)
            task_text = (
                "---\n"
                "verifier:\n"
                "  type: test-script\n"
                "---\n"
                "# Demo\n"
            )
            (source / "task.md").write_text(task_text)
            (environment / "Dockerfile").write_text("FROM python:3.12-slim\n")

            with patch.dict(os.environ, {}, clear=True):
                staged = stage_task_with_network_proxy(
                    source=source,
                    skillsbench_root=root,
                    jobs_label="proxy-test",
                    proxy_env={
                        "HTTP_PROXY": "http://host.docker.internal:7897",
                        "NO_PROXY": "localhost,127.0.0.1",
                    },
                    forward_build_proxy=True,
                    forward_verifier_proxy=True,
                )
                self.assertEqual(
                    os.environ["CAUSALFLOW_CONTAINER_HTTP_PROXY"],
                    "http://host.docker.internal:7897",
                )

            import yaml

            compose = yaml.safe_load(
                (staged / "environment" / "docker-compose.yaml").read_text()
            )
            build_args = compose["services"]["main"]["build"]["args"]
            self.assertEqual(
                build_args["HTTP_PROXY"],
                "${CAUSALFLOW_CONTAINER_HTTP_PROXY}",
            )
            self.assertEqual(
                build_args["http_proxy"],
                "${CAUSALFLOW_CONTAINER_HTTP_PROXY}",
            )
            staged_task = (staged / "task.md").read_text()
            self.assertIn(
                "HTTP_PROXY: ${CAUSALFLOW_CONTAINER_HTTP_PROXY}", staged_task
            )
            self.assertIn(
                "no_proxy: ${CAUSALFLOW_CONTAINER_NO_PROXY}", staged_task
            )
            self.assertEqual((source / "task.md").read_text(), task_text)
            self.assertEqual(
                (source / "environment" / "Dockerfile").read_text(),
                "FROM python:3.12-slim\n",
            )

    def test_staged_pip_index_changes_only_build_transport(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "tasks" / "demo"
            environment = source / "environment"
            environment.mkdir(parents=True)
            (source / "task.md").write_text(
                "---\nverifier:\n  type: test-script\n---\n# Demo\n"
            )
            original_dockerfile = (
                "FROM python:3.12-slim\n"
                "RUN pip install --no-cache-dir numpy==1.26.4\n"
            )
            (environment / "Dockerfile").write_text(original_dockerfile)

            staged = stage_task_with_network_proxy(
                source=source,
                skillsbench_root=root,
                jobs_label="pip-index-test",
                proxy_env={},
                forward_build_proxy=False,
                forward_verifier_proxy=False,
                pip_index_url="https://pypi.example/simple",
            )

            import yaml

            staged_dockerfile = (
                staged / "environment" / "Dockerfile"
            ).read_text()
            self.assertIn(
                "FROM python:3.12-slim\nARG PIP_INDEX_URL\n",
                staged_dockerfile,
            )
            self.assertIn(
                "RUN pip install --no-cache-dir numpy==1.26.4\n",
                staged_dockerfile,
            )
            compose = yaml.safe_load(
                (staged / "environment" / "docker-compose.yaml").read_text()
            )
            self.assertEqual(
                compose["services"]["main"]["build"]["args"][
                    "PIP_INDEX_URL"
                ],
                "https://pypi.example/simple",
            )
            self.assertEqual(
                (source / "environment" / "Dockerfile").read_text(),
                original_dockerfile,
            )

    def test_openrouter_http_error_keeps_safe_diagnostics(self):
        payload = {
            "error": {
                "code": "permission_denied",
                "type": "permission_denied",
                "message": "API key is disabled",
            },
            "openrouter_metadata": {
                "pipeline": [
                    {"type": "authentication", "status": "blocked"}
                ]
            },
        }
        exc = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            403,
            "Forbidden",
            {},
            BytesIO(json.dumps(payload).encode()),
        )
        text = describe_openrouter_http_error(exc)
        self.assertIn("OpenRouter HTTP 403", text)
        self.assertIn("permission_denied", text)
        self.assertIn("API key is disabled", text)
        self.assertIn("authentication:blocked", text)

    def test_openrouter_retries_retryable_error_body(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(self.payload).encode()

        responses = [
            Response({"error": {"code": 503, "message": "temporary"}}),
            Response(
                {
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 3,
                        "total_tokens": 14,
                    },
                }
            ),
        ]
        with (
            patch.dict(
                os.environ,
                {
                    "OPENROUTER_API_KEY": "test-key",
                    "CAUSALFLOW_OPENROUTER_MAX_TOKENS": "1234",
                },
            ),
            patch(
                "skillsbench_replay.openrouter_acp_agent.urllib.request.urlopen",
                side_effect=responses,
            ) as urlopen,
            patch("skillsbench_replay.openrouter_acp_agent.time.sleep"),
        ):
            message = openrouter_chat("test/model", [{"role": "user", "content": "x"}])
        self.assertEqual(message["content"], "ok")
        self.assertEqual(message["_causalflow_usage"]["total_tokens"], 14)
        self.assertEqual(message["_causalflow_finish_reason"], "stop")
        self.assertEqual(urlopen.call_count, 2)
        request = urlopen.call_args_list[0].args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["max_tokens"], 1234)
        self.assertEqual(payload["usage"], {"include": True})

    def test_openrouter_retries_partial_http_response(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {"message": {"role": "assistant", "content": "ok"}}
                        ]
                    }
                ).encode()

        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            patch(
                "skillsbench_replay.openrouter_acp_agent.urllib.request.urlopen",
                side_effect=[http.client.IncompleteRead(b"partial"), Response()],
            ) as urlopen,
            patch("skillsbench_replay.openrouter_acp_agent.time.sleep"),
        ):
            message = openrouter_chat("test/model", [{"role": "user", "content": "x"}])
        self.assertEqual(message["content"], "ok")
        self.assertEqual(urlopen.call_count, 2)

    def test_skill_preload_is_reported_as_a_skill_activation(self):
        tool_calls = []
        tool_results = []
        with (
            patch(
                "skillsbench_replay.openrouter_acp_agent.load_skill_context",
                return_value=("\nSKILL BODY", ["/skills/demo/SKILL.md"]),
            ),
            patch(
                "skillsbench_replay.openrouter_acp_agent.openrouter_chat",
                return_value={"role": "assistant", "content": "done"},
            ),
            patch(
                "skillsbench_replay.openrouter_acp_agent.emit_tool_call",
                side_effect=lambda *args, **kwargs: tool_calls.append((args, kwargs)),
            ),
            patch(
                "skillsbench_replay.openrouter_acp_agent.emit_tool_result",
                side_effect=lambda *args, **kwargs: tool_results.append((args, kwargs)),
            ),
            patch("skillsbench_replay.openrouter_acp_agent.emit_text"),
        ):
            usage = run_agent(
                model="test/model",
                instruction="solve",
                cwd="/app",
                session_id="session-1",
            )

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0][0][2], "activate_skill")
        self.assertEqual(tool_calls[0][1]["kind"], "skill")
        self.assertIn("[skill: /skills/demo/SKILL.md]", tool_results[0][0][2])
        self.assertIn("CAUSALFLOW_RESOURCE_EVENT=", tool_results[0][0][2])
        self.assertEqual(usage["totalTokens"], 0)

    def test_atif_recovers_command_but_labels_fallback_evidence(self):
        record = {
            "schema_version": "ATIF-v1.7",
            "session_id": "demo",
            "agent": {"name": "codex-acp", "version": "unknown"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "agent",
                    "message": "",
                    "tool_calls": [
                        {
                            "tool_call_id": "c1",
                            "function_name": "execute",
                            "arguments": {},
                            "extra": {
                                "title": "cat input.txt > output.txt",
                                "status": "completed",
                            },
                        }
                    ],
                    "observation": {
                        "results": [
                            {
                                "source_call_id": "c1",
                                "content": (
                                    "ok\nCAUSALFLOW_RESOURCE_EVENT="
                                    '{"observed_reads":["input.txt"],'
                                    '"observed_writes":["output.txt"],'
                                    '"observed_write_hashes":{"output.txt":"abc123"},'
                                    '"observed_deletes":[]}'
                                ),
                            }
                        ]
                    },
                }
            ],
        }
        parsed = parse_atif(record)
        self.assertEqual(parsed.events[0].command, "cat input.txt > output.txt")
        self.assertEqual(parsed.events[0].argument_source, "title_fallback")
        self.assertEqual(parsed.events[0].inferred_reads, ("input.txt",))
        self.assertEqual(parsed.events[0].inferred_writes, ("output.txt",))
        self.assertEqual(parsed.events[0].observed_reads, ("input.txt",))
        self.assertEqual(parsed.events[0].observed_writes, ("output.txt",))
        self.assertEqual(
            parsed.events[0].observed_write_hashes,
            {"output.txt": "abc123"},
        )
        self.assertIn("title_fallback", parsed.warnings[0])

    def test_atif_refuses_probably_truncated_title_without_marker(self):
        record = {
            "agent": {"name": "causalflow-openrouter-acp"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "agent",
                    "tool_calls": [
                        {
                            "tool_call_id": "c1",
                            "function_name": "execute",
                            "arguments": {},
                            "extra": {"title": "echo " + "x" * 3995},
                        }
                    ],
                }
            ],
        }

        parsed = parse_atif(record)
        self.assertIsNone(parsed.events[0].command)
        self.assertEqual(parsed.events[0].argument_source, "truncated_title")
        self.assertFalse(parsed.events[0].replayable)

    def test_atif_prefers_lossless_command_result_marker(self):
        full_command = "cat <<'PY' > /root/solve.py\n" + ("x = 1\n" * 900) + "PY"
        record = {
            "schema_version": "ATIF-v1.7",
            "session_id": "long-command",
            "agent": {"name": "causalflow-openrouter-acp"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "agent",
                    "tool_calls": [
                        {
                            "tool_call_id": "c1",
                            "function_name": "execute",
                            "arguments": {},
                            "extra": {
                                "title": full_command[:3960] + "\n...[truncated]",
                                "status": "completed",
                            },
                        }
                    ],
                    "observation": {
                        "results": [
                            {
                                "source_call_id": "c1",
                                "content": (
                                    "ok\nCAUSALFLOW_COMMAND_JSON="
                                    + json.dumps(full_command)
                                ),
                            }
                        ]
                    },
                }
            ],
        }

        parsed = parse_atif(record)
        self.assertEqual(parsed.events[0].command, full_command)
        self.assertEqual(parsed.events[0].argument_source, "result_marker")

    def test_atif_decodes_compressed_long_command_marker(self):
        full_command = "cat <<'PY' > solve.py\n" + ("print('x')\n" * 3000) + "PY"
        marker = base64.b64encode(
            zlib.compress(full_command.encode("utf-8"), level=9)
        ).decode("ascii")
        record = {
            "agent": {"name": "causalflow-openrouter-acp"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "agent",
                    "tool_calls": [
                        {
                            "tool_call_id": "c1",
                            "function_name": "execute",
                            "arguments": {},
                            "extra": {"title": full_command[:4000]},
                        }
                    ],
                    "observation": {
                        "results": [
                            {
                                "source_call_id": "c1",
                                "content": "CAUSALFLOW_COMMAND_ZLIB_B64=" + marker,
                            }
                        ]
                    },
                }
            ],
        }

        parsed = parse_atif(record)
        self.assertEqual(parsed.events[0].command, full_command)
        self.assertEqual(parsed.events[0].argument_source, "result_marker")

    def test_atif_refuses_tool_call_without_command_evidence(self):
        record = {
            "agent": {"name": "unknown"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "agent",
                    "tool_calls": [
                        {
                            "tool_call_id": "c1",
                            "function_name": "other",
                            "arguments": {},
                            "extra": {"title": "Thinking about the task"},
                        }
                    ],
                }
            ],
        }
        parsed = parse_atif(record)
        self.assertIsNone(parsed.events[0].command)
        self.assertFalse(parsed.events[0].replayable)

    def test_load_run_recovers_exact_terminal_command_from_llm_trajectory(self):
        full_command = "python3 - <<'PY'\n" + ("print('exact')\n" * 500) + "PY"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "trainer").mkdir()
            (root / "trajectory").mkdir()
            (root / "trainer" / "atif.json").write_text(
                json.dumps(
                    {
                        "agent": {"name": "openhands"},
                        "steps": [
                            {
                                "step_id": 1,
                                "source": "agent",
                                "tool_calls": [
                                    {
                                        "tool_call_id": "c1",
                                        "function_name": "execute",
                                        "arguments": {},
                                        "extra": {
                                            "title": full_command[:3990],
                                            "status": "completed",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                )
            )
            exchange = {
                "response": {
                    "body": {
                        "output": [
                            {
                                "type": "function_call",
                                "call_id": "c1",
                                "name": "terminal",
                                "arguments": json.dumps({"command": full_command}),
                            }
                        ]
                    }
                }
            }
            (root / "trajectory" / "llm_trajectory.jsonl").write_text(
                json.dumps(exchange) + "\n"
            )

            parsed = load_run(root)

            self.assertEqual(parsed.events[0].command, full_command)
            self.assertEqual(
                parsed.events[0].argument_source,
                "llm_trajectory.arguments.command",
            )
            self.assertTrue(parsed.events[0].replayable)

    def test_atif_converts_file_editor_mutations_to_replay_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "solution.py"
            record = {
                "agent": {"name": "openhands"},
                "steps": [
                    {
                        "step_id": 1,
                        "source": "agent",
                        "tool_calls": [
                            {
                                "tool_call_id": "create",
                                "function_name": "edit",
                                "arguments": {},
                                "extra": {"title": "file_editor create"},
                            }
                        ],
                    },
                    {
                        "step_id": 2,
                        "source": "agent",
                        "tool_calls": [
                            {
                                "tool_call_id": "replace",
                                "function_name": "edit",
                                "arguments": {},
                                "extra": {"title": "file_editor replace"},
                            }
                        ],
                    },
                ],
            }
            parsed = parse_atif(
                record,
                llm_tool_calls={
                    "create": (
                        "file_editor",
                        {
                            "command": "create",
                            "path": str(target),
                            "file_text": "value = 1\n",
                        },
                    ),
                    "replace": (
                        "file_editor",
                        {
                            "command": "str_replace",
                            "path": str(target),
                            "old_str": "value = 1",
                            "new_str": "value = 2",
                        },
                    ),
                },
            )

            for replay_event in parsed.events:
                completed = subprocess.run(
                    ["bash", "-c", replay_event.command or ""],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

            self.assertEqual(target.read_text(), "value = 2\n")
            self.assertTrue(all(event.kind == "execute" for event in parsed.events))
            self.assertEqual(parsed.events[0].inferred_writes, (str(target),))
            self.assertEqual(parsed.events[1].inferred_reads, (str(target),))
            self.assertEqual(parsed.events[1].inferred_writes, (str(target),))

    def test_graph_slice_skips_independent_command(self):
        events = [
            event(1, "cat input.txt > a.txt"),
            event(2, "cat independent.txt > b.txt"),
            event(3, "cat a.txt b.txt > out.txt"),
        ]
        graph = SkillsBenchGraphBuilder().build(events, verifier_reads=("out.txt",))
        changed = resource_ids_for_paths(graph, ["input.txt"])
        selected = ReplayPlanner().selected_steps(graph, changed)
        self.assertEqual(selected, [1, 3])
        self.assertNotIn(2, selected)
        self.assertFalse(graph.metadata["global_sequential_edges"])

    def test_slice_that_cannot_reach_verifier_requires_full_fallback(self):
        events = [
            event(1, "cat rule.md"),
            event(2, "echo done > output.txt"),
        ]
        graph = SkillsBenchGraphBuilder().build(
            events,
            verifier_reads=("output.txt",),
        )
        changed = resource_ids_for_paths(graph, ["rule.md"])
        planner = ReplayPlanner()
        selection = planner.plan(graph, changed)
        self.assertEqual(selection.selected_step_ids, (1,))
        self.assertFalse(selection.verifier_reachable)
        self.assertTrue(selection.fallback_required)
        self.assertIn("semantic dependency", selection.reason or "")
        self.assertEqual(planner.safe_selected_steps(graph, changed, [1, 2]), [1, 2])

    def test_semantic_skill_edge_connects_sparse_slice_to_verifier(self):
        events = [
            event(1, "cat /skills/rule/SKILL.md"),
            event(2, "cat independent.txt > notes.txt"),
            event(3, "python classify.py > output.txt"),
        ]
        graph = SkillsBenchGraphBuilder().build(
            events,
            verifier_reads=("output.txt",),
        )
        added = add_semantic_dependencies(
            graph,
            [
                SemanticDependency(
                    source_path="/skills/rule/SKILL.md",
                    target_step_id=3,
                    relation="required",
                    confidence=0.9,
                    reason="the command applies the classification rule",
                    shared_concepts=("classification rule",),
                    judge="test",
                )
            ],
        )
        changed = resource_ids_for_paths(graph, ["/skills/rule/SKILL.md"])
        selection = ReplayPlanner().plan(graph, changed)
        self.assertEqual(selection.selected_step_ids, (1, 3))
        self.assertTrue(selection.verifier_reachable)
        self.assertEqual(selection.regenerate_decision_step_ids, (3,))
        self.assertTrue(selection.fallback_required)
        self.assertIn("command-only replay", selection.reason or "")
        structural = ReplayPlanner().plan(
            graph, changed, supports_model_regeneration=True
        )
        self.assertFalse(structural.fallback_required)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].status, EdgeStatus.MAY)
        self.assertEqual(added[0].evidence, EdgeEvidence.INFERRED)
        self.assertEqual(added[0].target, "decision:3")
        self.assertEqual(graph.metadata["semantic_edge_count"], 1)

    def test_semantic_edges_reject_adjacency_and_low_confidence(self):
        graph = SkillsBenchGraphBuilder().build(
            [
                event(1, "cat /skills/rule/SKILL.md"),
                event(2, "echo done > output.txt"),
            ],
            verifier_reads=("output.txt",),
        )
        added = add_semantic_dependencies(
            graph,
            [
                SemanticDependency(
                    source_path="/skills/rule/SKILL.md",
                    target_step_id=1,
                    relation="supporting",
                    confidence=0.99,
                    reason="mere read adjacency",
                ),
                SemanticDependency(
                    source_path="/skills/rule/SKILL.md",
                    target_step_id=2,
                    relation="supporting",
                    confidence=0.2,
                    reason="weak guess",
                ),
            ],
        )
        self.assertEqual(added, [])
        self.assertEqual(len(graph.metadata["semantic_edge_rejections"]), 2)

    def test_intervention_evidence_stays_soft_until_repeated_validation(self):
        graph = SkillsBenchGraphBuilder().build(
            [
                event(1, "cat /skills/rule/SKILL.md"),
                event(2, "echo done > output.txt"),
            ],
            verifier_reads=("output.txt",),
        )
        added = add_semantic_dependencies(
            graph,
            [
                SemanticDependency(
                    source_path="/skills/rule/SKILL.md",
                    target_step_id=2,
                    relation="required",
                    confidence=0.8,
                    reason="skill ablation changed the verified artifact",
                    judge="intervention:run-a",
                )
            ],
            evidence=EdgeEvidence.INTERVENED,
        )
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].evidence, EdgeEvidence.INTERVENED)
        self.assertEqual(added[0].status, EdgeStatus.MAY)
        self.assertEqual(graph.metadata["intervened_semantic_edge_count"], 1)

    def test_snapshot_upgrades_write_to_observed_must_edge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.txt").write_text("hello")
            before = WorkspaceSnapshot.capture(root)
            (root / "output.txt").write_text("hello")
            after = WorkspaceSnapshot.capture(root)
            command = event(1, "cat input.txt > output.txt")
            attach_observed_writes(command, before, after)
            graph = SkillsBenchGraphBuilder().build([command], initial_snapshot=before)
            write_edges = [
                edge
                for edge in graph.edges
                if edge.source == "step:1" and edge.metadata.get("path") == "output.txt"
            ]
            self.assertEqual(len(write_edges), 1)
            self.assertEqual(write_edges[0].status, EdgeStatus.MUST)
            self.assertEqual(write_edges[0].evidence, EdgeEvidence.OBSERVED)

    def test_heredoc_body_does_not_create_false_resources_or_versions(self):
        command = event(
            1,
            "cat <<'PY' > /root/replay.py\n"
            "victim = next(iter(M.items()))\n"
            "rate = 0.0\n"
            "PY",
        )
        command.observed_writes = ("replay.py",)
        graph = SkillsBenchGraphBuilder().build([command], workspace_root="/root")
        paths = [resource.metadata.get("path") for resource in graph.resources.values()]
        self.assertEqual(paths, ["/root/replay.py"])
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual(graph.edges[0].status, EdgeStatus.MUST)
        self.assertEqual(graph.edges[0].evidence, EdgeEvidence.OBSERVED)

    def test_runtime_read_upgrades_dependency_to_observed_must(self):
        command = event(1, "python replay.py")
        command.observed_reads = ("config.json", "trace.jsonl")
        graph = SkillsBenchGraphBuilder().build([command], workspace_root="/root")
        read_edges = [edge for edge in graph.edges if edge.target == "step:1"]
        self.assertEqual(len(read_edges), 3)
        observed = [
            edge for edge in read_edges if edge.evidence == EdgeEvidence.OBSERVED
        ]
        self.assertEqual(len(observed), 2)
        self.assertTrue(all(edge.status == EdgeStatus.MUST for edge in observed))

    def test_local_full_and_selective_replay_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.txt").write_text("old\n")
            (root / "independent.txt").write_text("fixed\n")
            events = [
                event(1, "cat input.txt > a.txt"),
                event(2, "cat independent.txt > b.txt"),
                event(3, "cat a.txt b.txt > out.txt"),
            ]
            graph = SkillsBenchGraphBuilder().build(events, verifier_reads=("out.txt",))

            def verifier(workspace: Path) -> bool:
                return (workspace / "out.txt").read_text() == "new\nfixed\n"

            comparison = LocalReplayRunner(
                root, events, graph, verifier=verifier
            ).compare({"input.txt": "new\n"})
            self.assertTrue(comparison.agreement)
            self.assertTrue(comparison.full.verifier_passed)
            self.assertTrue(comparison.selective.verifier_passed)
            self.assertEqual(comparison.full.executed_step_ids, [1, 2, 3])
            self.assertEqual(comparison.selective.executed_step_ids, [1, 3])
            self.assertAlmostEqual(comparison.command_reduction, 1 / 3)

    def test_load_run_reads_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "trainer").mkdir()
            (root / "trainer" / "atif.json").write_text(
                json.dumps(
                    {
                        "session_id": "oracle",
                        "agent": {"name": "oracle"},
                        "steps": [{"step_id": 1, "source": "user", "message": "x"}],
                    }
                )
            )
            (root / "result.json").write_text(json.dumps({"rewards": {"reward": 1.0}}))
            parsed = load_run(root)
            self.assertEqual(parsed.reward, 1.0)
            self.assertTrue(parsed.verifier_passed)
            self.assertEqual(parsed.events, [])

    def test_local_runner_rejects_hidden_pipeline_command(self):
        reason = local_replay_safety_reason("cat input.txt | curl https://example.com")
        self.assertIn("multiple shell commands", reason or "")

    def test_verifier_path_hints_exclude_infrastructure_and_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.sh").write_text(
                "#!/bin/sh\ncurl https://example.com/x\npytest /tests/test.py\n"
            )
            (root / "test.py").write_text(
                '"""headers/footers"""\nOUTPUT = "/app/out.json"\n'
            )
            self.assertEqual(infer_verifier_reads(root), ("/app/out.json",))

    def test_verifier_path_hints_resolve_pathlib_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_outputs.py").write_text(
                "from pathlib import Path\n"
                'OUTPUT_DIR = Path("/app/output")\n'
                'OUTPUT_FILE = OUTPUT_DIR / "report.json"\n'
            )
            self.assertEqual(
                infer_verifier_reads(root),
                ("/app/output", "/app/output/report.json"),
            )

    def test_verifier_path_hints_include_task_output_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_outputs.py").write_text(
                'SOLUTION = "/output/scenario_3.json"\n'
                'INPUT = "/data/scenario_3/scenario.json"\n'
            )
            self.assertEqual(
                infer_verifier_reads(root),
                ("/output/scenario_3.json", "/data/scenario_3/scenario.json"),
            )

    def test_workspace_root_aligns_relative_command_with_absolute_verifier(self):
        graph = SkillsBenchGraphBuilder().build(
            [event(1, "echo done > output.txt")],
            verifier_reads=("/app/output.txt",),
            workspace_root="/app",
        )
        verifier_edges = [
            edge for edge in graph.edges if edge.target == "verifier:skillsbench"
        ]
        self.assertEqual(len(verifier_edges), 1)
        resource = graph.resources[verifier_edges[0].source]
        self.assertEqual(resource.metadata["path"], "/app/output.txt")

    def test_verifier_path_prefix_connects_dynamic_filename(self):
        graph = SkillsBenchGraphBuilder().build(
            [event(1, "echo done > /output/scenario_3.json")],
            verifier_reads=("/output/scenario_",),
            workspace_root="/root",
        )
        verifier_edges = [
            edge for edge in graph.edges if edge.target == "verifier:skillsbench"
        ]
        self.assertEqual(len(verifier_edges), 1)
        resource = graph.resources[verifier_edges[0].source]
        self.assertEqual(resource.metadata["path"], "/output/scenario_3.json")

    def test_task_workspace_prefers_explicit_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "environment").mkdir()
            (root / "task.md").write_text("sandbox:\n  workdir: /app/task\n")
            (root / "environment" / "Dockerfile").write_text(
                "FROM python:3.11\nWORKDIR /fallback\n"
            )
            self.assertEqual(infer_task_workspace(root), "/app/task")

    def test_full_result_summary_keeps_only_auditable_metrics(self):
        payload = {
            "task": "example",
            "model": "openai/gpt-5.2-codex",
            "baseline_official_reward": 0.0,
            "baseline_saved_ctrf": {
                "tests": 3,
                "passed": 2,
                "failed": 1,
                "skipped": 0,
            },
            "strict_baseline_replay_matches": True,
            "baseline_replay_fidelity": {
                "lossless_command_markers": True,
                "recorded_command_count": 2,
                "replayed_command_count": 2,
                "command_count_matches": True,
                "return_codes_match": True,
                "artifact_hashes_match": True,
                "sandbox_identity_matches": True,
                "execution_identity": {
                    "agent_user": "agent",
                    "agent_uid": 1001,
                    "agent_gid": 1001,
                    "agent_home": "/home/agent",
                    "verifier_user": "root",
                },
                "expected_final_write_hashes": {"out.json": "abc"},
                "artifact_hash_mismatches": {},
            },
            "baseline_fresh_replay": {
                "reward": 0.0,
                "ctrf": {"tests": 3, "passed": 2, "failed": 1, "skipped": 0},
                "seconds": 1.5,
            },
            "causal_attribution": {"causal_steps": [], "seconds": 4.0},
            "reexecution_evaluations": [
                {
                    "phase": "crs_attribution",
                    "replay_ratio": 1.0,
                    "reward": 0.0,
                },
                {
                    "phase": "crs_attribution",
                    "replay_ratio": 1.0,
                    "reward": 0.0,
                },
            ],
            "summary": {
                "repair_candidates_evaluated": 0,
                "local_repair_full_success": False,
            },
            "model_usage": {
                "totals": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "cost": 0.1,
                }
            },
        }
        result = summarize_payload(payload, "result.json")
        self.assertEqual(result["status"], "unrepaired_failure")
        self.assertTrue(result["valid_strict_replay"])
        self.assertEqual(result["strict_replay"]["artifact_hash_count"], 1)
        self.assertTrue(result["strict_replay"]["sandbox_identity_matches"])
        self.assertEqual(result["crs"]["branches"], 2)
        self.assertEqual(result["crs"]["interventions_attempted"], 2)
        self.assertEqual(result["crs"]["candidate_or_policy_failures"], 0)
        self.assertEqual(result["causal_outcome_mode"], "full-success")
        self.assertEqual(result["crs"]["branches_with_same_reward"], 2)
        self.assertEqual(result["crs"]["branches_with_higher_reward"], 0)
        self.assertEqual(result["crs"]["branches_with_lower_reward"], 0)
        self.assertEqual(result["crs"]["full_trace_branches"], 2)
        self.assertEqual(result["crs"]["mean_replay_ratio"], 1.0)
        self.assertEqual(result["crs_model_usage"]["total_tokens"], 12)

    def test_full_result_summary_rejects_failed_strict_replay(self):
        result = summarize_payload(
            {
                "task": "invalid",
                "baseline_official_reward": 1.0,
                "strict_baseline_replay_matches": False,
            }
        )
        self.assertEqual(result["status"], "invalid_strict_replay")
        self.assertFalse(result["valid_strict_replay"])

    def test_full_result_summary_rejects_legacy_root_replay_without_identity(self):
        result = summarize_payload(
            {
                "task": "legacy-root",
                "baseline_official_reward": 1.0,
                "strict_baseline_replay_matches": True,
            }
        )
        self.assertEqual(result["status"], "invalid_strict_replay")
        self.assertFalse(result["valid_strict_replay"])


if __name__ == "__main__":
    unittest.main()
