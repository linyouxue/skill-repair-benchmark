"""Guards JPG diagnosis PR #34 and local bridge against commit 64e7ca8.

All HTTP and OpenHands responses below are MOCK, never provider evidence.
"""
import asyncio
import base64
import importlib.util
import json
import os
import shutil
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"skillgrad"))
from jpg_adapter import (ExactFilePolicy, WireRecorder, audit_first_window,
    packet_to_runner_input, read_json, load_reader, sha, SKILLS)

PACKAGE = ROOT/"source/jpg-ocr-stat"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WireGuard(unittest.TestCase):
    def test_diagnosis_requires_22_distinct_images(self):
        from run_one_round import validated_image_count
        images = [{"type":"image_url", "image_url":{"url":f"data:image/jpeg;base64,{i}"}}
                  for i in range(22)]
        body = {"messages":[{"role":"system", "content":"Diagnose the failed original JPG task"},
                            {"role":"user", "content":images}]}
        self.assertEqual(validated_image_count(body), 22)
        with self.assertRaises(RuntimeError):
            validated_image_count({"messages":[body["messages"][0],
                                               {"role":"user", "content":[]}]})
        with self.assertRaises(RuntimeError):
            validated_image_count({"messages":[body["messages"][0],
                                               {"role":"user", "content":images[:-1]+images[:1]}]})
        with self.assertRaises(RuntimeError):
            validated_image_count({"messages":[{"role":"system", "content":"Patcher"},
                                               body["messages"][1]]})


class OfflineInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet, cls.audit = audit_first_window(PACKAGE)

    def test_real_22_jpeg_bytes_and_no_model_claim(self):
        self.assertEqual(len(self.audit["images"]), 22)
        self.assertEqual(self.audit["windows"], 37)
        self.assertEqual(self.audit["total_image_bytes"], 8261743)
        self.assertEqual(self.audit["model_calls"], 0)
        self.assertFalse(self.audit["actual_model_delivery_verified"])
        self.assertTrue(all(p.startswith(("diagnosis/", "environment/skills/", "environment/workspace/dataset/img/"))
                            for p in self.audit["source_files_read"]))

    def test_sdk_input_is_structured_not_stringified_base64(self):
        result = packet_to_runner_input(self.packet)
        blocks = result[0]["content"]
        self.assertEqual(blocks[0]["type"], "input_text")
        self.assertEqual(sum(b["type"] == "input_image" for b in blocks), 22)
        self.assertNotIn("data:image/jpeg;base64,", blocks[0]["text"])
        self.assertGreater(len(blocks[0]["text"]), 60000)
        self.assertNotIn('"ordinary_ctrf_tests"', blocks[0]["text"])
        self.assertNotIn('"ordinary_ctrf_summary"', blocks[0]["text"])
        self.assertNotIn('"ctrf_source"', blocks[0]["text"])
        self.assertNotIn('"scoring_source"', blocks[0]["text"])

    def test_reject_missing_image_or_wrong_run(self):
        from copy import deepcopy
        bad = deepcopy(self.packet); bad["messages"][0]["content"].pop()
        with self.assertRaises(ValueError):
            packet_to_runner_input(bad)
        bad = deepcopy(self.packet); bad["run_id"] = "200-receipt-extended"
        with self.assertRaises(ValueError):
            packet_to_runner_input(bad)

    def test_all_windows_are_loadable_without_raw_log_reparse(self):
        reader = load_reader(PACKAGE)
        index = read_json(PACKAGE/"diagnosis/index.json")
        spans = {}
        for row in index["windows"]:
            packet = reader.load_window(PACKAGE, row["window_id"])
            self.assertEqual(packet["prepared_image_ids"], self.packet["prepared_image_ids"])
            self.assertEqual(packet["model_calls"], 0)
            window = read_json(PACKAGE/row["path"])
            for item in window["items"]:
                spans.setdefault(item["record_id"], []).append((item["char_start"], item["char_end"]))
        table = reader._record_table(PACKAGE, index)
        self.assertEqual(set(spans), set(table))
        self.assertEqual(len(table), 380)
        for rid, intervals in spans.items():
            cursor = 0
            for start, end in sorted(intervals):
                self.assertEqual(start, cursor, rid)
                cursor = end
            self.assertEqual(cursor, len(reader._serial(table[rid]["record"])))
        from jpg_adapter import write_json
        write_json(ROOT/"evidence/window_coverage.json", {"windows":37, "prepared_records":380,
            "all_character_spans_contiguous":True, "no_gaps_or_overlaps":True,
            "source":"prepared diagnosis streams only; no raw logs reparsed",
            "coverage_kind":"OFFLINE_VALIDATED_NOT_MODEL_CONSUMED", "model_calls":0})

    def test_exact_stage_permissions_and_bundle_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            skills = root/"skills"
            shutil.copytree(PACKAGE/"environment/skills", skills)
            docs = [skills/n/"SKILL.md" for n in SKILLS]
            previous, diagnosis, overlay, memory = [root/n for n in ("previous.md", "diagnosis.md", "overlay.md", "memory.md")]
            for p in (previous, diagnosis, overlay, memory): p.write_text("SYNTHETIC", encoding="utf-8")
            files = [p for p in skills.rglob("*") if p.is_file()]
            m = ExactFilePolicy(root, files+[previous, diagnosis], [overlay, memory])
            p = ExactFilePolicy(root, files+[diagnosis, overlay, memory], docs)
            d = ExactFilePolicy(root, files)
            for policy in (m, p, d):
                for forbidden in (root/"oracle/solve.sh", PACKAGE/"verifier/stat_oracle.xlsx", root/"../outside"):
                    with self.assertRaises(PermissionError): policy.read(forbidden)
            with self.assertRaises(PermissionError): p.read(previous)
            with self.assertRaises(PermissionError): d.read(memory)
            with self.assertRaises(PermissionError): m.read(root/"trace.jsonl")
            support = next(f for f in files if f not in docs)
            with self.assertRaises(PermissionError): p.write(support, "BAD")
            with self.assertRaises(PermissionError): p.write(skills/"new/SKILL.md", "BAD")
            with self.assertRaises(PermissionError): m.write(docs[0], "BAD")
            p.write(docs[0], p.read(docs[0])+"\nSYNTHETIC_TEST_ONLY\n")
            self.assertEqual(load_reader(PACKAGE)._validate_bundle(PACKAGE/"environment/skills", skills), ["image-ocr/SKILL.md"])
            support.write_text("BAD", encoding="utf-8")
            with self.assertRaises(ValueError): load_reader(PACKAGE)._validate_bundle(PACKAGE/"environment/skills", skills)

    def test_all_five_skill_documents_are_listed_for_momentum_and_patcher(self):
        from pipeline.momentum import _list_skill_files as m
        from pipeline.patcher import _list_skill_files as p
        for fn in (m, p):
            docs = [Path(x).parent.name for x in fn(PACKAGE/"environment/skills") if Path(x).name == "SKILL.md"]
            self.assertEqual(set(docs), set(SKILLS))


