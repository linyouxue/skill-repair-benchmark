"""Audit new attempts and five reused runs; do not alter scores or source artifacts."""
from pathlib import Path
import hashlib,importlib.util,json,re,sys,zipfile
BASE=Path(__file__).resolve().parent
OUT=BASE/'wml-gpt52-completion-20261124'
OLD=BASE/'controlled55-strict-audit-20261123'
spec=importlib.util.spec_from_file_location('safe',Path('/private/tmp/controlled55-strict-20261123/method/safe_controlled_eval.py'));safe=importlib.util.module_from_spec(spec);spec.loader.exec_module(safe)
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(path,expected=None,skills=None):
 d=load(path);root=path.parent;acp=root/'trajectory/acp_trajectory.jsonl';provider=root/'trajectory/llm_trajectory.jsonl';errors={k:d.get(k) for k in ['error','verifier_error','export_error','partial_trajectory','api_error_info','transport_error_info','idle_timeout_info','agent_timeout_info','verifier_timeout_info'] if d.get(k)}
 events=[json.loads(s) for s in acp.read_text().splitlines() if s.strip()] if acp.exists() else [];requests=[json.loads(s) for s in provider.read_text().splitlines() if s.strip()] if provider.exists() else []
 tools={e['tool_call_id']:e for e in events if e.get('type')=='tool_call'};last=max((i for i,e in enumerate(events) if e.get('type')=='tool_call'),default=-1);final='\n'.join(e.get('text','') for e in events[last+1:] if e.get('type')=='agent_message');ex=d.get('executor',{});reward=(d.get('rewards') or {}).get('reward');issues=[]
 pending=[k for k,e in tools.items() if e.get('status') not in ['completed','failed']]
 fake=bool(re.search(r'"(?:security_risk|tool_uses|recipient_name|tool_name|command)"\s*:',final));future=bool(re.search(r"\bI(?:[’']ll| will)\s+(?:now\s+)?(?:execute|continue|create|write|save|run|inspect|check|extract|generate)\b",final,re.I));abnormal=ex.get('stop_reason')=='end_turn' and (fake or future)
 http=[];response_errors=[];pcalls={};returns=set()
 for i,q in enumerate(requests):
  response=q.get('response',{});body=response.get('body',{});request=q.get('request',{}).get('body',{})
  if response.get('status_code')!=200:http.append({'line':i+1,'status':response.get('status_code')})
  if body.get('error') or body.get('incomplete_details'):response_errors.append({'line':i+1,'error':body.get('error'),'incomplete_details':body.get('incomplete_details')})
  for t in body.get('output',[]):
   if t.get('type')=='function_call':pcalls[t['call_id']]=t.get('name')
  for t in request.get('messages',request.get('input',[])):
   if t.get('type')=='function_call_output':returns.add(t.get('call_id'))
   if t.get('role')=='tool':returns.add(t.get('tool_call_id'))
 unmatched=[k for k,n in pcalls.items() if n!='finish' and k not in tools and k not in returns]
 network=[{'event':i,'title':e.get('title')} for i,e in enumerate(events) if e.get('type')=='tool_call' and re.search(r'No address associated with hostname|Failed to establish a new connection|NewConnectionError|Temporary failure in name resolution|Could not resolve host|502 Bad Gateway|503 Service Unavailable',json.dumps(e,ensure_ascii=False),re.I)]
 ctrfpath=root/'verifier/ctrf.json';ctrf=load(ctrfpath) if ctrfpath.exists() else {};tests=ctrf.get('results',{}).get('tests',[]);testsummary=ctrf.get('results',{}).get('summary',{});failed=[t for t in tests if t.get('status')=='failed'];rewardfile=root/'verifier/reward.txt';actualreward=float(rewardfile.read_text()) if rewardfile.exists() else None
 if errors:issues.append('formal_result_error')
 if not requests or not events:issues.append('missing_trace')
 if http or response_errors:issues.append('provider_error')
 if pending or unmatched:issues.append('unmatched_tool_or_pending_call')
 if abnormal:issues.append('premature_end_turn')
 if network and reward!=1:issues.append('unresolved_tool_network_error')
 if not tests or actualreward!=reward:issues.append('incomplete_or_inconsistent_verifier')
 compatibility=any('Node is not an HTMLElement' in t.get('trace','') for t in failed)
 if compatibility:issues.append('SVG_verifier_error')
 config=[]
 if expected:
  for k,need in [('model',expected['model']),('provider_base_url',expected['base_url']),('max_parent_iterations_per_step',60),('skill_bundle_sha256',expected['skill_bundle']['skill_bundle_sha256'])]:
   if ex.get(k)!=need:config.append(k)
  pre=load(path.parents[3]/'EXECUTION_PREFLIGHT.json')
  if pre['validated_prebuilt_image']!=expected['image']:config.append('image')
  snapshot=root/'inputs/skills'
  if snapshot.exists() and safe.bundle_manifest(snapshot)!=expected['skill_bundle']:config.append('skill_files')
 if skills and skills.exists():
  if safe.bundle_manifest(skills)['skill_bundle_sha256']!=ex.get('skill_bundle_sha256'):config.append('historical_repaired_skill_hash')
 if config:issues.append('configuration_mismatch')
 if not ex.get('prompt_runs') or any(x.get('iterations_used',61)>60 for x in ex.get('prompt_runs',[])):issues.append('iteration_accounting_unverified')
 status='invalid' if issues else 'valid_pass' if reward==1 else 'valid_fail'
 archived=[]
 for prefix in [root/'observed-task-outputs',root/'artifacts/task-outputs']:
  for p in prefix.rglob('*'):
   if not p.is_file():continue
   item={'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'parser':None,'readable':True}
   try:
    if p.suffix=='.json':x=load(p);item.update(parser='json',type=type(x).__name__,length=len(x) if isinstance(x,(dict,list)) else None)
    elif p.suffix=='.jar':
     with zipfile.ZipFile(p) as z:item.update(parser='zipfile',bad_member=z.testzip())
   except Exception as e:item.update(readable=False,error=str(e))
   archived.append(item)
 return {'status':status,'reward':reward,'issues':issues,'config_mismatch_fields':config,'formal_errors':errors,'http_errors':http,'response_errors':response_errors,'pending_tools':pending,'unmatched_provider_tools':unmatched,'network_error_events':network,'last_tool_event':last,'final_text':final,'model':ex.get('model'),'base_url':ex.get('provider_base_url'),'budget':ex.get('max_parent_iterations_per_step'),'stop_reason':ex.get('stop_reason'),'prompt_runs':ex.get('prompt_runs'),'skill_hash':ex.get('skill_bundle_sha256'),'result_path':str(path),'result_sha256':sha(path),'acp_path':str(acp),'provider_path':str(provider),'verifier_path':str(root/'verifier'),'verifier_summary':testsummary,'failed_tests':failed,'reward_file_matches':actualreward==reward,'archived_output_files':archived,'historical_provenance_limit':'Historical provider/source environment differences are disclosed; no independent human-review claim.'}

def main():
 plans=load(OUT/'ATTEMPT_PLAN.json') if (OUT/'ATTEMPT_PLAN.json').exists() else [];rows=[]
 if (OUT/'INFRASTRUCTURE_RETRY_PLAN.json').exists():
  overrides={p['experiment_id']:p for p in load(OUT/'INFRASTRUCTURE_RETRY_PLAN.json')};plans=[overrides.get(p['experiment_id'],p) for p in plans]
 for plan in plans:
  attempt=Path(plan['new_attempt']);reports=[]
  for p in attempt.glob('jobs/*/*/result.json'):
   try:reports.append(audit(p,plan))
   except Exception as e:reports.append({'result_path':str(p),'status':'audit_read_error','error':repr(e)})
  finished=(attempt/'ATTEMPT_LINK.json').exists();valid=[r for r in reports if r['status'] in ['valid_pass','valid_fail']]
  rows.append({'experiment_id':plan['experiment_id'],'finished':finished,'verifier_version':plan['verifier_version'],'attempt':str(attempt),'internal_rollouts':reports,'selected':valid[0] if len(valid)==1 and finished else None})
 (OUT/'NEW_ATTEMPT_AUDIT.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 supplementary=OUT/'UNHINTED_SUPPLEMENT_PLAN.json'
 if supplementary.exists():
  plan=load(supplementary);attempt=Path(plan['new_attempt']);reports=[]
  for p in attempt.glob('jobs/*/*/result.json'):
   pre=load(attempt/'EXECUTION_PREFLIGHT.json');expected={**plan,'image':pre['validated_prebuilt_image']}
   try:reports.append(audit(p,expected))
   except Exception as e:reports.append({'result_path':str(p),'status':'audit_read_error','error':repr(e)})
  valid=[r for r in reports if r['status'] in ['valid_pass','valid_fail']];finished=(attempt/'ATTEMPT_LINK.json').exists()
  report={'plan':plan,'finished':finished,'internal_rollouts':reports,'selected':valid[0] if finished and len(valid)==1 else None}
  (OUT/'UNHINTED_SUPPLEMENT_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('SUPPLEMENT',finished,report['selected']['status'] if report['selected'] else None,flush=True)
 published=OUT/'unhinted_local_published_integrity.json'
 if published.exists() and load(published)['all_verified']:
  unhinted=[]
  for tid in ['dialogue-parser','data-to-d3','flink-query','manufacturing-equipment-maintenance','pddl-airport-planning']:
   root=OUT/'unhinted-reuse'/tid
   try:r=audit(root/'repaired_run/result.json',skills=root/'repaired_skill');r['task_id']=tid;unhinted.append(r)
   except Exception as e:unhinted.append({'task_id':tid,'status':'audit_read_error','error':repr(e)})
  (OUT/'UNHINTED_REUSE_AUDIT.json').write_text(json.dumps(unhinted,ensure_ascii=False,indent=2))
  print('UNHINTED',[(r['task_id'],r['status'],r.get('issues')) for r in unhinted],flush=True)
 print('NEW',[(r['experiment_id'],r['finished'],r['selected']['status'] if r['selected'] else None) for r in rows],flush=True)

if __name__=='__main__':main()
