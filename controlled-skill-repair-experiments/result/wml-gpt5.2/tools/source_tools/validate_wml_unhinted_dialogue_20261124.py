"""User-authorized cross-endpoint supplemental validation of frozen historical Skill."""
from pathlib import Path
import importlib.util,json,os,subprocess
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent
OUT=BASE/'wml-gpt52-completion-20261124'
LOCAL=Path('/private/tmp/controlled55-strict-20261123')
DATA=Path('/Users/king/Downloads/03_论文科研/skill-repair-controlled-datasets-20261020')
PY='/Users/king/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2))
def main():
 completion=module('completion',BASE/'complete_wml_gpt52_20261124.py');completion.qualify('dialogue-parser','wml-controlled55-ready:dialogue-parser')
 safe=completion.safe;runner=module('official_runner',DATA/'tools/runner.py');skills=OUT/'unhinted-reuse/dialogue-parser/repaired_skill';old=OUT/'unhinted-reuse/dialogue-parser/repaired_run/result.json';ex=json.loads(old.read_text())['executor'];assert safe.bundle_manifest(skills)['skill_bundle_sha256']==ex['skill_bundle_sha256']
 catalog=json.loads((DATA/'datasets/catalog.json').read_text());task=next(t for t in catalog['tasks'] if t['task_id']=='dialogue-parser')
 name='unhinted-dialogue-parser-frozen-skill-tatumass-validation';prepared=OUT/'prepared'/name
 if not prepared.exists():runner.prepare(DATA,task,None,skills,prepared,'unhinted_frozen_candidate_validation')
 attempt=OUT/'supplemental'/f'{name}-attempt-001';assert not attempt.exists(),attempt
 key=None
 for raw in (BASE.parent/'opus47-wml.env').read_text().splitlines():
  s=raw.strip().removeprefix('export ')
  if '=' in s:
   k,v=s.split('=',1)
   if k.strip() in ['API_KEY','WML_API_KEY']:key=v.strip().strip('"').strip("'")
 assert key
 env=dict(os.environ,PYTHONPATH=str(LOCAL/'runtime'),TATUMASS_API_KEY=key,TATUMASS_BASE_URL='https://maas.tatucloud.com/deployer/coding_tatu/v1',NO_PROXY='127.0.0.1,localhost,host.docker.internal',no_proxy='127.0.0.1,localhost,host.docker.internal')
 cmd=[PY,str(LOCAL/'method/safe_controlled_eval.py'),'--prepared',str(prepared),'--jobs',str(attempt),'--agent','openhands','--model','tatumass-openai/gpt-5.2@AZUREOPENAI-default','--method','WML-Historical-Unhinted-Frozen-Skill-Supplement-20261124','--bench',str(OUT/'bench.sh')]
 plan={'experiment_id':name,'task_id':'dialogue-parser','new_attempt':str(attempt),'old_historical_result':str(old),'authorization':'User explicitly approved Tatumass supplemental validation on 20261124, retain original Zenmux result','purpose':'Validate execution completeness using the exact historical WML repaired bundle; no new diagnosis/repair generation','model':'tatumass-openai/gpt-5.2@AZUREOPENAI-default','base_url':env['TATUMASS_BASE_URL'],'parent_budget':60,'skill_bundle':safe.bundle_manifest(skills),'old_endpoint':ex['provider_base_url'],'configuration_difference':'Provider and endpoint changed with explicit user authorization; original result remains separately recorded.','command':cmd,'started_at':datetime.now(timezone.utc).isoformat(),'finished_at':None}
 save(OUT/'UNHINTED_SUPPLEMENT_PLAN.json',plan);attempt.parent.mkdir(exist_ok=True)
 with (attempt.parent/(attempt.name+'.launcher.log')).open('w') as f:q=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 plan['finished_at']=datetime.now(timezone.utc).isoformat();plan['exit_code']=q.returncode;save(attempt/'ATTEMPT_LINK.json',plan);save(OUT/'UNHINTED_SUPPLEMENT_PLAN.json',plan);print('SUPPLEMENT_DONE',q.returncode,flush=True)
if __name__=='__main__':main()