class SDKTransport(unittest.IsolatedAsyncioTestCase):
    async def test_actual_diagnoser_sdk_serializes_22_images_to_mock_http(self):
        import httpx
        from openai import AsyncOpenAI
        from agents.tracing import set_tracing_disabled
        from pipeline.diagnoser import run_diagnose
        from runners.cost_tracker import CostTracker
        from runners import model_dispatch
        set_tracing_disabled(True)
        packet, audit = audit_first_window(PACKAGE)
        captured = []
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(body["model"], "gpt-5.2")
            content = [m["content"] for m in body["messages"] if m["role"] == "user"][0]
            text = next(b["text"] for b in content if b["type"] == "text")
            for field in ('"ordinary_ctrf_tests"', '"ordinary_ctrf_summary"', '"ctrf_source"', '"scoring_source"'):
                self.assertNotIn(field, text)
            images = [b for b in content if b["type"] == "image_url"]
            self.assertEqual(len(images), 22)
            for image, expected in zip(images, audit["images"]):
                raw = base64.b64decode(image["image_url"]["url"].split(",", 1)[1], validate=True)
                self.assertEqual(sha(raw), expected["sha256"])
            captured.append({"image_blocks": len(images), "model": body["model"], "url": str(request.url)})
            chunks = [
                {"id":"chatcmpl-MOCK","object":"chat.completion.chunk","created":0,"model":"gpt-5.2", "choices":[{"index":0,"delta":{"role":"assistant","content":"<diagnosis>MOCK_TRANSPORT_ONLY</diagnosis>"},"finish_reason":None}]},
                {"id":"chatcmpl-MOCK","object":"chat.completion.chunk","created":0,"model":"gpt-5.2", "choices":[{"index":0,"delta":{},"finish_reason":"stop"}]},
                {"id":"chatcmpl-MOCK","object":"chat.completion.chunk","created":0,"model":"gpt-5.2", "choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}},
            ]
            data = "".join("data: " + json.dumps(row) + "\n\n" for row in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, text=data, headers={"content-type":"text/event-stream", "x-request-id":"MOCK-REQUEST-001"})
        # Persist explicitly MOCK evidence, separate from any later paid smoke.
        output = ROOT/"evidence/mock_wire"
        if output.exists():
            # Test reruns use a new folder; never replace evidence.
            output = Path(tempfile.mkdtemp(prefix="mock-rerun-", dir=ROOT/"evidence"))/"wire"
        recorder = WireRecorder(output, mode="MOCK", secrets=("MOCK_SECRET",))
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler),
            event_hooks={"request":[recorder.on_request], "response":[recorder.on_response]})
        client = AsyncOpenAI(api_key="MOCK_SECRET", base_url="https://mock.invalid/v1", http_client=http, max_retries=0)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"TATU_API_KEY":"MOCK_SECRET", "TATU_BASE_URL":"https://mock.invalid/v1"}), \
             patch.object(model_dispatch, "_TATU_CLIENT", client), patch.object(model_dispatch, "_TATU_CHECKED", True), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
             patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            root = Path(tmp)
            result = await run_diagnose(assessment={"id":"mock-window"}, diagnosis_type="skillsbench_sanitized",
                iter_dir=root, skills_dir=PACKAGE/"environment/skills", base_trajectories_dir=root,
                model="gpt-5.2", project_root=root, semaphore=asyncio.Semaphore(1),
                cost_tracker=CostTracker("gpt-5.2"), system_prompt_override="Offline transport test.",
                input_messages=packet_to_runner_input(packet), allowed_root=root)
        await client.close()
        self.assertEqual(result["diagnosis"], "MOCK_TRANSPORT_ONLY")
        self.assertEqual(len(captured), 1)
        request = read_json(output/"request-001.json")
        response = read_json(output/"response-001.json")
        self.assertEqual(request["evidence_mode"], "MOCK")
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(request["body_sha256"], response["request_body_sha256"])
        self.assertNotIn("MOCK_SECRET", (output/"request-001.json").read_text(encoding="utf-8"))
        self.assertFalse(response["actual_model_delivery_verified"])
        from jpg_adapter import write_json
        write_json(ROOT/"evidence/mock_transport_latest.json", {"mode":"MOCK",
            "wire_directory":str(output), "image_blocks":22, "jpeg_bytes_verified":8261743,
            "native_ctrf_fields_absent":True, "request_response_hash_linked":True,
            "provider_delivery_verified":False, "provider_vision_verified":False})


