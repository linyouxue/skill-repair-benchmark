"""Resume the retained JPG conversation within its original 65 parent steps."""
import json
import os
from pathlib import Path


def install_resume():
    from openhands_cli.acp_impl.agent import base_agent
    expected_id = os.environ['BENCHFLOW_RECOVERY_SESSION_ID']
    expected_events = int(os.environ['BENCHFLOW_RECOVERY_EVENT_COUNT'])
    prior = int(os.environ['BENCHFLOW_RECOVERY_PRIOR_ITERATIONS'])
    remaining = int(os.environ['BENCHMARK_EXECUTOR_MAX_ITERATIONS'])
    if prior + remaining != 65:
        raise RuntimeError('JPG continuation must share the original 65-step budget')

    async def checkpoint_prompt(agent, prompt, session_id, **kwargs):
        if session_id.replace('-', '') != expected_id.replace('-', ''):
            raise RuntimeError('JPG checkpoint session mismatch')
        conversation = await agent._get_or_create_conversation(session_id=session_id)
        if len(conversation.state.events) != expected_events or conversation.max_iteration_per_run != remaining:
            raise RuntimeError('JPG checkpoint changed or remaining budget was not applied')
        cls = type(conversation.agent)
        original = cls.step

        def step(inner, current, *args, **kwargs):
            if current is conversation:
                started = getattr(current, '_benchmark_executor_total_iterations', 0) + 1
                total = prior + started
                if total > 65:
                    raise RuntimeError('JPG total parent budget exhausted')
                target = Path('/logs/agent/jpg-checkpoint-parent-counter.json')
                temporary = target.with_suffix('.tmp')
                temporary.write_text(json.dumps({'total_started': total, 'prior': prior,
                    'segment_started': started, 'session_id': str(current.state.id)}))
                temporary.replace(target)
            return original(inner, current, *args, **kwargs)

        cls.step = step
        # Resume natively, without adding another task or user message.
        await base_agent.run_conversation_with_confirmation(conversation=conversation,
            conn=agent._conn, session_id=session_id)
        return base_agent.PromptResponse(stop_reason='end_turn')

    base_agent.BaseOpenHandsACPAgent.prompt = checkpoint_prompt
