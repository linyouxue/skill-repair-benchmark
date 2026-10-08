"""Check isolated networking and requeue only the five proven pre-model failures."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(p):
    return json.loads(Path(p).read_text())


def write(p, value):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check_build_network():
    name = 'guard3-reserves-initial-build-20261008'
    network = subprocess.check_output(['docker', 'network', 'create', '--subnet', '10.252.245.0/24', '--label', 'benchflow.owned=true', name], text=True).strip()
    tag = 'guard3-network-canary:20261008'
    try:
        with tempfile.TemporaryDirectory(prefix='guard3-network-canary-') as directory:
            code = "import urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://host.docker.internal:7890','https':'http://host.docker.internal:7890'})); print(o.open('https://openrouter.ai/api/v1/models',timeout=20).status); print(o.open('http://mirrors.tuna.tsinghua.edu.cn/ubuntu/dists/noble/InRelease',timeout=20).status)"
            Path(directory, 'Dockerfile').write_text('FROM python:3.12-slim\nRUN ["python", "-c", ' + json.dumps(code) + ']\n')
            env = dict(os.environ, DOCKER_BUILDKIT='0')
            with (ROOT / 'build-network-canary.log').open('w') as log:
                subprocess.run(['docker', 'build', '--network', name, '--add-host', 'host.docker.internal:host-gateway', '-t', tag, directory], env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        assert (ROOT / 'build-network-canary.log').read_text().count('200') >= 2
    finally:
        subprocess.run(['docker', 'network', 'rm', network], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['docker', 'image', 'rm', tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def recover():
    assert not subprocess.check_output(['docker', 'ps', '-q'], text=True).strip()
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            try:
                assert str(ROOT / 'experiment.py').encode() not in (p / 'cmdline').read_bytes(), 'Live controller/worker exists'
            except OSError:
                pass
    state = read(ROOT / 'batch_state.json')
    assert state['status'] == 'blocked_incomplete_validation'
    assert not (ROOT / 'infra-recovery-check.json').exists(), 'Recovery already prepared; do not requeue again'
    manifest = read(ROOT / 'manifest.json')
    evidence = []
    for row in manifest['tasks']:
        target = Path(row['rerun_root'])
        run = target / 'runs' / row['method_id'] / row['rollout_id']
        trace = run / 'trajectory/llm_trajectory.jsonl'
        assert not trace.exists() or trace.stat().st_size == 0, 'Provider request exists: do not fresh-retry'
        if run.exists():
            result = read(run / 'benchmark_result.json')
            assert result.get('provider_requests') in (None, 0)
            assert not (run / 'agent/install-stdout.txt').exists(), 'Runtime install started: reconcile before retry'
            assert 'all predefined address pools have been fully subnetted' in str(result), 'Unexpected failure'
        else:
            assert row['task_id'] == 'reserves-at-risk-calc'
            log = target / 'runtime-cache/reserves-at-risk-calc/build.log'
            assert 'Unable to connect to host.docker.internal:7890' in log.read_text()
        evidence.append({'slot': row['slot'], 'prior_rollout_id': row['rollout_id'],
                         'task_provider_requests': 0, 'failure_kind': 'pre-model-network-build'})
    check_build_network()
    archive = ROOT / 'recovery-history/pre-model-network-20261008'
    archive.mkdir(parents=True)
    for name in ('manifest.json', 'batch_state.json', 'batch.pid', 'startup-evidence.json'):
        shutil.copyfile(ROOT / name, archive / name)
    shutil.copytree(ROOT / 'worker_logs', archive / 'worker_logs')
    for row in manifest['tasks']:
        target = Path(row['rerun_root'])
        old_state = target / 'task_state' / f"{row['task_id']}.json"
        if old_state.exists():
            dest = archive / 'task_state' / f"{row['slot']}.json"
            dest.parent.mkdir(exist_ok=True)
            shutil.copyfile(old_state, dest)
        recovery = read(target / 'recovery_queue.json')
        row['prior_pre_model_rollout_id'] = row['rollout_id']
        row['rollout_id'] = row['rollout_id'].replace('-r001', '-r002')
        assert not (target / 'runs' / row['method_id'] / row['rollout_id']).exists()
        recovery[row['task_id']]['fresh_rollout_id'] = row['rollout_id']
        recovery[row['task_id']]['reason'] = 'Verified pre-model infrastructure recovery: explicit nonoverlapping Docker networks; all prior task provider requests zero'
        write(target / 'recovery_queue.json', recovery)
        write(old_state, {'task_id': row['task_id'], 'phase': 'pending', 'rollout': 'pending', 'fresh_rollout_id': row['rollout_id'], 'prior_infra_evidence': str(archive)})
        if row['task_id'] == 'reserves-at-risk-calc':
            log = target / 'runtime-cache/reserves-at-risk-calc/build.log'
            shutil.copyfile(log, archive / 'reserves-build-r001.log')
            log.rename(log.with_name('build.pre-network-recovery.log'))
    write(ROOT / 'manifest.json', manifest)
    write(ROOT / 'infra-recovery-check.json', {'passed': True, 'no_model_canary': 'Legacy Docker build with explicit isolated subnet; OpenRouter free models and original Ubuntu mirror both HTTP200', 'evidence': evidence, 'all_old_runs_preserved': True, 'other_networks_unchanged': True, 'automatically_retry_again': False})
    print('verified pre-model network recovery; five r002 slots safely prepared', flush=True)


if __name__ == '__main__':
    recover()
