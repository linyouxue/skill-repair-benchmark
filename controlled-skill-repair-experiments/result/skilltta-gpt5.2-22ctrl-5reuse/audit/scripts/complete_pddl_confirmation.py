"""Consume PDDL's one remaining same-config confirmation slot; retain original failure."""
import ast,json,hashlib,subprocess,sys,threading,importlib.util,fcntl
from pathlib import Path
from datetime import datetime,timezone
L=Path(__file__).resolve().parent;B=L.parents[1];O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit')
spec=importlib.util.spec_from_file_location('stable',B/'run_evals_stable.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');t.replace(p)
registry=O/'rerun_registry.json';reg=json.loads(registry.read_text());assert not any(r['status']=='running' for r in reg['entries'])
row=next(r for r in reg['entries'] if r['experiment_id']=='location-pddl-airport-planning');assert len(row['new_attempts'])==1,'Confirmation slot already consumed'
assert json.loads((L/'audit-evidence/resource_matched_reference_acceptance.json').read_text())['all_passed']
modelenv=m.execution_env();id=row['experiment_id'];prepared=m.PREPARED_ROOT/id;attempt=m.next_attempt(m.ROOT/'runs/repaired'/id)
prev=row['new_attempts'][0];cmd=list(prev['command']);cmd[cmd.index('--jobs')+1]=str(attempt)
assert prev['prepared_sha256']==sha(prepared/'PREPARED_SHA256.json')
namespace={'O':O,'paths':{'pddl-airport-planning':['/app/task01.txt','/app/task02.txt']},'modelenv':modelenv,'subprocess':subprocess,'json':json,'hashlib':hashlib,'datetime':datetime,'timezone':timezone,'write':write,'sha':sha}
tree=ast.parse((L/'frozen_rerun_invalid.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='observe');exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen-readonly-observer>','exec'),namespace)
with (O/'rerun.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 link={k:v for k,v in prev.items() if k in ['old_attempt','old_result','prepared_sha256','image','image_id','reference_acceptance','budget_policy']};link.update(new_attempt=attempt.name,status='running',reason=['same_configuration_confirmatory_rerun_of_normal_zero_score_invalid_serialized_plan_format'],configuration_difference={},confirmation_of=prev['new_attempt'],adoption_policy='Preserve first valid failure; confirmation is reported separately and never cherry-picked by reward.',command=cmd)
 row['new_attempts'].append(link);row['status']='running';write(registry,reg)
 stop=threading.Event();thread=threading.Thread(target=namespace['observe'],args=(attempt,'pddl-airport-planning',stop),daemon=True);thread.start();log=O/'rerun_logs'/('repaired__'+id+'__'+attempt.name+'.log')
 try:
  with log.open('wb') as f:q=subprocess.run(cmd,env=modelenv,cwd=m.ROOT,stdout=f,stderr=subprocess.STDOUT)
  link['runner_exit']=q.returncode;results=list(attempt.glob('jobs/*/task__*/result.json'));link['outcome']={'valid':False,'reason':'confirmation_requires_full_audit','results':[str(p) for p in results]}
  if results:
   d=json.loads(results[-1].read_text());link['outcome']['reward']=(d.get('rewards') or {}).get('reward');link['outcome']['result_file']=str(results[-1])
 finally:
  stop.set();thread.join(timeout=65);link['status']='closed';link['log']=str(log);link['log_sha256']=sha(log);row['status']='provisional_completed_requires_artifact_review';write(registry,reg)
  if attempt.exists():write(attempt/'STRICT_AUDIT_RERUN_LINK.json',link)
 print(json.dumps({'id':id,'attempt':attempt.name,'outcome':link['outcome']},ensure_ascii=False),flush=True)
