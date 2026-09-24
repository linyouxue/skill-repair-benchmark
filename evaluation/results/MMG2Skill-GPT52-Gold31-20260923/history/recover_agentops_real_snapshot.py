"""No-model verifier recovery from the actual MMG workspace; original evidence stays intact."""
import datetime, hashlib, json, os, subprocess, time, tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OPUS=ROOT.parent/'opus47-gold15-20260924'
OUT=ROOT/'verifier-recovery-agentops-real-snapshot-20260924'
RUN=ROOT/'runs/mmg2skill-gpt52-gold31-20260923/fix-build-agentops-mmg2skill-gpt52-r001'
TASK=Path(json.loads((ROOT/'manifest.json').read_text())['tasks_root'])/'fix-build-agentops'
NAME='mmg-agentops-verifier-snapshot-20260924'
IMAGE='sha256:5b0c1c98d55c67b47fcc57bd39680f4eedb335ddee3cab48d296bd168e80d98b'
PY='/opt/hostedtoolcache/Python/3.11.8/x64/bin/python'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2)+'\n')
def call(*args):
 r=subprocess.run(args,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-1500:]+r.stdout[-1500:])
 return r.stdout
def logged(name,args,timeout):
 with (OUT/name).open('w') as log:return subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
OUT.mkdir(exist_ok=False)
write('state.json',dict(status='waiting_resource',pid=os.getpid(),at=now()))
# Opus pending dispatch is held; never interrupt a live rollout.
while True:
 state=json.loads((OPUS/'batch_state.json').read_text()); specs={s['task_id']:s for s in json.loads((OPUS/'preflight.json').read_text())['tasks']}; active=[]
 for tid,row in state['tasks'].items():
  try:cmd=Path('/proc/'+str(row.get('worker_pid'))+'/cmdline').read_bytes()
  except OSError:continue
  if str(OPUS/'experiment.py').encode() in cmd and b'--worker' in cmd:active.append(specs[tid])
 if len(active)<3 and sum(s['memory_mb'] for s in active)+4096<=11264 and not any(s['exclusive'] for s in active):break
 time.sleep(5)
snapshot=RUN/'artifacts/workspace-before-verifier.tar.gz'
with tarfile.open(snapshot) as t:
 members=[m for m in t.getmembers() if m.isfile() and m.name.startswith('home/github/build/failed/')]
 evidence={m.name:hashlib.sha256(t.extractfile(m).read()).hexdigest() for m in members}
write('source-workspace-files.json',evidence)
write('provenance.json',dict(source_run=str(RUN),snapshot=str(snapshot),snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),image=IMAGE,model_calls=0,verifier_timeout_sec=240,source_files=len(evidence),verifier_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (TASK/'verifier').iterdir() if p.is_file()},dependency_only_preparation=True,started_at=now()))
try:
 write('state.json',dict(status='restoring_real_workspace',pid=os.getpid(),at=now()))
 call('docker','create','--name',NAME,'--cpus','4','--memory','4096m','--entrypoint','/bin/bash',IMAGE,'-c','sleep infinity')
 call('docker','start',NAME)
 call('docker','cp',str(snapshot),NAME+':/tmp/real-workspace.tar.gz')
 call('docker','cp',str(TASK/'verifier'),NAME+':/verifier')
 call('docker','exec',NAME,'bash','-lc','set -eu; tar -xzf /tmp/real-workspace.tar.gz -C / home/github/build --no-same-owner; mkdir -p /logs/verifier; ln -s /verifier /tests')
 paths=':'.join('/opt/hostedtoolcache/Python/'+v+'/x64/bin' for v in ['3.11.8','3.8.18','3.9.18','3.10.13','3.12.2'])
 env=[]
 for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:env+=['-e',k+'=http://host.docker.internal:7890']
 env+=['-e','NO_PROXY=localhost,127.0.0.1,host.docker.internal','-e','REPO_ID=AgentOps-AI/agentops','-e','bugswarm_image_tag=AgentOps-AI-agentops-24579293289','-e','TOX_WORK_DIR=/opt/mmg-agentops-verifier-tox','-e','VIRTUALENV_NO_PERIODIC_UPDATE=1']
 base=['docker','exec',*env,NAME]
 setup=f'''set -eu
export PATH={paths}:/root/.local/bin:/usr/local/bin:/usr/bin:/bin
cat > /tmp/agentops-pip-constraints.txt <<'EOF'
langchain==0.0.352
langchain-core==0.1.23
EOF
export PIP_CONSTRAINT=/tmp/agentops-pip-constraints.txt PIP_INDEX_URL=https://pypi.org/simple
unset PIP_EXTRA_INDEX_URL
date -u
{PY} -m pip install tox
cd /home/github/build/failed/AgentOps-AI/agentops
{PY} -m tox -e py38,py39,py310,py311,py312 --notest
date -u
cd /home/github/build
uv init --python 3.10
uv add pytest==8.4.1
uv add pytest-json-ctrf==0.3.5
uv add unidiff==0.7.5
date -u
'''
 write('state.json',dict(status='dependency_preparation',pid=os.getpid(),at=now()))
 code=logged('prepare.log',base+['bash','-lc',setup],1800)
 assert code==0,f'Dependency preparation failed: {code}; no scored verifier retry started'
 write('state.json',dict(status='verifier_running',pid=os.getpid(),at=now()))
 started=time.monotonic()
 code=logged('test-stdout.txt',base+['timeout','--signal=TERM','240','bash','-lc','cd /home/github/build && bash /verifier/test.sh'],270)
 call('docker','cp',NAME+':/logs/verifier',str(OUT/'verifier-output'))
 # Preserve tox diagnostics independently even when the official wrapper buffers them.
 call('docker','exec',NAME,'bash','-lc',"cd /opt/mmg-agentops-verifier-tox; find . -type f \\( -path '*/log/*' -o -name '.tox-info.json' \\) -print0 | tar --null -T - -czf /tmp/tox-evidence.tar.gz")
 call('docker','cp',NAME+':/tmp/tox-evidence.tar.gz',str(OUT/'tox-evidence.tar.gz'))
 reward_path=OUT/'verifier-output/reward.txt';reward=reward_path.read_text().strip() if reward_path.exists() else None
 write('state.json',dict(status='complete' if code==0 and reward in ('0','1') else 'needs_attention',pid=os.getpid(),exit_code=code,reward=reward,elapsed_sec=time.monotonic()-started,at=now()))
except Exception as exc:
 write('state.json',dict(status='error',pid=os.getpid(),error=str(exc),at=now()));raise
finally:
 subprocess.run(['docker','stop',NAME],capture_output=True)
