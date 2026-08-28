from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from benchflow.agents import openhands_benchmark_adapter as adapter
from benchflow.benchmark_executor import build_skill_bundle_manifest


def _adapter_env(root: Path) -> dict[str, str]:
    manifest = build_skill_bundle_manifest(root)
    return {
        adapter.ENV_MAX_ITERATIONS: "60",
        adapter.ENV_DISABLE_SUBAGENTS: "1",
        adapter.ENV_SKILLS_ROOT: str(root),
        adapter.ENV_SKILLS_SHA256: manifest.sha256,
        adapter.ENV_SKILL_COUNT: str(manifest.skill_count),
        adapter.ENV_BUNDLE_FILE_COUNT: str(manifest.file_count),
    }


def test_render_preload_contains_complete_bodies_in_path_order(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: all SKILL.md bodies preload stably."""
    (tmp_path / "z").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "z" / "SKILL.md").write_text("Z-BODY\n")
    (tmp_path / "a" / "SKILL.md").write_text("A-BODY\n")
    (tmp_path / "z" / "script.py").write_text("print(1)\n")

    rendered = adapter.render_preloaded_skill_context(_adapter_env(tmp_path))

    assert rendered is not None
    assert rendered.startswith(adapter.PRELOAD_START)
    assert rendered.endswith(adapter.PRELOAD_END)
    assert rendered.index('path="a/SKILL.md"') < rendered.index('path="z/SKILL.md"')
    assert "A-BODY" in rendered and "Z-BODY" in rendered
    assert "do not require invoke_skill" in rendered


def test_render_preload_fails_closed_on_digest_mismatch(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44 against deployed bundle drift."""
    (tmp_path / "one").mkdir()
    skill = tmp_path / "one" / "SKILL.md"
    skill.write_text("before")
    env = _adapter_env(tmp_path)
    skill.write_text("after")

    with pytest.raises(RuntimeError, match="digest mismatch"):
        adapter.render_preloaded_skill_context(env)


class _Context:
    def __init__(self, suffix: str | None = None):
        self.system_message_suffix = suffix

    def model_copy(self, *, update: dict):
        return _Context(update["system_message_suffix"])


class _Agent:
    def __init__(
        self,
        context: _Context | None = None,
        tools: list[SimpleNamespace] | None = None,
    ):
        self.agent_context = context
        self.tools = list(tools or [])
        self._runtime_tools = None

    def model_copy(self, *, update: dict):
        return _Agent(
            update.get("agent_context", self.agent_context),
            update.get("tools", self.tools),
        )

    def step(self, conversation, *args, **kwargs):
        del conversation, args, kwargs

    def _initialize(self, state):
        del state
        resolved = {}
        for tool in self.tools:
            runtime_name = "task" if tool.name == "task_tool_set" else tool.name
            resolved[runtime_name] = SimpleNamespace(name=runtime_name)
        self._runtime_tools = resolved

    @property
    def tools_map(self):
        if self._runtime_tools is None:
            raise RuntimeError("agent is not initialized")
        return self._runtime_tools


class _Response:
    def __init__(self, stop_reason: str, field_meta: dict | None = None, **kwargs):
        del kwargs
        self.stop_reason = stop_reason
        self.field_meta = field_meta

    def model_copy(self, *, update: dict):
        return _Response(
            update.get("stop_reason", self.stop_reason),
            update.get("field_meta", self.field_meta),
        )


def _install_fake_openhands(monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, type]:
    context_module = ModuleType("openhands.sdk.context")
    context_module.AgentContext = _Context
    monkeypatch.setitem(sys.modules, "openhands", ModuleType("openhands"))
    monkeypatch.setitem(sys.modules, "openhands.sdk", ModuleType("openhands.sdk"))
    monkeypatch.setitem(sys.modules, "openhands.sdk.context", context_module)

    local_agent = ModuleType("openhands_cli.acp_impl.agent.local_agent")

    class Conversation:
        def __init__(self, *, agent, **kwargs):
            self.agent = agent
            self.kwargs = kwargs
            self.state = SimpleNamespace(events=[])

    local_agent.Conversation = Conversation

    base_agent = ModuleType("openhands_cli.acp_impl.agent.base_agent")

    class BaseOpenHandsACPAgent:
        async def prompt(self, prompt, session_id, **kwargs):
            del prompt, kwargs
            conversation = self.active_sessions[session_id]
            for _ in range(self.iterations):
                conversation.agent.step(conversation)
            if self.emit_limit:
                conversation.state.events.append(
                    SimpleNamespace(code="MaxIterationsReached")
                )
            return _Response("end_turn")

    base_agent.BaseOpenHandsACPAgent = BaseOpenHandsACPAgent
    base_agent.PromptResponse = _Response

    agent_package = ModuleType("openhands_cli.acp_impl.agent")
    agent_package.base_agent = base_agent
    agent_package.local_agent = local_agent
    monkeypatch.setitem(sys.modules, "openhands_cli", ModuleType("openhands_cli"))
    monkeypatch.setitem(
        sys.modules, "openhands_cli.acp_impl", ModuleType("openhands_cli.acp_impl")
    )
    monkeypatch.setitem(sys.modules, "openhands_cli.acp_impl.agent", agent_package)
    monkeypatch.setitem(
        sys.modules, "openhands_cli.acp_impl.agent.base_agent", base_agent
    )
    monkeypatch.setitem(
        sys.modules, "openhands_cli.acp_impl.agent.local_agent", local_agent
    )
    return local_agent, BaseOpenHandsACPAgent


@pytest.mark.asyncio
async def test_adapter_preloads_before_conversation_and_caps_each_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: preload precedes the N=60 run."""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "SKILL.md").write_text("FULL SKILL BODY")
    env = _adapter_env(tmp_path)
    local_agent, base_cls = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)

    adapter.install_adapter(env)
    conversation = local_agent.Conversation(
        agent=_Agent(
            _Context("existing context"),
            [
                SimpleNamespace(name="terminal"),
                SimpleNamespace(name="task_tool_set"),
                SimpleNamespace(name="delegate"),
            ],
        ),
        workspace="/app",
    )

    assert conversation.kwargs["max_iteration_per_run"] == 60
    assert [tool.name for tool in conversation.agent.tools] == ["terminal"]
    suffix = conversation.agent.agent_context.system_message_suffix
    assert suffix.startswith("existing context\n\n")
    assert "FULL SKILL BODY" in suffix

    instance = base_cls()
    instance.iterations = 60
    instance.emit_limit = True
    instance.active_sessions = {"s": conversation}
    response = await instance.prompt([], "s")
    assert response.stop_reason == "max_turn_requests"
    assert response.field_meta["benchmark_executor"] == {
        "stop_reason": "max_iterations",
        "acp_stop_reason": "max_turn_requests",
        "execution_status": None,
        "error_code": "MaxIterationsReached",
        "iterations_used": 60,
        "max_iterations": 60,
        "skill_context_preloaded": True,
        "skill_bundle_sha256": f"sha256:{env[adapter.ENV_SKILLS_SHA256]}",
        "preloaded_skill_count": 1,
    }


@pytest.mark.asyncio
async def test_exactly_sixty_finished_steps_remain_end_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: success on iteration 60 is success."""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "SKILL.md").write_text("BODY")
    local_agent, base_cls = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    env = _adapter_env(tmp_path)
    adapter.install_adapter(env)
    conversation = local_agent.Conversation(agent=_Agent(), workspace="/app")
    instance = base_cls()
    instance.iterations = 60
    instance.emit_limit = False
    instance.active_sessions = {"s": conversation}

    response = await instance.prompt([], "s")

    assert response.stop_reason == "end_turn"
    assert response.field_meta["benchmark_executor"] == {
        "stop_reason": "end_turn",
        "acp_stop_reason": "end_turn",
        "execution_status": None,
        "error_code": None,
        "iterations_used": 60,
        "max_iterations": 60,
        "skill_context_preloaded": True,
        "skill_bundle_sha256": f"sha256:{env[adapter.ENV_SKILLS_SHA256]}",
        "preloaded_skill_count": 1,
    }


