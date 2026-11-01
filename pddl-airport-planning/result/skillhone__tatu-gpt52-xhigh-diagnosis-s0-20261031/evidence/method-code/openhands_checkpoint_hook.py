"""Continue an existing native conversation without appending another user prompt."""
import os
import json
from pathlib import Path


def persist_iteration_counter(conversation, prior):
    target = conversation
    agent_class = type(conversation.agent)
    original_step = agent_class.step

    def recorded_step(agent, conversation, *args, **kwargs):
        if conversation is target:
            segment = getattr(conversation, "_benchmark_executor_total_iterations", 0) + 1
            total = prior + segment
            if total > 60:
                raise RuntimeError("Resumed parent budget is exhausted")
            path = Path("/logs/agent/checkpoint-parent-counter.json")
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"session_id":str(conversation.state.id),
                "prior_iterations":prior,"segment_iterations_started":segment,
                "total_started":total}))
            temporary.replace(path)
        return original_step(agent, conversation, *args, **kwargs)

    agent_class.step = recorded_step


async def resume_existing(agent, session_id, *, expected_id, expected_events,
                          remaining, runner, response_factory):
    if session_id.replace("-", "") != expected_id.replace("-", ""):
        raise RuntimeError("Checkpoint session identity mismatch")
    conversation = await agent._get_or_create_conversation(session_id=session_id)
    if len(conversation.state.events) != expected_events:
        raise RuntimeError("Checkpoint event count changed before continuation")
    if conversation.max_iteration_per_run != remaining:
        raise RuntimeError("Continuation does not use the remaining parent budget")
    # The SDK natively resumes ERROR -> RUNNING. Do not call send_message():
    # the original task and all observations are already in the checkpoint.
    await runner(conversation=conversation, conn=agent._conn, session_id=session_id)
    return response_factory(stop_reason="end_turn")


def install_resume():
    from openhands_cli.acp_impl.agent import base_agent
    from openhands.sdk.llm import LLM

    original_responses = LLM.uses_responses_api

    def use_responses(llm):
        # Preserve the native Message/tool-call history directly on this
        # provider's declared Chat endpoint instead of converting it twice.
        if "gpt-5.2" in llm.model:
            return False
        return original_responses(llm)

    LLM.uses_responses_api = use_responses

    expected_id = os.environ["BENCHFLOW_RECOVERY_SESSION_ID"]
    expected_events = int(os.environ["BENCHFLOW_RECOVERY_EVENT_COUNT"])
    remaining = int(os.environ["BENCHMARK_EXECUTOR_MAX_ITERATIONS"])

    async def checkpoint_prompt(agent, prompt, session_id, **kwargs):
        conversation = await agent._get_or_create_conversation(session_id=session_id)
        persist_iteration_counter(conversation, int(os.environ["BENCHFLOW_RECOVERY_PRIOR_ITERATIONS"]))
        return await resume_existing(
            agent, session_id, expected_id=expected_id, expected_events=expected_events,
            remaining=remaining, runner=base_agent.run_conversation_with_confirmation,
            response_factory=base_agent.PromptResponse,
        )

    # Install before the official benchmark adapter so its iteration counting,
    # delegation guard and completion metadata still wrap this prompt method.
    base_agent.BaseOpenHandsACPAgent.prompt = checkpoint_prompt
