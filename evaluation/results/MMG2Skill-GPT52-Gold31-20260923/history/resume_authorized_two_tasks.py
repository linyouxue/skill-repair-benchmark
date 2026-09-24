"""Apply the user's 2026-09-24 two-task authorization, exactly once."""
import hashlib, json, os, shutil, signal, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
def write(p, data):
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(p)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

assert not (ROOT/'authorized-two-task-recovery.json').exists(), 'Already applied; reconcile instead of retrying'
state = read(ROOT/'batch_state.json')
assert state['tasks']['fix-build-agentops']['phase'] == 'blocked_protocol'
assert state['tasks']['manufacturing-equipment-maintenance']['phase'] == 'error'
assert all(v['phase'] in ('finished','blocked_protocol','waiting_remote','error') for v in state['tasks'].values())
assert not subprocess.check_output(['docker','ps','-q'],text=True).strip(), 'Unexpected active container'
pid = int((ROOT/'batch.pid').read_text())
assert str(ROOT/'experiment.py').encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
task = Path(read(ROOT/'manifest.json')['tasks_root'])/'fix-build-agentops'
script = task/'verifier/run_passed.sh'
old = script.read_text(encoding='utf-8')
needle = 'echo tox > /home/github/24653510459/steps/bugswarm_3.sh'
assert old.count(needle) == 1
paths = ':'.join('/opt/hostedtoolcache/Python/'+v+'/x64/bin' for v in ['3.11.8','3.8.18','3.9.18','3.10.13','3.12.2'])
anchor = 'source /etc/environment\nset +o allexport\n'
assert old.count(anchor) == 1
new = old.replace(needle, "echo 'tox -e py38,py39,py310,py311,py312 --result-json /logs/verifier/tox-results.json' > /home/github/24653510459/steps/bugswarm_3.sh")
new = new.replace(anchor, anchor+'\n# Approved supported-Python matrix; expose the image\'s existing interpreters.\nexport PATH="'+paths+':$PATH"\n')
subprocess.run(['bash','-n'],input=new,text=True,check=True)
probe = 'set -eu\n' + '\n'.join('/opt/hostedtoolcache/Python/'+v+'/x64/bin/python --version' for v in ['3.8.18','3.9.18','3.10.13','3.11.8','3.12.2'])
probe_result = subprocess.run(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--entrypoint','/bin/bash','bugswarm/cached-images:AgentOps-AI-agentops-24579293289','-c',probe],capture_output=True,text=True,check=True)
g = ROOT/'generation/manufacturing-equipment-maintenance'
assert not (g/'analysis.json').exists() and not (g/'adapter_result.json').exists()
calls = sorted((g/'analysis_calls').glob('*.response.json'))
assert len(calls) == 1 and calls[0].name == 'call-001.response.json'
assert not list((g/'refine_calls').glob('*.response.json'))
for tid in ['fix-build-agentops','manufacturing-equipment-maintenance']:
    assert not (ROOT/'runs/mmg2skill-gpt52-gold31-20260923'/f'{tid}-mmg2skill-gpt52-r001').exists()
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive = ROOT/'recovery-history'/(stamp+'-user-authorized-two-tasks')
archive.mkdir(parents=True)
shutil.copytree(task/'verifier', archive/'agentops-verifier-original')
shutil.copytree(g, archive/'manufacturing-generation-original')
for name in ['batch_state.json','protocol.json','recovery_queue.json']:
    shutil.copy2(ROOT/name,archive/name)
for tid in ['fix-build-agentops','manufacturing-equipment-maintenance']:
    for folder in ['task_state','worker_logs']:
        f=ROOT/folder/(tid+('.json' if folder=='task_state' else '.log'))
        if f.exists():
            (archive/folder).mkdir(exist_ok=True)
            shutil.copy2(f,archive/folder/f.name)
approval = dict(approved_at=datetime.now(timezone.utc).isoformat(), user_authorization='Yes to AgentOps py38-py312 and one extra manufacturing Analyzer retry; Druid continues waiting.', old_matrix=['py37','py38','py39','py310','py311','py312'], new_matrix=['py38','py39','py310','py311','py312'], assertions_changed=False, dependency_pins_changed=False, original_run_passed_sha256=sha(script), revised_run_passed_sha256=hashlib.sha256(new.encode()).hexdigest(), interpreter_probe=probe_result.stdout, protocol_revision='mmg-agentops-supported-python-v1', archive=str(archive))
os.kill(pid, signal.SIGSTOP)
replaced=False
try:
    assert script.read_text(encoding='utf-8') == old
    script.write_text(new,encoding='utf-8')
    assert sha(task/'verifier/test_outputs.py') == sha(archive/'agentops-verifier-original/test_outputs.py')
    assert sha(task/'verifier/test.sh') == sha(archive/'agentops-verifier-original/test.sh')
    write(ROOT/'agentops-protocol-approval.json',approval)
    # Original request stays byte-identical. Archive the paid invalid response and its
    # pending marker so RecordedClient permits exactly one newly authorized attempt.
    removed=[]
    for suffix in ['response.json','pending.json','error.json']:
        f=g/'analysis_calls'/('call-001.'+suffix)
        if f.exists():
            assert f.resolve().is_relative_to(g.resolve())
            target=archive/('manufacturing-call-001.'+suffix)
            f.rename(target); removed.append({'file':f.name,'sha256':sha(target)})
    q=read(ROOT/'recovery_queue.json')
    q['fix-build-agentops']={'stage':'method','reason':'User approved supported py38-py312 verifier matrix; unchanged assertions and dependency pins; no prior MMG method or fresh run.'}
    q['manufacturing-equipment-maintenance']={'stage':'analysis_authorized_retry_once','reason':'User explicitly authorized one extra Analyzer call after invalid completed output; original response archived; same request; no automatic additional retries.'}
    write(ROOT/'recovery_queue.json',q)
    protocol=read(ROOT/'protocol.json')
    protocol['task_exceptions']={'fix-build-agentops':approval,'manufacturing-equipment-maintenance':{'extra_analyzer_attempts_authorized':1,'original_invalid_response_archived':True,'request_unchanged':True,'archive':str(archive)}}
    write(ROOT/'protocol.json',protocol)
    receipt={'at':approval['approved_at'],'archive':str(archive),'agentops':approval,'manufacturing_archived_call_files':removed,'extra_analyzer_attempts_authorized':1,'druid':'waiting_remote','old_controller_pid':pid}
    write(ROOT/'authorized-two-task-recovery.json',receipt)
    write(archive/'recovery.json',receipt)
    os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
    for _ in range(100):
        if not Path(f'/proc/{pid}').exists(): break
        time.sleep(.1)
    assert not Path(f'/proc/{pid}').exists()
    subprocess.run(['bash',str(ROOT/'launch.sh'),'--resume-queue'],check=True)
    replaced=True
    print(json.dumps(receipt,ensure_ascii=True))
finally:
    if not replaced and Path(f'/proc/{pid}').exists(): os.kill(pid,signal.SIGCONT)
