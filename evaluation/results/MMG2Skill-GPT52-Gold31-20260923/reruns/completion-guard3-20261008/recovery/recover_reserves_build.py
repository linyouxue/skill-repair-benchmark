"""One controlled pre-model dependency recovery; never rerun a completed slot."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import experiment as runner

ROOT = Path(__file__).resolve().parent
SLOT = 'skilltta__reserves-at-risk-calc'


def recover():
    assert not subprocess.check_output(['docker', 'ps', '-q'], text=True).strip()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parts = (entry / 'cmdline').read_bytes().split(b'\0')
            assert b'--worker' not in parts, 'Keep healthy workers; defer dependency recovery'
        except OSError:
            pass
    state = runner.read(ROOT / 'batch_state.json')
    assert state['status'] == 'blocked_incomplete_validation'
    saved = state['tasks'][SLOT]
    assert saved['phase'] == 'error' and saved['rollout'] == 'NOT_RUN'
    manifest = runner.read(ROOT / 'manifest.json')
    row = next(r for r in manifest['tasks'] if r['slot'] == SLOT)
    target = Path(row['rerun_root'])
    run = target / 'runs' / row['method_id'] / row['rollout_id']
    assert not run.exists(), 'No fresh/provider request may exist before this recovery'
    log = target / 'runtime-cache/reserves-at-risk-calc/build.log'
    raw = log.read_text()
    assert 'Running in 6c3f48b98ab5' in raw and 'Fetched 605 MB' in raw
    assert 'Unable to connect to host.docker.internal:7890' in raw
    container = json.loads(subprocess.check_output(['docker', 'inspect', '6c3f48b98ab5'], text=True))[0]
    assert not container['State']['Running'] and container['State']['ExitCode'] == 100
    assert container['Image'].startswith('sha256:d4a81e5ecf60')
    archive = ROOT / 'recovery-history/reserves-apt-proxy-drop-20261008'
    assert not archive.exists(), 'Recovery already attempted; inspect its real outcome before another attempt'
    archive.mkdir(parents=True)
    for name in ('batch_state.json', 'manifest.json', 'protocol.json', 'experiment.py', 'prebuild_skillsbench_task.py', 'runtime_fixes.py'):
        shutil.copyfile(ROOT / name, archive / name)
    shutil.copyfile(log, archive / 'reserves-build-r002.log')
    shutil.copyfile(ROOT / 'worker_logs' / f'{SLOT}.log', archive / 'worker.log')
    shutil.copyfile(target / 'task_state/reserves-at-risk-calc.json', archive / 'task_state.json')
    runner.write(archive / 'cause.json', {
        'at': runner.now(), 'cause': 'APT downloaded 605MB then existing host proxy connections dropped',
        'task_provider_requests': 0, 'fresh_started': False, 'failed_build_container': container['Id'],
        'remediation': 'Reuse downloaded Ubuntu packages; bounded APT retries/timeouts and disable HTTP pipelining in temporary build only',
        'proxy_address': 'existing host.docker.internal:7890 unchanged',
        'methods_inputs_pins_and_verifier': 'unchanged', 'completed_slots_preserved': 4,
    })
    cache = ROOT / 'runtime-cache/apt-reserves-at-risk-calc'
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(['docker', 'cp', f"{container['Id']}:/var/cache/apt/archives/.", str(cache)], check=True)
    packages = list(cache.glob('*.deb'))
    assert len(packages) > 500 and sum(p.stat().st_size for p in packages) > 500_000_000
    helper = runner.load('_guard3_reserves_build_support', ROOT / 'prebuild_skillsbench_task.py')
    text = helper.inject_apt_download_support('FROM ubuntu:24.04\nRUN apt-get update\n', cache, 'reserves-at-risk-calc')
    assert 'Acquire::Retries' in text and 'Pipeline-Depth' in text and 'COPY .causalflow-apt-cache/' in text
    log.rename(log.with_name('build.apt-proxy-drop-r002.log'))
    cf = runner.load('_guard3_reserves_recovery_cf', runner.CF / 'experiment.py')
    fixes = runner.load('_guard3_reserves_recovery_fixes', ROOT / 'runtime_fixes.py')
    try:
        proof = fixes.ensure_reserves_initial_image(target, cf)
    except BaseException as exc:
        runner.write(archive / 'recovery-error.json', {'at': runner.now(), 'type': type(exc).__name__, 'error': str(exc), 'model_calls': 0})
        raise
    check = {'at': runner.now(), 'passed': True, 'initial_image': proof,
             'apt_cache_packages': len(packages), 'apt_cache_bytes': sum(p.stat().st_size for p in packages),
             'no_model_calls': True, 'offline_input_packages_empty_outputs_verified': True,
             'source_fresh_rollout_id_reused': row['rollout_id'], 'fresh_was_never_started': True,
             'completed_slots_preserved': [s for s, v in state['tasks'].items() if v['phase'] == 'finished']}
    runner.write(ROOT / 'reserves-build-recovery-check.json', check)
    pending = {'task_id': row['task_id'], 'phase': 'pending', 'rollout': 'pending',
               'fresh_rollout_id': row['rollout_id'], 'prior_infra_evidence': str(archive)}
    runner.write(target / 'task_state/reserves-at-risk-calc.json', pending)
    state['tasks'][SLOT] = pending
    state['updated_at'] = runner.now()
    runner.write(ROOT / 'batch_state.json', state)
    runner.write(ROOT / 'resume-plan.json', {
        'at': runner.now(), 'passed': True, 'slots': [SLOT], 'rollout_ids': {SLOT: row['rollout_id']},
        'batch_state_sha256': hashlib.sha256((ROOT / 'batch_state.json').read_bytes()).hexdigest(),
        'evidence': str(ROOT / 'reserves-build-recovery-check.json'), 'fresh_model_calls_so_far': 0,
    })
    print('reserves dependencies rebuilt and verified offline; only reserves prepared for fresh continuation', flush=True)


if __name__ == '__main__':
    recover()
