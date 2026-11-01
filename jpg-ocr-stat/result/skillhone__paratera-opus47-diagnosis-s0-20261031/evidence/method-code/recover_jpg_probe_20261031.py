"""Continue the real retained round-1 task after WSL shutdown, not a new rollout."""
import asyncio
import inspect
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

import adapter

ROOT = Path('/home/linyuanjing/jpg-skillhone-diagnosis-s0-20261031')
HERE = Path(__file__).resolve().parent
CONTAINER = 'f1145bf236a1'
SESSION = '77e63f79ee6e4362b41f66f4fdeabbc7'
SOURCE = 'jpg-ocr-stat-probe-0-0-4fec25956e'


def checkpoint():
    data = subprocess.check_output(['docker', 'cp', f'{CONTAINER}:/home/agent/.openhands/conversations', '-'])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        events = [json.load(archive.extractfile(m)) for m in archive.getmembers()
                  if f'/{SESSION}/events/event-' in m.name and m.isfile()]
        state = json.load(archive.extractfile(f'conversations/{SESSION}/base_state.json'))
    if str(state['id']).replace('-', '') != SESSION:
        raise ValueError('Retained conversation differs from original probe')
    responses = len({e['llm_response_id'] for e in events if e.get('llm_response_id')})
    errors = sum(e.get('kind') == 'ConversationErrorEvent' for e in events)
    guards = sum(e.get('kind') == 'MessageEvent' and e.get('source') == 'environment'
        and e.get('llm_message', {}).get('role') == 'user'
        and '[Benchmark executor text-only guard]' in json.dumps(e) for e in events)
    source = next((ROOT/'state/projects').glob(f'*/benchmark/results/*-rollouts/jobs/skillhone/{SOURCE}'))
    # Serialization starts immediately before the actual request. Preserve the
    # interrupted request in the budget, rather than counting only responses.
    serializations = len((source/'agent/jpg-vision-audit.jsonl').read_text().splitlines())
    counter_file = source/'agent/jpg-checkpoint-parent-counter.json'
    counter = adapter.read_json(counter_file) if counter_file.exists() else {}
    used = max(responses + errors, serializations, int(counter.get('total_started', 0)))
    if not 0 < used < 65 or guards > 1:
        raise ValueError('Inspect exhausted or inconsistent original JPG budget')
    return {'session': SESSION, 'event_count': len(events), 'successful_parent_responses': responses,
        'prior_parent_iterations': used, 'serialized_requests_before_shutdown': serializations,
        'guard_used': guards, 'source_run': str(source), 'remaining': 65-used}


