"""Reuse the completed build; finish its offline check and queue only Organize."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
SLOT = 'skilltta__organize-messy-files'

def read(path):
    return json.loads(path.read_text())

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert not subprocess.check_output(['docker', 'ps', '-q'], text=True).strip()
assert not (ROOT / 'resume-plan.json').exists(), 'Preserve an existing recovery plan'
error = read(ROOT / 'organize-build-recovery-error.json')
assert error['type'] == 'AssertionError' and error['error'] == "['.ssh']" and error['model_calls'] == 0
manifest = read(ROOT / 'manifest.json')
row = next(r for r in manifest['tasks'] if r['slot'] == SLOT)
target = Path(row['rerun_root'])
run = target / 'runs' / row['method_id'] / row['rollout_id']
result = read(run / 'benchmark_result.json')
assert not result['execution_ok'] and result.get('provider_requests') in (None, 0)
assert not (run / 'agent/install-stdout.txt').exists()
directory = target / 'runtime-cache/organize-messy-files'
cache_check = read(directory / 'input-cache-check.json')
assert cache_check['passed'] and cache_check['every_pdf_matches_historical_bytes']
env = Path(row['tasks_root']) / row['task_id'] / 'environment'
assert cache_check['source_environment_sha256_by_file'] == {p.relative_to(env).as_posix(): sha(p) for p in env.rglob('*') if p.is_file()}
build_log = (directory / 'build.log').read_text()
assert '#15 DONE ' in build_log and 'Successfully installed ' in build_log
tag = 'skilltta-guard3-two-organize-initial:20261008'
image = subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'], text=True).strip()
code = "import pathlib,hashlib,json,importlib.metadata as m; p=pathlib.Path('/root/papers'); s=pathlib.Path('/root/.ssh'); print(json.dumps({'files':{f.relative_to(p/'all').as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/'all').rglob('*') if f.is_file()},'other_files':[f.relative_to(p).as_posix() for f in p.rglob('*') if f.is_file() and not f.is_relative_to(p/'all')],'packages':{n:m.version(n) for n in ['openpyxl','pandas','pdfplumber','tabula-py','PyPDF2']},'other_root_files':[f.name for f in pathlib.Path('/root').iterdir() if f.name not in ['papers','.bashrc','.profile','.wget-hsts','.cache','.ssh']],'system_ssh_entries':[f.name for f in s.iterdir()] if s.exists() else [],'home_agent_exists':pathlib.Path('/home/agent').exists(),'app_files':[str(f) for f in pathlib.Path('/app').rglob('*') if f.is_file()]}))"
clean = json.loads(subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', image, '-c', code], text=True))
expected = dict(cache_check['paper_sha256_by_file'])
for name in ['DAMOP.pptx', 'paper_file_1.docx', 'paper_file_2.docx']:
    expected[name] = sha(env / name)
assert clean['files'] == expected and len(expected) == 103
assert not clean['other_files'] and not clean['other_root_files'] and not clean['system_ssh_entries']
assert not clean['home_agent_exists'] and not clean['app_files']
assert clean['packages'] == {'openpyxl': '3.1.5', 'pandas': '2.2.3', 'pdfplumber': '0.11.4', 'tabula-py': '2.9.3', 'PyPDF2': '3.0.1'}
archive = ROOT / 'recovery-history/organize-pre-model-paper-download'
shutil.copyfile(ROOT / 'organize-build-recovery-error.json', archive / 'offline-check-empty-system-dir.json')
proof = {'at': datetime.now(timezone.utc).isoformat(), 'passed': True, 'image_id': image, 'source_tag': tag,
         'model_calls': 0, 'input_sha256_by_file': expected, 'packages': clean['packages'],
         'clean_output_directories': True, 'original_environment_unchanged': True,
         'system_ssh_directory_verified_empty': True, 'original_run_preserved': str(run),
         'build_provenance': 'Original Dockerfile with transport-only cached original PDF COPY and established APT mirror; unchanged guards, docs and pins. Immutable build, no replay container commit.',
         'all_inputs_real_and_byte_identical': True, 'offline_network': 'none'}
write(directory / 'prebuilt-image.json', proof)
write(ROOT / 'organize-build-recovery-check.json', proof)
row['prior_pre_model_rollout_id'] = row['rollout_id']
row['rollout_id'] = row['rollout_id'].replace('-r001', '-r002')
assert not (target / 'runs' / row['method_id'] / row['rollout_id']).exists()
recovery = read(target / 'recovery_queue.json')
recovery[row['task_id']] = {'fresh_rollout_id': row['rollout_id'],
    'reason': 'Original input image verified offline after pre-model paper download network failure; preserve r001, zero task model calls.'}
write(target / 'recovery_queue.json', recovery)
pending = {'task_id': row['task_id'], 'phase': 'pending', 'rollout': 'pending',
           'fresh_rollout_id': row['rollout_id'], 'prior_infra_evidence': str(archive)}
write(target / 'task_state' / (row['task_id'] + '.json'), pending)
state = read(ROOT / 'batch_state.json')
assert state['status'] == 'blocked_incomplete_validation'
assert state['tasks']['mmg2skill__drone-planning-control']['rollout'] == 'FAIL'
state['tasks'][SLOT] = pending
state['updated_at'] = proof['at']
write(ROOT / 'manifest.json', manifest)
write(ROOT / 'batch_state.json', state)
write(ROOT / 'resume-plan.json', {'at': proof['at'], 'passed': True, 'slots': [SLOT],
    'rollout_ids': {SLOT: row['rollout_id']}, 'batch_state_sha256': sha(ROOT / 'batch_state.json'),
    'evidence': str(ROOT / 'organize-build-recovery-check.json'), 'fresh_model_calls_so_far': 0})
protocol = read(ROOT / 'protocol.json')
protocol['infrastructure_recovery'] = {'organize': {'old_rollout_id': row['prior_pre_model_rollout_id'],
    'recovered_rollout_id': row['rollout_id'], 'old_task_provider_requests': 0,
    'initial_image': image, 'original_pdf_inputs_verified': 100, 'original_document_inputs_verified': 3,
    'fixed_package_versions_verified': 5, 'model_calls_during_recovery': 0,
    'completed_drone_untouched': True, 'evidence': str(ROOT / 'organize-build-recovery-check.json')}}
write(ROOT / 'protocol.json', protocol)
print('Clean image checked offline:103 original inputs,5 fixed dependencies,empty outputs; only Organize r002 queued')