class IterativeMechanism(unittest.IsolatedAsyncioTestCase):
    async def test_two_rounds_keep_dmp_execution_order_and_inherit_momentum(self):
        from agents.tool_context import ToolContext
        from jpg_adapter import run_repair, RUN_ID, write_json
        from pipeline.skillsbench_per_task import hash_tree, hash_file
        events, previous_records, manifests = [], [], []
        async def tool(fn, **kwargs):
            arguments = json.dumps(kwargs)
            context = ToolContext(context=None, tool_name=fn.name,
                tool_call_id="SYNTHETIC-TOOL", tool_arguments=arguments)
            return await fn.on_invoke_tool(context, arguments)
        async def diagnose(**kwargs):
            events.append("D")
            self.assertEqual(sum(b["type"] == "input_image" for b in kwargs["input_messages"][0]["content"]), 22)
            self.assertIn("Error:", await tool(kwargs["file_tools_override"][0], file_path=str(PACKAGE/"verifier/stat_oracle.xlsx")))
            self.assertEqual(len(kwargs["additional_tools"]), 1)
            return {"diagnosis":"SYNTHETIC_CAUSAL_DIAGNOSIS", "diagnosis_tag_present":True,
                    "id":kwargs["assessment"]["id"]}
        async def momentum(**kwargs):
            events.append("M")
            read, write = kwargs["file_tools_override"]
            previous_records.append(await tool(read, file_path=str(kwargs["previous_record_path"])))
            await tool(write, file_path=str(kwargs["record_output_path"]), content=f"SYNTHETIC_MEMORY_{kwargs['iter_num']}")
            await tool(write, file_path=str(kwargs["overlay_output_path"]), content="SYNTHETIC_OVERLAY")
        async def patcher(**kwargs):
            events.append("P")
            self.assertTrue(kwargs["skill_files_only"])
            read, write = kwargs["file_tools_override"]
            path = kwargs["skills_dir"]/"image-ocr/SKILL.md"
            body = await tool(read, file_path=str(path))
            self.assertNotIn("Error:", await tool(write, file_path=str(path), content=body+"\nSYNTHETIC_PATCH\n"))
            support = next(p for p in kwargs["skills_dir"].rglob("*") if p.is_file() and p.name != "SKILL.md")
            self.assertIn("Error:", await tool(write, file_path=str(support), content="BAD"))
            return "SYNTHETIC_PATCH_COMPLETE"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            fresh = tmp/"SYNTHETIC_FRESH_PACKAGE"
            shutil.copytree(PACKAGE/"diagnosis", fresh/"diagnosis")
            shutil.copytree(PACKAGE/"environment", fresh/"environment")
            fresh_run = RUN_ID.replace("r003", "s001")  # Same char length preserves window spans.
            for path in (fresh/"diagnosis").rglob("*"):
                if path.suffix in {".json", ".jsonl"}:
                    path.write_bytes(path.read_bytes().replace(RUN_ID.encode(), fresh_run.encode()))
            metadata_path = fresh/"diagnosis/outputs/execution_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["run_id"] = fresh_run
            metadata["source"] = {"repository_path": "synthetic/fresh_execution/result.json",
                                   "file": "result.json", "commit": "synthetic"}
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            evidence_dir = fresh/"fresh_execution"
            evidence_dir.mkdir()
            result_path = evidence_dir/"result.json"
            trajectory_path = evidence_dir/"trajectory.jsonl"
            result_path.write_text(json.dumps({"run_id":fresh_run,
                "result_class":"valid_failure", "effective_skill_hash":"PENDING"}), encoding="utf-8")
            trajectory_path.write_text(json.dumps({"run_id":fresh_run,
                "event":"synthetic_agent_step", "evidence_mode":"SYNTHETIC_TEST_ONLY"})+"\n", encoding="utf-8")
            index = read_json(fresh/"diagnosis/index.json")
            # A source ID can straddle a fragment boundary. Regenerate synthetic
            # fragment text from the altered prepared records, not substring
            # replacements in individual partial fragments.
            reader = load_reader(PACKAGE)
            table = reader._record_table(fresh, index)
            for row in index["windows"]:
                window = read_json(fresh/row["path"])
                for item in window["items"]:
                    serial = reader._serial(table[item["record_id"]]["record"])
                    self.assertEqual(len(serial), item["record_chars"])
                    item["text"] = serial[item["char_start"]:item["char_end"]]
                (fresh/row["path"]).write_bytes(json.dumps(window, ensure_ascii=False).encode("utf-8"))
            async def execute(plan):
                events.append("EXECUTE_MOCK")
                manifests.append(read_json(plan.round_dir/"round_input_manifest.json"))
                if plan.round_index == 1:
                    return {"result_class":"valid_pass", "evidence_mode":"SYNTHETIC_TEST_ONLY"}
                result_path.write_text(json.dumps({"run_id":fresh_run,
                    "result_class":"valid_failure", "effective_skill_hash":hash_tree(plan.next_skill_bundle)}),
                    encoding="utf-8")
                return {"result_class":"valid_failure", "package":str(fresh), "evidence_mode":"SYNTHETIC_TEST_ONLY",
                    "fresh_execution_binding": {"run_id":fresh_run, "effective_skill_hash":hash_tree(plan.next_skill_bundle),
                        "result_class":"valid_failure", "window_index_sha256":hash_file(fresh/"diagnosis/index.json"),
                        "fresh_execution_evidence":{
                            "result":{"path":"fresh_execution/result.json", "sha256":hash_file(result_path)},
                            "trajectory":{"path":"fresh_execution/trajectory.jsonl", "sha256":hash_file(trajectory_path)}},
                        "stream_sha256":{row["path"]:hash_file(fresh/row["path"]) for row in index["streams"]}}}
            with patch("pipeline.diagnoser.run_diagnose", diagnose), patch("pipeline.momentum.run_momentum", momentum), \
                 patch("pipeline.patcher.run_patch", patcher), \
                 patch.dict(os.environ, {"TATU_API_KEY":"SYNTHETIC_NOT_A_REAL_KEY", "TATU_BASE_URL":"https://maas.tatucloud.com/v1"}), \
                 patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN")):
                history = await run_repair(package=PACKAGE, repair_root=tmp/"repair",
                    current_skill_bundle=PACKAGE/"environment/skills", execute_and_prepare=execute)
        self.assertEqual(len(history), 2)
        self.assertEqual(events, ["D"]*37+["M", "P", "EXECUTE_MOCK"]+["D"]*37+["M", "P", "EXECUTE_MOCK"])
        self.assertIn("initial", previous_records[0])
        self.assertEqual(previous_records[1], "SYNTHETIC_MEMORY_0")
        self.assertEqual(manifests[0]["output_repaired_skill_bundle_hash"], manifests[1]["current_skill_bundle_hash"])
        self.assertEqual(manifests[0]["current_momentum_hash"], manifests[1]["previous_momentum_hash"])
        write_json(ROOT/"evidence/dmp_two_round_mock.json", {"evidence_mode":"SYNTHETIC_TEST_ONLY",
            "diagnosis_calls_per_round":37, "rounds":2, "stage_order_verified":True,
            "momentum_inheritance_verified":True, "skill_inheritance_verified":True,
            "support_write_denied":True, "model_calls":0, "formal_execution_started":False})

    async def test_lineage_rejects_wrong_skill_and_previous_momentum(self):
        from pipeline.skillsbench_per_task import RoundInputManifest, assert_round_lineage, LineageAssertionError, hash_tree, hash_file
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root/"skills"; skill.mkdir(); (skill/"SKILL.md").write_text("SYNTHETIC")
            momentum = root/"memory.md"; momentum.write_text("SYNTHETIC_MEMORY")
            values = {field:"synthetic" for field in RoundInputManifest.__dataclass_fields__}
            values.update(output_repaired_skill_bundle_hash=hash_tree(skill), current_momentum_hash=hash_file(momentum))
            previous = RoundInputManifest(**values)
            assert_round_lineage(previous=previous, current_skill_bundle=skill, previous_momentum_path=momentum)
            momentum.write_text("WRONG")
            with self.assertRaises(LineageAssertionError):
                assert_round_lineage(previous=previous, current_skill_bundle=skill, previous_momentum_path=momentum)
            momentum.write_text("SYNTHETIC_MEMORY"); (skill/"SKILL.md").write_text("WRONG")
            with self.assertRaises(LineageAssertionError):
                assert_round_lineage(previous=previous, current_skill_bundle=skill, previous_momentum_path=momentum)


