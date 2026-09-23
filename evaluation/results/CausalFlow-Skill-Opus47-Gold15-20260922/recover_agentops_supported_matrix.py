"""Verifier-only recovery with an explicit Python compatibility protocol revision.

No model calls, test assertion edits, or model patch edits. Original attempts remain intact.
"""
import datetime, hashlib, json, shutil, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'verifier-recovery-agentops-supported-matrix-20260923'
TASK = Path('/home/linyuanjing/skillgen-jobs/opus47-openrouter-v1.1-20260919/tasks/fix-build-agentops')
SOURCE = ROOT/'runs/causalflow-skill-opus47-gold15-20260922/fix-build-agentops-causalflow-opus47-r001'
NAME = 'causalflow-agentops-verifier-supported-20260923'
IMAGE = 'sha256:5b0c1c98d55c67b47fcc57bd39680f4eedb335ddee3cab48d296bd168e80d98b'
REPO = '/home/github/build/failed/AgentOps-AI/agentops'
PY = '/opt/hostedtoolcache/Python/3.11.8/x64/bin/python'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name, value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args):
    result = subprocess.run(args,capture_output=True,text=True)
    if result.returncode: raise RuntimeError(str(args[:3])+': '+result.stderr[-1500:]+result.stdout[-1500:])
    return result.stdout
def logged(name, command, timeout):
    with (OUT/name).open('w') as stream:
        result = subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
    return result.returncode

OUT.mkdir(exist_ok=False)
shutil.copytree(TASK/'verifier', OUT/'verifier-original')
shutil.copytree(TASK/'verifier', OUT/'verifier-revised')
script = OUT/'verifier-revised/run_passed.sh'
old = script.read_text()
needle = 'echo tox > /home/github/24653510459/steps/bugswarm_3.sh'
assert old.count(needle)==1
replacement = "echo 'tox -e py38,py39,py310,py311,py312 --workdir /opt/agentops-verifier-tox --result-json /logs/verifier/tox-results.json' > /home/github/24653510459/steps/bugswarm_3.sh"
script.write_text(old.replace(needle,replacement))
patch = SOURCE/'verifier/diffs/AgentOps-AI/agentops/patch_1.diff'
note = SOURCE/'verifier/failed_reasons.txt'
provenance = dict(started_at=now(),mode='verifier-only from real exported patch and note',
    source_run=str(SOURCE),image=IMAGE,container=NAME,patch_sha256=sha(patch),note_sha256=sha(note),
    protocol_revision='agentops-supported-python-v1',old_matrix=['py37','py38','py39','py310','py311','py312'],
    new_matrix=['py38','py39','py310','py311','py312'],
    reason='The original verifier pins langchain 0.0.352 and langchain-core 0.1.23, both require Python >=3.8.1. User requested fixing this disclosed INFRA_ERROR and rerunning on 2026-09-23.',
    assertions_changed=False,model_patch_changed=False,method_calls=0,fresh_rollout_calls=0,judge_calls=0,
    original_verifier_sha256={p.name:sha(p) for p in (OUT/'verifier-original').iterdir() if p.is_file()},
    revised_verifier_sha256={p.name:sha(p) for p in (OUT/'verifier-revised').iterdir() if p.is_file()},
    timeout_sec=240,restoration='Clean initial source image plus byte-identical exported patch/note. Not a full original workspace snapshot.')
write('provenance.json',provenance)
write('state.json',dict(status='setup',started_at=now()))
try:
    run('docker','create','--name',NAME,'--cpus','4','--memory','4096m','--entrypoint','/bin/bash',IMAGE,'-c','sleep infinity')
    run('docker','start',NAME)
    run('docker','cp',str(OUT/'verifier-revised'),NAME+':/verifier')
    run('docker','cp',str(patch),NAME+':'+REPO+'/patch_1.diff')
    run('docker','cp',str(note),NAME+':/home/github/build/failed/failed_reasons.txt')
    paths=':'.join('/opt/hostedtoolcache/Python/'+v+'/x64/bin' for v in ['3.11.8','3.8.18','3.9.18','3.10.13','3.12.2'])
    setup=f'''set -eu
cd {REPO}
git apply --check patch_1.diff
git apply patch_1.diff
mkdir -p /logs/verifier
ln -s /verifier /tests
printf '\\nPATH="{paths}:$PATH"\\nVIRTUALENV_PIP=24.0\\nVIRTUALENV_SETUPTOOLS=69.5.1\\nVIRTUALENV_WHEEL=0.43.0\\nVIRTUALENV_NO_PERIODIC_UPDATE=1\\n' >> /etc/environment
cat > /tmp/agentops-pip-constraints.txt <<'EOF'
langchain==0.0.352
langchain-core==0.1.23
EOF
git diff --stat
sha256sum patch_1.diff /home/github/build/failed/failed_reasons.txt
'''
    (OUT/'setup.log').write_text(run('docker','exec',NAME,'bash','-lc',setup))
    env=[]
    for key in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:
        env += ['-e',key+'=http://host.docker.internal:7890']
    base=['docker','exec',*env,'-e','REPO_ID=AgentOps-AI/agentops','-e','bugswarm_image_tag=AgentOps-AI-agentops-24579293289',NAME]
    prepare=f'''set -eu
set -a; . /etc/environment; set +a
export PIP_CONSTRAINT=/tmp/agentops-pip-constraints.txt PIP_INDEX_URL=https://pypi.org/simple
unset PIP_EXTRA_INDEX_URL
{PY} -m pip install tox==4.63.0 virtualenv==21.11.0
cd {REPO}
{PY} -m tox -e py38,py39,py310,py311,py312 --workdir /opt/agentops-verifier-tox --notest
cd /home/github/build
export PATH=/root/.local/bin:/home/github/.local/bin:$PATH
uv init --python 3.10
uv add pytest==8.4.1
uv add pytest-json-ctrf==0.3.5
uv add unidiff==0.7.5
'''
    write('state.json',dict(status='preparing_dependencies',started_at=now()))
    code=logged('prepare.log',base+['bash','-lc',prepare],1800)
    assert code==0, f'Dependency preflight failed: {code}; see prepare.log'
    write('state.json',dict(status='verifier_running',started_at=now()))
    started=time.monotonic()
    code=logged('test-stdout.txt',base+['timeout','--signal=TERM','240','bash','/verifier/test.sh'],270)
    run('docker','cp',NAME+':/logs/verifier',str(OUT/'verifier-output'))
    archive="cd /opt/agentops-verifier-tox && find . -type f \\( -path '*/log/*' -o -name '.tox-info.json' \\) -print0 | tar --null -T - -czf /tmp/tox-evidence.tar.gz"
    run('docker','exec',NAME,'bash','-c',archive)
    run('docker','cp',NAME+':/tmp/tox-evidence.tar.gz',str(OUT/'tox-evidence.tar.gz'))
    rewardfile=OUT/'verifier-output/reward.txt'
    reward=rewardfile.read_text().strip() if rewardfile.exists() else None
    provenance.update(finished_at=now(),verifier_process_exit_code=code,wall_time_sec=time.monotonic()-started,reward=reward)
    write('provenance.json',provenance)
    write('state.json',dict(status='complete' if code==0 and reward in ('0','1') else 'needs_attention',finished_at=now(),reward=reward,exit_code=code))
except Exception as exc:
    write('state.json',dict(status='error',at=now(),error=str(exc)))
    raise
finally:
    subprocess.run(['docker','stop',NAME],capture_output=True)
