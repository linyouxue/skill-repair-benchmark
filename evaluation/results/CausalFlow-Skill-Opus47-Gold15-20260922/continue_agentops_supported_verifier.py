"""Continue environment preparation of the preserved verifier-only recovery container."""
import datetime, json, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'verifier-recovery-agentops-supported-matrix-20260923'
NAME='causalflow-agentops-verifier-supported-20260923'
PY='/opt/hostedtoolcache/Python/3.11.8/x64/bin/python'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def call(*args):
    result=subprocess.run(args,capture_output=True,text=True)
    if result.returncode: raise RuntimeError(result.stderr[-1200:]+result.stdout[-1200:])
    return result.stdout
def logged(name,args,timeout):
    assert not (OUT/name).exists()
    with (OUT/name).open('w') as log:
        return subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
previous=json.loads((OUT/'state.json').read_text())
assert previous['status']=='error'
assert not (OUT/'test-stdout.txt').exists()
write('initial-preparation-error.json',previous)
call('docker','start',NAME)
env=[]
for key in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']: env += ['-e',key+'=http://host.docker.internal:7890']
base=['docker','exec',*env,'-e','REPO_ID=AgentOps-AI/agentops','-e','bugswarm_image_tag=AgentOps-AI-agentops-24579293289',NAME]
try:
    write('state.json',dict(status='preparing_dependencies',at=now()))
    prepare=f'''set -eu
set -a; . /etc/environment; set +a
export PIP_CONSTRAINT=/tmp/agentops-pip-constraints.txt PIP_INDEX_URL=https://pypi.org/simple
unset PIP_EXTRA_INDEX_URL
{PY} -m pip install tox==4.63.0 virtualenv==21.11.0
cd /home/github/build/failed/AgentOps-AI/agentops
{PY} -m tox -e py38,py39,py310,py311,py312 --workdir /opt/agentops-verifier-tox --notest
cd /home/github/build
export PATH=/root/.local/bin:/home/github/.local/bin:$PATH
uv init --python 3.10
uv add pytest==8.4.1
uv add pytest-json-ctrf==0.3.5
uv add unidiff==0.7.5
'''
    code=logged('prepare-r002.log',base+['bash','-lc',prepare],1800)
    assert code==0,f'Dependency preparation failed, code {code}'
    write('state.json',dict(status='verifier_running',at=now()))
    started=time.monotonic()
    code=logged('test-stdout.txt',base+['timeout','--signal=TERM','240','bash','/verifier/test.sh'],270)
    call('docker','cp',NAME+':/logs/verifier',str(OUT/'verifier-output'))
    # Preserve only tox logs/metadata, not multi-gigabyte installed dependencies.
    archive="cd /opt/agentops-verifier-tox && find . -type f \\( -path '*/log/*' -o -name '.tox-info.json' \\) -print0 | tar --null -T - -czf /tmp/tox-evidence.tar.gz"
    call('docker','exec',NAME,'bash','-c',archive)
    call('docker','cp',NAME+':/tmp/tox-evidence.tar.gz',str(OUT/'tox-evidence.tar.gz'))
    rewardfile=OUT/'verifier-output/reward.txt'
    reward=rewardfile.read_text().strip() if rewardfile.exists() else None
    provenance=json.loads((OUT/'provenance.json').read_text())
    provenance.update(finished_at=now(),verifier_process_exit_code=code,wall_time_sec=time.monotonic()-started,reward=reward)
    write('provenance.json',provenance)
    write('state.json',dict(status='complete' if code==0 and reward in ('0','1') else 'needs_attention',finished_at=now(),reward=reward,exit_code=code))
except Exception as exc:
    write('state.json',dict(status='error',at=now(),error=str(exc)))
    raise
finally:
    subprocess.run(['docker','stop',NAME],capture_output=True)
