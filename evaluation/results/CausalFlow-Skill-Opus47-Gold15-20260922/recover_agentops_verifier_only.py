"""Restore exported patch/note on initial image; no model or trajectory replay."""
import hashlib,json,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'verifier-recovery-agentops-20260923'
SOURCE=ROOT/'runs/causalflow-skill-opus47-gold15-20260922/fix-build-agentops-causalflow-opus47-r001'
TASK=Path('/home/linyuanjing/skillgen-jobs/opus47-openrouter-v1.1-20260919/tasks/fix-build-agentops')
NAME='causalflow-agentops-verifier-recovery-20260923'
IMAGE='causalflow-gold15-fix-build-agentops:20260922'
OUT.mkdir(exist_ok=False)
def run(*args,**kw):
    x=subprocess.run(list(args),text=True,capture_output=True,**kw)
    if x.returncode: raise RuntimeError(f'{args[:3]}: {x.stderr[-1000:]} {x.stdout[-1000:]}')
    return x.stdout
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
patch=SOURCE/'verifier/diffs/AgentOps-AI/agentops/patch_1.diff'
note=SOURCE/'verifier/failed_reasons.txt'
provenance={'started_at':datetime.now(timezone.utc).isoformat(),'mode':'verifier-only from real exported deliverables','source_run':str(SOURCE),'patch_sha256':sha(patch),'note_sha256':sha(note),'original_verifier_sha256':{p.name:sha(p) for p in (TASK/'verifier').iterdir() if p.is_file()},'method_calls':0,'fresh_rollout_calls':0,'input_restoration':'Original source image plus byte-identical exported patch_1.diff applied with git apply, and exported failed_reasons. ACP confirms no other source/test edits; installation caches are not task answers. This is not a recovered full workspace snapshot.','environment_fix':'Add existing exact interpreter bin directories to /etc/environment PATH, because original run_passed.sh re-sources it. No new interpreter versions.'}
(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2))
run('docker','create','--name',NAME,'--cpus','4','--memory','4096m','--entrypoint','/bin/bash',IMAGE,'-c','sleep infinity')
run('docker','start',NAME)
run('docker','cp',str(TASK/'verifier'),NAME+':/verifier')
repo='/home/github/build/failed/AgentOps-AI/agentops'
run('docker','cp',str(patch),NAME+':'+repo+'/patch_1.diff')
run('docker','cp',str(note),NAME+':/home/github/build/failed/failed_reasons.txt')
paths=':'.join('/opt/hostedtoolcache/Python/'+ver+'/x64/bin' for ver in ['3.7.17','3.8.18','3.9.18','3.10.13','3.11.8','3.12.2'])
setup=f'''set -eu
cd {repo}
git apply --check patch_1.diff
git apply patch_1.diff
git diff -- agentops/langchain_callback_handler.py
mkdir -p /logs/verifier
test ! -e /tests && ln -s /verifier /tests
chmod 700 /verifier
printf '\\nPATH="{paths}:$PATH"\\n' >> /etc/environment
. /etc/environment
python3.7 --version
python3.8 --version
python3.9 --version
sha256sum patch_1.diff /home/github/build/failed/failed_reasons.txt
'''
(OUT/'setup.log').write_text(run('docker','exec',NAME,'bash','-lc',setup))
cmd=['docker','exec','-w','/home/github/build','-e','REPO_ID=AgentOps-AI/agentops','-e','bugswarm_image_tag=AgentOps-AI-agentops-24579293289']
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:cmd.extend(['-e',k+'=http://host.docker.internal:7890'])
cmd +=[NAME,'timeout','--signal=TERM','240','bash','/verifier/test.sh']
with (OUT/'test-stdout.txt').open('w') as log:
    process=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
run('docker','cp',NAME+':/logs/verifier',str(OUT/'verifier'))
provenance.update({'finished_at':datetime.now(timezone.utc).isoformat(),'verifier_process_exit_code':process.returncode,'reward':(OUT/'verifier/reward.txt').read_text().strip() if (OUT/'verifier/reward.txt').exists() else None,'container_name':NAME})
(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2))
run('docker','stop',NAME)
print(json.dumps(provenance))
