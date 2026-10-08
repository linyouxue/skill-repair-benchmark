"""Explicit followup budgets; shared policy and stuck detector stay intact."""
from __future__ import annotations


def install(parent_limit):
    assert parent_limit in {100, 200}
    import benchflow.benchmark_executor as policy
    import benchflow.acp.runtime as acp
    import benchmark_executor.executor as executor
    import benchmark_executor.result as result

    assert policy.EXECUTOR_PROTOCOL_ID == executor.EXECUTOR_PROTOCOL_ID == 'skillrepair-v1'
    assert policy.MAX_PARENT_ITERATIONS_PER_STEP == acp.MAX_PARENT_ITERATIONS_PER_STEP == result.MAX_PARENT_ITERATIONS_PER_STEP == 60
    protocol = f'skillrepair-v1-gemini-parent{parent_limit}'
    policy.MAX_PARENT_ITERATIONS_PER_STEP = parent_limit
    acp.MAX_PARENT_ITERATIONS_PER_STEP = parent_limit
    result.MAX_PARENT_ITERATIONS_PER_STEP = parent_limit
    policy.EXECUTOR_PROTOCOL_ID = executor.EXECUTOR_PROTOCOL_ID = protocol
    return protocol


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-parent-iterations', required=True, type=int, choices=[100, 200])
    args = parser.parse_args()
    protocol = install(args.max_parent_iterations)
    import benchflow.benchmark_executor as policy
    env = policy.apply_openhands_executor_env('openhands', {}, skill_policy=None, manifest=None)
    descriptor = policy.protocol_descriptor()
    assert env[policy.ENV_MAX_ITERATIONS] == str(args.max_parent_iterations)
    assert env[policy.ENV_TEXT_ONLY_RETRY_LIMIT] == '1'
    assert descriptor['protocol_id'] == protocol
    assert descriptor['max_parent_iterations_per_step'] == args.max_parent_iterations
    print(json.dumps({'protocol': protocol, 'parent_limit': args.max_parent_iterations,
                      'continuation_limit': 1, 'provider_calls': 0, 'shared_source_modified': False}))