@pytest.mark.asyncio
async def test_each_prompt_gets_an_independent_iteration_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: each BenchFlow Step resets N."""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "SKILL.md").write_text("BODY")
    local_agent, base_cls = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter(_adapter_env(tmp_path))
    conversation = local_agent.Conversation(agent=_Agent(), workspace="/app")
    instance = base_cls()
    instance.emit_limit = False
    instance.active_sessions = {"s": conversation}

    instance.iterations = 2
    first = await instance.prompt([], "s")
    instance.iterations = 4
    second = await instance.prompt([], "s")

    assert first.field_meta["benchmark_executor"]["iterations_used"] == 2
    assert second.field_meta["benchmark_executor"]["iterations_used"] == 4
    assert conversation._benchmark_executor_total_iterations == 6


def test_subagent_step_does_not_increment_root_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: only root iterations are counted."""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "SKILL.md").write_text("BODY")
    local_agent, _ = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter(_adapter_env(tmp_path))
    root = local_agent.Conversation(agent=_Agent(), workspace="/app")
    subagent = SimpleNamespace(
        agent=root.agent,
        _benchmark_executor_root=False,
        _benchmark_executor_total_iterations=0,
    )

    root.agent.step(subagent)

    assert root._benchmark_executor_total_iterations == 0
    assert subagent._benchmark_executor_total_iterations == 0