def main():
    if (ROOT/'recovered-probe.json').exists():
        raise RuntimeError('Recovery already scored; do not regenerate')
    metadata = checkpoint()
    sys.path.insert(0, str(ROOT/'eval'))
    executor_root = Path(adapter.read_json(ROOT/'eval/campaign.json')['executor_root'])
    sys.path.insert(0, str(executor_root/'src'))
    os.chdir(executor_root)
    adapter.activate_worker_budget({'task_id': 'jpg-ocr-stat', 'task_dir': str(ROOT/'eval/tasks/probe/jpg-ocr-stat'),
        'parent_iterations': 65, 'execution_budget_scope': 'jpg-isolated-worker-65'})
    from benchflow.acp import runtime
    native_signature = inspect.signature(runtime.connect_acp)
    from jpg_runtime_20261030 import setup_worker
    setup_worker()
    from benchflow.acp.client import ACPClient
    from benchflow.acp import runtime
    import benchflow.rollout_planes as planes
    from benchflow.sandbox.docker import DockerSandbox
    import benchflow.agents.install as installation
    from benchflow.agents import openhands_runtime_cache as cache
    from benchmark_executor import BenchmarkExecutor

    remaining = metadata['remaining']
    runtime.MAX_PARENT_ITERATIONS_PER_STEP = remaining

    async def retained_runtime(sandbox):
        code = ('from pathlib import Path; from importlib.metadata import version; '
            f'assert Path({cache.OPENHANDS_RUNTIME_MARKER!r}).read_text().strip()=={cache.expected_runtime_marker()!r}; '
            "assert version('openhands-sdk')=='1.28.1'; assert version('openhands-tools')=='1.28.1'")
        checked = await sandbox.exec('/opt/benchflow/uv-tools/openhands/bin/python -c '+shlex.quote(code), user='root', timeout_sec=20)
        if checked.return_code: raise RuntimeError('Retained runtime identity differs')
        return {'mode': 'retained-pinned-runtime',
            'archive': Path(os.environ['BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE']).name}

    installation.prepare_openhands_runtime_cache = retained_runtime

    async def retained_start(sandbox, force_build):
        sandbox.session_id = SOURCE
        subprocess.run(['docker', 'start', CONTAINER], check=True, stdout=subprocess.DEVNULL)
        check = await sandbox.exec(f'test -f /home/agent/.openhands/conversations/{SESSION}/base_state.json', user='root', timeout_sec=10)
        if check.return_code: raise RuntimeError('Original JPG checkpoint is missing')
        # A stopped container's artifact export may leave this bound scalar log
        # owned by root. Restore its existing native agent writer only.
        writable = await sandbox.exec('chown agent /logs/agent/jpg-vision-audit.jsonl', user='root', timeout_sec=10)
        if writable.return_code: raise RuntimeError('Cannot restore native JPG audit writer ownership')
        proxy = await sandbox.exec("python3 -c \"import socket; s=socket.create_connection(('host.docker.internal',7890),timeout=5);s.close()\"", user='root', timeout_sec=10)
        if proxy.return_code: raise RuntimeError('Retained JPG verifier proxy is unreachable')
        adapter.write_json(ROOT/'recovery-proxy-preflight.json', {'container': CONTAINER,
            'proxy_tcp_preflight': True, 'phase': 'retained-start-before-agent'})

    DockerSandbox.start = retained_start
    DockerSandbox.is_mounted = property(lambda sandbox: False)

    async def load_original(client, cwd='/app', mcp_servers=None):
        return await client.session_load(SESSION, cwd=cwd, mcp_servers=mcp_servers)

    ACPClient.session_new = load_original
    original_connect = runtime.connect_acp

    async def connect(*args, **kwargs):
        bound = native_signature.bind(*args, **kwargs)
        sandbox = bound.arguments['env']
        await sandbox.upload_file(HERE/'openhands_jpg_checkpoint_hook_20261031.py', '/opt/benchflow/bin/openhands_jpg_checkpoint_hook_20261031.py')
        code = ("from pathlib import Path; p=Path('/opt/benchflow/bin/openhands-benchmark-executor'); s=p.read_text(); "
            "s=s.replace('    from openhands_jpg_vision_hook import install'+chr(10)+'    install()'+chr(10),''); "
            "old='    install_adapter()'+chr(10); assert s.count(old)==1; "
            "new='    from openhands_jpg_checkpoint_hook_20261031 import install_resume'+chr(10)+'    install_resume()'+chr(10)+old; "
            "p.write_text(s if 'from openhands_jpg_checkpoint_hook_20261031 import install_resume' in s else s.replace(old,new,1))")
        patched = await sandbox.exec('python3 -c '+shlex.quote(code), user='root', timeout_sec=15)
        if patched.return_code: raise RuntimeError('Could not install JPG continuation hook')
        env = dict(bound.arguments['agent_env'])
        env.update(BENCHFLOW_RECOVERY_SESSION_ID=SESSION,
            BENCHFLOW_RECOVERY_EVENT_COUNT=str(metadata['event_count']),
            BENCHFLOW_RECOVERY_PRIOR_ITERATIONS=str(metadata['prior_parent_iterations']),
            BENCHMARK_EXECUTOR_MAX_ITERATIONS=str(remaining),
            BENCHFLOW_OPENHANDS_TEXT_ONLY_RETRY_LIMIT=str(1-metadata['guard_used']))
        bound.arguments['agent_env'] = env
        return await original_connect(**bound.arguments)

    runtime.connect_acp = planes.connect_acp = connect
    adapter.write_json(ROOT/'probe-recovery-metadata.json', dict(metadata, parent_budget=65,
        prior_plus_remaining=metadata['prior_parent_iterations']+remaining, injected_user_messages=0,
        recovery_pid=os.getpid(), original_candidate_commit='cefb35d9a1adc54ff956c83c7f4406e85947264f'))
    executor = BenchmarkExecutor(tasks_root=ROOT/'eval/tasks/probe', jobs_root=ROOT/'probe-recovery',
        model='paratera/Claude-Opus-4.7', reasoning_effort=None, experimental_text_only_retry_limit=1)
    sequence = 1
    while (ROOT/'probe-recovery/skillhone'/f'{SOURCE}-checkpoint-{sequence:02d}').exists():
        sequence += 1
    result = executor.run(task_id='jpg-ocr-stat', condition='method-skill', skill_bundle=ROOT/'skill/skills',
        method_id='skillhone', stage='round-1-native-checkpoint', rollout_id=f'{SOURCE}-checkpoint-{sequence:02d}')
    row = {'reward': result.reward, 'passed': result.task_passed is True, 'execution_ok': result.execution_ok,
        'result_json': str(result.artifacts.result_json), 'prior_parent_iterations': metadata['prior_parent_iterations'],
        'continuation_parent_iterations': result.agent_iterations, 'parent_budget': 65,
        'n_skill_invocations': result.skill_exposure.native_skill_invocations,
        'skill_preload_verified': result.skill_exposure.verified, 'cost_usd': result.cost_usd}
    adapter.write_json(ROOT/'probe-recovery-result.json', row)
    adapter.write_json(Path(result.artifacts.result_json).parent/'checkpoint-recovery.json', dict(metadata, result=row))
    if not result.execution_ok or result.reward is None:
        raise RuntimeError('Continuation needs infrastructure inspection; do not blindly rerun')
    adapter.write_json(ROOT/'recovered-probe.json', {'id': 'round-1-recovered-probe', 'score': result.reward,
        'n_total': 1, 'n_passed': int(result.task_passed is True), 'traces': [row],
        'source_kind': 'real_native_checkpoint_recovery', 'source_result': row['result_json']})
    node = HERE/'.runtime/node-v24.19.0-linux-x64/bin/node'
    with (ROOT/'resumed-controller.log').open('w') as log:
        child = subprocess.Popen([str(node), '--disable-warning=ExperimentalWarning',
            str(HERE/'jpg_diagnosis_iterations_20261031.mjs'), str(HERE/'SkillHone'), str(ROOT), '--resume-probe'],
            cwd=ROOT, env=os.environ, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    adapter.write_json(ROOT/'resumed-controller-launch.json', {'pid': child.pid,
        'source': str(ROOT/'recovered-probe.json'), 'repaired_skill_regenerated': False})
    print(json.dumps({'recovery_scored': True, 'reward': result.reward, 'remaining_at_start': remaining}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        state = adapter.read_json(ROOT/'campaign-state.json')
        state.update(status='needs-infrastructure-recovery', error_type=type(error).__name__,
            error_message=str(error), recovery_pid=os.getpid())
        adapter.write_json(ROOT/'campaign-state.json', state)
        raise
