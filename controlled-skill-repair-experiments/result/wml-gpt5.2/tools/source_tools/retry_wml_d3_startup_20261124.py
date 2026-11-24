"""Retry one model-unstarted infrastructure-invalid control after import acceptance."""
from pathlib import Path
from datetime import datetime,timezone
import copy,json,os,subprocess,sys
BASE=Path(__file__).resolve().parent
OUT=BASE/'wml-gpt52-completion-20261124'
def save(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2))
def main():
 probe=json.loads((OUT/'environment-acceptance/data-to-d3/startup-import-probe.json').read_text());assert probe['exit_code']==0
 abnormal='--confirm-abnormal' in sys.argv
 original=(json.loads((OUT/'INFRASTRUCTURE_RETRY_PLAN.json').read_text())[0] if abnormal else next(p for p in json.loads((OUT/'ATTEMPT_PLAN.json').read_text()) if p['experiment_id']=='data-to-d3__original'));old=Path(original['new_attempt'])
 results=[json.loads(p.read_text()) for p in old.glob('jobs/*/*/result.json')]
 if abnormal:
  assert old.name.endswith('attempt-004'), 'One model-abnormal confirmation only; do not repeat automatically.'
  review=next(r for r in json.loads((OUT/'NEW_ATTEMPT_AUDIT.json').read_text()) if r['experiment_id']=='data-to-d3__original')
  assert review['finished'] and review['selected'] is None and all('premature_end_turn' in r['issues'] for r in review['internal_rollouts'])
 else:
  assert results and all(r['n_tool_calls']==0 and r['executor']['stop_reason']=='infrastructure_error' for r in results)
  for trace in old.glob('jobs/*/*/trajectory/llm_trajectory.jsonl'):assert not trace.read_text().strip()
 plan=copy.deepcopy(original);n=int(old.name.rsplit('-',1)[1])+1;dest=old.with_name('data-to-d3__original-attempt-'+f'{n:03d}');assert not dest.exists()
 plan['old_attempts'] += [str(old)];plan['new_attempt']=str(dest);cmd=plan['command'];cmd[cmd.index('--jobs')+1]=str(dest);plan.update(started_at=datetime.now(timezone.utc).isoformat(),finished_at=None,exit_code=None,reason='Prior run timed out in preinstalled runtime import probe before any model call; unchanged accepted image warmed/probed successfully; one bounded infrastructure retry.')
 if abnormal:plan['reason']='Prior same-version control claimed further work but ended after 3 tools; one bounded model-abnormal confirmation under existing strict audit rule, same frozen Skill, endpoint, budget and verifier. Do not retry normal completed valid failures.'
 save(OUT/'INFRASTRUCTURE_RETRY_PLAN.json',[plan]);key=None
 for raw in (BASE.parent/'opus47-wml.env').read_text().splitlines():
  s=raw.strip().removeprefix('export ')
  if '=' in s:
   k,v=s.split('=',1)
   if k.strip() in ['API_KEY','WML_API_KEY']:key=v.strip().strip('"').strip("'")
 assert key
 env=dict(os.environ,PYTHONPATH='/private/tmp/controlled55-strict-20261123/runtime',TATUMASS_API_KEY=key,TATUMASS_BASE_URL=plan['base_url'],NO_PROXY='127.0.0.1,localhost,host.docker.internal',no_proxy='127.0.0.1,localhost,host.docker.internal')
 with (dest.parent/(dest.name+'.launcher.log')).open('w') as f:q=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 plan['exit_code']=q.returncode;plan['finished_at']=datetime.now(timezone.utc).isoformat();save(dest/'ATTEMPT_LINK.json',plan);save(OUT/'INFRASTRUCTURE_RETRY_PLAN.json',[plan]);print('INFRA_RETRY_DONE',q.returncode,flush=True)
if __name__=='__main__':main()