@pytest.mark.asyncio
async def test_no_skill_run_has_no_preload_but_keeps_iteration_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-skill keeps an empty context while still disabling delegation."""
    local_agent, base_cls = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter(
        {
            adapter.ENV_MAX_ITERATIONS: "60",
            adapter.ENV_DISABLE_SUBAGENTS: "1",
        }
    )
    conversation = local_agent.Conversation(
        agent=_Agent(
            tools=[
                SimpleNamespace(name="terminal"),
                SimpleNamespace(name="task_tool_set"),
            ]
        ),
        workspace="/app",
    )
    instance = base_cls()
    instance.iterations = 1
    instance.emit_limit = False
    instance.active_sessions = {"s": conversation}

    response = await instance.prompt(["original task"], "s")

    assert conversation.agent.agent_context is None
    assert [tool.name for tool in conversation.agent.tools] == ["terminal"]
    assert conversation.kwargs["max_iteration_per_run"] == 60
    outcome = response.field_meta["benchmark_executor"]
    assert outcome["skill_context_preloaded"] is False
    assert outcome["skill_bundle_sha256"] is None
    assert outcome["preloaded_skill_count"] == 0


def test_adapter_preserves_delegation_tools_without_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_agent, _ = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter({adapter.ENV_MAX_ITERATIONS: "60"})

    conversation = local_agent.Conversation(
        agent=_Agent(tools=[SimpleNamespace(name="task_tool_set")]),
        workspace="/app",
    )

    assert [tool.name for tool in conversation.agent.tools] == ["task_tool_set"]


def test_delegation_filter_fails_closed_on_malformed_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_agent, _ = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter(
        {
            adapter.ENV_MAX_ITERATIONS: "60",
            adapter.ENV_DISABLE_SUBAGENTS: "1",
        }
    )

    with pytest.raises(RuntimeError, match="tool without a string name"):
        local_agent.Conversation(
            agent=_Agent(tools=[SimpleNamespace()]),
            workspace="/app",
        )


def test_runtime_delegation_guard_fails_before_agent_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_agent, _ = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter(
        {
            adapter.ENV_MAX_ITERATIONS: "60",
            adapter.ENV_DISABLE_SUBAGENTS: "1",
        }
    )
    conversation = local_agent.Conversation(
        agent=_Agent(tools=[SimpleNamespace(name="terminal")]),
        workspace="/app",
    )
    conversation.agent.tools.append(SimpleNamespace(name="task_tool_set"))

    with pytest.raises(RuntimeError, match="after lazy resolution: task"):
        conversation.agent._initialize(conversation.state)


@pytest.mark.asyncio
async def test_stuck_status_is_not_reported_as_normal_end_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: STUCK remains distinct from success."""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "SKILL.md").write_text("BODY")
    local_agent, base_cls = _install_fake_openhands(monkeypatch)
    monkeypatch.setattr(adapter, "_PATCHED", False)
    adapter.install_adapter(_adapter_env(tmp_path))
    conversation = local_agent.Conversation(agent=_Agent(), workspace="/app")
    conversation.state.execution_status = "stuck"
    instance = base_cls()
    instance.iterations = 5
    instance.emit_limit = False
    instance.active_sessions = {"s": conversation}

    response = await instance.prompt([], "s")

    outcome = response.field_meta["benchmark_executor"]
    assert response.stop_reason == "end_turn"
    assert outcome["stop_reason"] == "stuck"
    assert outcome["execution_status"] == "stuck"