class Executor65(unittest.IsolatedAsyncioTestCase):
    async def test_original60_and_isolated65_reach_real_adapter_hooks_with_mock_conversation(self):
        original = load_module("original_policy", ROOT/"source/src/benchflow/benchmark_executor.py")
        isolated = load_module("jpg65_policy", ROOT/"executor65/src/benchflow/benchmark_executor.py")
        self.assertEqual(original.MAX_PARENT_ITERATIONS_PER_STEP, 60)
        self.assertEqual(isolated.protocol_descriptor()["max_parent_iterations_per_step"], 65)
        env60 = original.apply_openhands_executor_env("openhands", {original.ENV_MAX_ITERATIONS:"65"}, skill_policy=None, manifest=None)
        env65 = isolated.apply_openhands_executor_env("openhands", {}, skill_policy=None, manifest=None)
        self.assertEqual(env60[original.ENV_MAX_ITERATIONS], "60")
        self.assertEqual(env65[isolated.ENV_MAX_ITERATIONS], "65")
        adapter = load_module("actual_openhands_adapter", ROOT/"executor65/src/benchflow/agents/openhands_benchmark_adapter.py")
        class Agent:
            tools = []
            tools_map = {}
            def model_copy(self, update): return self
            def _initialize(self): return None
            def step(self, conversation): return None
            def _handle_content_response(self, *args): return None
        class Conversation:
            def __init__(self, agent, max_iteration_per_run):
                self.agent, self.limit = agent, max_iteration_per_run
                self.state = types.SimpleNamespace(events=[], execution_status="running")
        class Result:
            stop_reason = "end_turn"
            field_meta = {}
            def model_copy(self, update):
                result = Result()
                for key, value in update.items(): setattr(result, key, value)
                return result
        class Base:
            def __init__(self, conversation): self.active_sessions = {"root":conversation}
            async def prompt(self, prompt, session_id, **kwargs):
                c = self.active_sessions[session_id]
                for _ in range(c.limit-2): c.agent.step(c)
                c.state.execution_status = "finished"
                c.agent._handle_content_response(None, None, c, c.state, c.state.events.append)
                self.assert_guard_was_running = c.state.execution_status
                for _ in range(2): c.agent.step(c)
                # Non-root/subagent steps are not part of this root budget.
                child = types.SimpleNamespace(_benchmark_executor_root=False, agent=c.agent)
                for _ in range(7): c.agent.step(child)
                c.state.events.append(types.SimpleNamespace(code="MaxIterationsReached"))
                return Result()
        mock_modules = {"openhands_cli.acp_impl.agent": types.SimpleNamespace(
            local_agent=types.SimpleNamespace(Conversation=Conversation),
            base_agent=types.SimpleNamespace(BaseOpenHandsACPAgent=Base)),
            "openhands.sdk.conversation.state":types.SimpleNamespace(ConversationExecutionStatus=types.SimpleNamespace(RUNNING="running")),
            "openhands.sdk.event":types.SimpleNamespace(MessageEvent=lambda **kwargs:types.SimpleNamespace(**kwargs)),
            "openhands.sdk.llm":types.SimpleNamespace(Message=lambda **kwargs:kwargs, TextContent=lambda **kwargs:kwargs)}
        with patch.dict(sys.modules, mock_modules):
            adapter.install_adapter(env65)
            namespace = mock_modules["openhands_cli.acp_impl.agent"]
            c = namespace.local_agent.Conversation(agent=Agent())
            response = await Base(c).prompt([], "root")
        meta = response.field_meta["benchmark_executor"]
        self.assertEqual(c.limit, 65)
        self.assertEqual(meta["max_iterations"], 65)
        self.assertEqual(meta["iterations_used"], 65)
        self.assertEqual(meta["stop_reason"], "max_iterations")
        self.assertEqual(meta["experimental_text_only_retries_used"], 1)
        self.assertEqual(c.state.execution_status, "running")
        self.assertEqual(original.MAX_PARENT_ITERATIONS_PER_STEP, 60)
        from jpg_adapter import write_json
        write_json(ROOT/"evidence/executor65_mock_runtime.json", {
            "evidence_mode":"REAL_ADAPTER_MOCK_OPENHANDS_CLASSES", "upstream":60,
            "isolated_protocol":isolated.EXECUTOR_PROTOCOL_ID, "prompt_metadata":meta,
            "real_openhands_session_verified":False, "formal_execution_started":False})


if __name__ == "__main__":
    unittest.main(verbosity=2)
