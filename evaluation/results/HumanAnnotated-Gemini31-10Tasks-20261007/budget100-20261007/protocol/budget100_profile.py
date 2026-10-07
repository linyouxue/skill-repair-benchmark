"""User-authorized parent-100 extension, confined to this worker process.

The shared skillrepair-v1 policy and historical 60-parent results stay intact.
All three budget consumers (env, ACP accounting, normalized result validation)
must agree. An explicit derived protocol ID prevents claiming the 60 protocol.
"""
from __future__ import annotations

PROTOCOL_ID = 'skillrepair-v1-gemini-parent100'
PARENT_LIMIT = 100


def install():
    import benchflow.benchmark_executor as policy
    import benchflow.acp.runtime as acp
    import benchmark_executor.executor as executor
    import benchmark_executor.result as result

    assert policy.EXECUTOR_PROTOCOL_ID == executor.EXECUTOR_PROTOCOL_ID == 'skillrepair-v1'
    assert policy.MAX_PARENT_ITERATIONS_PER_STEP == acp.MAX_PARENT_ITERATIONS_PER_STEP == result.MAX_PARENT_ITERATIONS_PER_STEP == 60
    policy.MAX_PARENT_ITERATIONS_PER_STEP = PARENT_LIMIT
    acp.MAX_PARENT_ITERATIONS_PER_STEP = PARENT_LIMIT
    result.MAX_PARENT_ITERATIONS_PER_STEP = PARENT_LIMIT
    policy.EXECUTOR_PROTOCOL_ID = PROTOCOL_ID
    executor.EXECUTOR_PROTOCOL_ID = PROTOCOL_ID
    return PROTOCOL_ID


if __name__ == '__main__':
    # Offline check only: no container, provider, or verifier invocation.
    import json
    install()
    import benchflow.benchmark_executor as policy
    env = policy.apply_openhands_executor_env('openhands', {}, skill_policy=None, manifest=None)
    assert env[policy.ENV_MAX_ITERATIONS] == '100'
    assert env[policy.ENV_TEXT_ONLY_RETRY_LIMIT] == '1'
    descriptor = policy.protocol_descriptor()
    assert descriptor['protocol_id'] == PROTOCOL_ID
    assert descriptor['max_parent_iterations_per_step'] == PARENT_LIMIT
    print(json.dumps({'protocol_id': PROTOCOL_ID, 'max_parent_iterations': PARENT_LIMIT,
                      'text_only_continuation_limit': 1, 'provider_calls': 0,
                      'shared_source_modified': False}))
