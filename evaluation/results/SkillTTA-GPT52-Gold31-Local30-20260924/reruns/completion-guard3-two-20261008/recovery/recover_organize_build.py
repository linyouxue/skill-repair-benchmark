"""Recover pre-model paper download failure with verified original bytes only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import ipaddress
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import traceback

ROOT = Path(__file__).resolve().parent
SLOT = 'skilltta__organize-messy-files'

def read(path):
    return json.loads(path.read_text())

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    assert not subprocess.check_output(['docker', 'ps', '-q'], text=True).strip()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == __import__('os').getpid():
            continue
        try:
            command = (entry / 'cmdline').read_bytes()
            assert str(ROOT / 'experiment.py').encode() not in command, 'Preserve existing controller/worker'
        except OSError:
            pass
    state = read(ROOT / 'batch_state.json')
    assert state['status'] == 'blocked_incomplete_validation'
    assert state['tasks']['mmg2skill__drone-planning-control']['phase'] == 'finished'
    assert state['tasks']['mmg2skill__drone-planning-control']['rollout'] == 'FAIL'
    manifest = read(ROOT / 'manifest.json')
    row = next(r for r in manifest['tasks'] if r['slot'] == SLOT)
    target = Path(row['rerun_root'])
    run = target / 'runs' / row['method_id'] / row['rollout_id']
    result = read(run / 'benchmark_result.json')
    assert result['execution_ok'] is False and result.get('provider_requests') in (None, 0)
    assert 'wget -q' in result['error'] and 'exit code: 4' in result['error']
    assert not (run / 'agent/install-stdout.txt').exists()
    assert not (run / 'trajectory/llm_trajectory.jsonl').exists()
    acp = run / 'trajectory/acp_trajectory.jsonl'
    assert not acp.exists() or acp.stat().st_size == 0
    assert read(run / 'results.jsonl')['info']['training_ready'] is False
    archive = ROOT / 'recovery-history/organize-pre-model-paper-download'
    assert not archive.exists(), 'Inspect existing recovery; never loop it automatically'
    archive.mkdir(parents=True)
    for name in ['manifest.json', 'protocol.json', 'batch_state.json', 'batch.pid', 'experiment.py', 'startup-evidence.json']:
        shutil.copyfile(ROOT / name, archive / name)
    shutil.copyfile(ROOT / 'worker_logs' / (SLOT + '.log'), archive / 'worker.log')
    shutil.copyfile(target / 'task_state/organize-messy-files.json', archive / 'task_state.json')
    write(archive / 'cause.json', {'at': now(), 'cause': 'Dockerfile wget paper download exited 4 before runtime installation',
          'fresh_model_calls': 0, 'old_run_preserved': str(run),
          'remediation': 'Download same pinned paper URLs through the existing host proxy with bounded transport retries; require byte-for-byte match to prior authentic papers. Cache only these inputs in a temporary Docker build, leave download guards, original docs, package pins, task and verifier unchanged.',
          'no_outputs_reconstructed': True, 'completed_drone_preserved': True})
    env = Path(row['tasks_root']) / row['task_id'] / 'environment'
    source_manifest = {p.relative_to(env).as_posix(): sha(p) for p in env.rglob('*') if p.is_file()}
    text = (env / 'Dockerfile').read_text()
    urls = re.findall(r'https://arxiv\.org/pdf/[0-9.]+v[0-9]+\.pdf', text)
    assert len(urls) == 100 and len(set(urls)) == 100
    names = {url.rsplit('/', 1)[-1] for url in urls}
    original_tar = Path(row['previous_result']).parent / 'artifacts/workspace-before-verifier.tar.gz'
    historical = {}
    with tarfile.open(original_tar, 'r|gz') as tar:
        for member in tar:
            name = Path(member.name).name
            if member.isfile() and name in names:
                digest = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                assert name not in historical or historical[name] == digest
                historical[name] = digest
    assert set(historical) == names, 'Require authentic byte references for every original paper'
    directory = target / 'runtime-cache/organize-messy-files'
    cache = directory / 'papers'
    cache.mkdir(parents=True)
    write(directory / 'original-paper-references.json', {'source': str(original_tar), 'sha256_by_file': historical,
           'use': 'Equality check only; inputs downloaded from original pinned URLs, never copied from repaired outputs'})

    def fetch(url):
        name = url.rsplit('/', 1)[-1]
        partial = cache / (name + '.pending')
        with (directory / (name + '.download.log')).open('w') as log:
            subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                            '--proxy', 'http://127.0.0.1:7890', '--retry', '2', '--retry-all-errors',
                            '--retry-delay', '1', '--connect-timeout', '15', '--max-time', '60',
                            '--output', str(partial), url], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=200)
        assert partial.read_bytes().startswith(b'%PDF-'), name
        assert sha(partial) == historical[name], 'Pinned paper bytes changed: ' + name
        partial.replace(cache / name)
        return name

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fetch, url) for url in urls]
        for index, future in enumerate(as_completed(futures), 1):
            name = future.result()
            print(f'original pinned PDF verified {index}/100: {name}', flush=True)
    assert {p.name: sha(p) for p in cache.glob('*.pdf')} == historical
    context = directory / 'build-context'
    shutil.copytree(env, context)
    shutil.copytree(cache, context / '.guard3-paper-cache')
    project = ROOT.parents[1]
    helper_path = project / 'causalflow_runs/opus47-gold15-20260922/source/repro_wrappers/prebuild_skillsbench_task.py'
    spec = importlib.util.spec_from_file_location('_organize_dependency_helper', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    marker = "RUN <<'EOF'"
    assert text.count(marker) == 1
    modified = text.replace(marker, 'COPY .guard3-paper-cache/ /root/papers/all/\n\n' + marker)
    modified = helper.inject_apt_mirror_profile(modified, 'tuna')
    (context / 'Dockerfile').write_text(modified)
    write(directory / 'input-cache-check.json', {'passed': True, 'model_calls': 0, 'pdf_count': 100,
          'every_pdf_matches_historical_bytes': True, 'original_urls_unchanged': True,
          'source_environment_sha256_by_file': source_manifest, 'paper_sha256_by_file': historical,
          'temporary_dockerfile_sha256': sha(context / 'Dockerfile'),
          'original_download_guards_and_dependency_pins_retained': True})
    tag = 'skilltta-guard3-two-organize-initial:20261008'
    with Path('/tmp/skillrepair-expanded-docker-start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with (directory / 'build.log').open('w') as log:
            command = ['docker', 'build', '--add-host', 'host.docker.internal:host-gateway']
            for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
                command += ['--build-arg', key + '=http://host.docker.internal:7890']
            command += ['--build-arg', 'NO_PROXY=localhost,127.0.0.1,::1,host.docker.internal,main,mirrors.tuna.tsinghua.edu.cn', '-t', tag, str(context)]
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    image = subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'], text=True).strip()
    ids = subprocess.check_output(['docker', 'network', 'ls', '-q'], text=True).split()
    networks = json.loads(subprocess.check_output(['docker', 'network', 'inspect', *ids], text=True))
    subnet = '10.252.249.0/24'
    assert all(not ipaddress.ip_network(subnet).overlaps(ipaddress.ip_network(c['Subnet']))
               for n in networks for c in (n['IPAM'].get('Config') or []) if c.get('Subnet'))
    network = subprocess.check_output(['docker', 'network', 'create', '--subnet', subnet, '--label', 'benchflow.owned=true',
                                       'guard3-two-organize-offline-check'], text=True).strip()
    cid = None
    try:
        cid = subprocess.check_output(['docker', 'run', '-d', '--network', network, '--entrypoint', 'sleep', image, '180'], text=True).strip()
        # Disconnect the only interface before inspecting the clean image.
        subprocess.run(['docker', 'network', 'disconnect', network, cid], check=True)
        code = "import pathlib,hashlib,json,importlib.metadata as m; p=pathlib.Path('/root/papers'); print(json.dumps({'files':{f.relative_to(p/'all').as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/'all').rglob('*') if f.is_file()},'other_files':[f.relative_to(p).as_posix() for f in p.rglob('*') if f.is_file() and not f.is_relative_to(p/'all')],'packages':{n:m.version(n) for n in ['openpyxl','pandas','pdfplumber','tabula-py','PyPDF2']},'other_root_files':[f.name for f in pathlib.Path('/root').iterdir() if f.name not in ['papers','.bashrc','.profile','.wget-hsts','.cache']]}))"
        clean = json.loads(subprocess.check_output(['docker', 'exec', cid, 'python3', '-c', code], text=True))
        expected = dict(historical)
        for name in ['DAMOP.pptx', 'paper_file_1.docx', 'paper_file_2.docx']:
            expected[name] = sha(env / name)
        assert clean['files'] == expected and not clean['other_files']
        assert clean['packages'] == {'openpyxl': '3.1.5', 'pandas': '2.2.3', 'pdfplumber': '0.11.4', 'tabula-py': '2.9.3', 'PyPDF2': '3.0.1'}
        assert not clean['other_root_files'], clean['other_root_files']
    finally:
        if cid:
            subprocess.run(['docker', 'rm', '-f', cid], stdout=subprocess.DEVNULL, check=True)
        subprocess.run(['docker', 'network', 'rm', network], stdout=subprocess.DEVNULL, check=True)
    assert source_manifest == {p.relative_to(env).as_posix(): sha(p) for p in env.rglob('*') if p.is_file()}
    proof = {'at': now(), 'passed': True, 'image_id': image, 'source_tag': tag, 'model_calls': 0,
             'input_sha256_by_file': expected, 'packages': clean['packages'], 'clean_output_directories': True,
             'original_environment_unchanged': True, 'original_run_preserved': str(run),
             'build_provenance': 'Immutable build of original Dockerfile with transport-only cached original input COPY and established APT mirror; not a commit of an agent/replay container.'}
    write(directory / 'prebuilt-image.json', proof)
    write(ROOT / 'organize-build-recovery-check.json', proof)
    row['prior_pre_model_rollout_id'] = row['rollout_id']
    row['rollout_id'] = row['rollout_id'].replace('-r001', '-r002')
    assert not (target / 'runs' / row['method_id'] / row['rollout_id']).exists()
    recovery = read(target / 'recovery_queue.json')
    recovery[row['task_id']] = {'fresh_rollout_id': row['rollout_id'],
          'reason': 'Verified clean original input image after pre-model wget network failure; r001 preserved, task model calls zero.'}
    write(target / 'recovery_queue.json', recovery)
    pending = {'task_id': row['task_id'], 'phase': 'pending', 'rollout': 'pending',
               'fresh_rollout_id': row['rollout_id'], 'prior_infra_evidence': str(archive)}
    write(target / 'task_state' / (row['task_id'] + '.json'), pending)
    state['tasks'][SLOT] = pending
    state['updated_at'] = now()
    write(ROOT / 'manifest.json', manifest)
    write(ROOT / 'batch_state.json', state)
    write(ROOT / 'resume-plan.json', {'at': now(), 'passed': True, 'slots': [SLOT],
         'rollout_ids': {SLOT: row['rollout_id']}, 'batch_state_sha256': sha(ROOT / 'batch_state.json'),
         'evidence': str(ROOT / 'organize-build-recovery-check.json'), 'fresh_model_calls_so_far': 0})
    print('Verified original clean image; only Organize r002 prepared, completed Drone preserved', flush=True)

if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        write(ROOT / 'organize-build-recovery-error.json', {'at': now(), 'type': type(exc).__name__, 'error': str(exc), 'model_calls': 0})
        traceback.print_exc()
        raise
