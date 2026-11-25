#!/usr/bin/env python3
"""Same-config new attempts only after immutable reference/environment gates."""
import json,subprocess,sys,time,hashlib,importlib.util,threading,fcntl,os
from datetime import datetime,timezone
from pathlib import Path
B=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52');O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit')
spec=importlib.util.spec_from_file_location('stable_runner',B/'run_evals_stable.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=json.loads((O/'initial_audit.json').read_bytes());envmap={(r['kind'],r['prepared_id']):r for r in json.loads((B/'audits/environment-prebuild-stable.json').read_bytes())['records']}
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n');t.replace(p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reference_gate(image):
 candidates=[]
 for name in ['reference_acceptance.json','reference_google_corrected.json']:
  p=O/name
  if p.exists():candidates += [(r,p) for r in json.loads(p.read_bytes()).get('records',[]) if r['image']==image and r.get('passed')]
 return candidates[-1] if candidates else None
paths={'dialogue-parser':['/app/solution.py','/app/dialogue.json','/app/dialogue.dot'],'manufacturing-equipment-maintenance':['/app/output'],'sec-financial-report':['/root/answers.json'],'pddl-airport-planning':['/app/task01.txt','/app/task02.txt'],'video-silence-remover':['/root/compressed_video.mp4','/root/compression_report.json'],'flink-query':['/app/workspace/out.txt','/app/workspace/src/main/java','/app/workspace/target/LongestSessionPerJob-jar-with-dependencies.jar'],'data-to-d3':['/root/output'],'fix-build-google-auto':['/home/travis/build/failed/failed_reasons.txt']}
plan=[]
for r in source['entries']:
 flags={x['type'] for x in r['findings']};reasons=[]
 if 'api_or_model_response_error' in flags:reasons.append('recorded_api_non_200')
 if r['original_reward']<1 and flags & {'promise_without_followup','tool_command_in_final_text_not_executed'}:reasons.append('final_unperformed_action_and_task_failure')
 if reasons:plan.append({'experiment_id':r['experiment_id'],'kind':r['kind'],'task_id':r['task_id'],'old_attempt':r['attempt'],'old_result':r['formal_result'],'reasons':reasons,'status':'awaiting_reference_gate','new_attempts':[]})
registry=O/'rerun_registry.json'
if registry.exists():plan=json.loads(registry.read_bytes())['entries']
write(registry,{'protocol':'Same frozen setup; at most two NEW attempts per invalid condition (old attempt retained, total3). Normal valid failure never rerun for score. Any repeated anomaly remains unresolved after cap.','entries':plan})
# No paid model call before exact same image has passed reference acceptance.
equivalence=json.loads((O/'runtime_dependency_equivalence.json').read_bytes())
if not equivalence.get('complete') or len(equivalence['records'])!=55 or not all(r['equivalent'] for r in equivalence['records']):
 raise RuntimeError('Full actual runtime dependency comparison has not passed')
actual_refs=json.loads((O/'actual_runtime_reference_acceptance.json').read_bytes())
if not actual_refs.get('complete') or not all(r['passed'] for r in actual_refs['records']):
 raise RuntimeError('All actual runtime reference groups must pass before further model calls')
m.require_prebuilt_environments();m.require_executor_runtime();modelenv=m.execution_env()
key=m.read_api_key().encode()

def observe(attempt,task,stop):
 recorded=set()
 while not stop.is_set():
  for folder in (attempt/'jobs').glob('*/task__*'):
   name=folder.name+'-main-1'
   try:
    q=subprocess.run(['docker','inspect',name],env=modelenv,capture_output=True,text=True,timeout=10)
    if q.returncode:continue
    info=json.loads(q.stdout)[0];cid=info['Id']
    identity=O/'image_provenance'/attempt.parent.name/attempt.name/(folder.name+'.json')
    if not identity.exists():
     keep_tag='skilltta-audit-observed:'+hashlib.sha256((attempt.parent.name+'/'+attempt.name+'/'+folder.name).encode()).hexdigest()[:20]
     retained=subprocess.run(['docker','tag',info['Image'],keep_tag],env=modelenv,capture_output=True,text=True,timeout=20)
     image_info=subprocess.run(['docker','image','inspect',info['Image']],env=modelenv,capture_output=True,text=True,timeout=20)
     history=subprocess.run(['docker','history','--no-trunc','--format','{{.CreatedBy}}',info['Image']],env=modelenv,capture_output=True,text=True,timeout=20)
     write(identity,{'container_id':cid,'runtime_image_id':info['Image'],'retained_image_tag':keep_tag if retained.returncode==0 else None,'image_inspect':json.loads(image_info.stdout) if image_info.returncode==0 else None,'history':history.stdout,'capture_time':datetime.now(timezone.utc).isoformat()})

    # Trigger after model writes final ACP message or actual verifier starts.
    tr=folder/'trajectory/acp_trajectory.jsonl';tail=tr.read_text(errors='replace').splitlines()[-1:] if tr.exists() else []
    final=bool(tail and json.loads(tail[0]).get('type')=='agent_message')
    stage='agent_snapshot' if final else 'running'
    if stage=='running':continue
    signature=(cid,sha(tr))
    if signature in recorded:continue
    dest=O/'rerun_artifacts'/attempt.parent.name/attempt.name/folder.name/str(len(recorded)+1);dest.mkdir(parents=True,exist_ok=True)
    trace_hash=sha(tr);now=datetime.now(timezone.utc).isoformat();rows=[]
    for path in paths[task]:
     target=dest/path.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
     cmd=['docker','cp',name+':'+path,str(target)]
     p=subprocess.run(cmd,env=modelenv,capture_output=True,text=True,timeout=60)
     rows.append({'source_path':path,'copy_exit':p.returncode,'copy_error':p.stderr[:500],'destination':str(target) if p.returncode==0 else None,'collected_at':now})
    # Record actually loaded Skill files by read-only hashes, not a manifest assertion.
    command=['docker','exec',name,'python3','-c','import hashlib,json; from pathlib import Path; r=Path("/skills"); print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob("*") if p.is_file()}))']
    s=subprocess.run(command,env=modelenv,capture_output=True,text=True,timeout=30)
    write(dest/'SNAPSHOT.json',{'captured_at':now,'container_id':cid,'image_id':info['Image'],'acp_sha256_at_collection':trace_hash,'stage':stage,'artifacts':rows,'skill_hash_command':command,'skill_hash_exit':s.returncode,'skill_hashes':json.loads(s.stdout) if s.returncode==0 else None,'container_created':info.get('Created'),'not_created_by_auditor':True,'note':'Read-only docker cp/exec observer; collection time and final-message time may differ; do not infer all files predate end_turn without execution trace.'})
    recorded.add(signature)
   except Exception as ex:
    write(O/'observer-errors'/f'{attempt.parent.name}__{attempt.name}.json',{'error':repr(ex),'at':datetime.now(timezone.utc).isoformat()})
  stop.wait(1)

def classify(attempt):
 results=[]
 for p in (attempt/'jobs').glob('*/task__*/result.json'):
  d=json.loads(p.read_bytes());results.append((p,d))
 usable=[(p,d) for p,d in results if not any(d.get(k) for k in ['error','export_error','verifier_error','partial_trajectory','agent_timeout_info','api_error_info','transport_error_info','verifier_timeout_info','idle_timeout_info']) and isinstance((d.get('rewards') or {}).get('reward'),(int,float))]
 if len(usable)!=1:return {'valid':False,'reason':'no_unique_error_free_result','results':[str(p) for p,d in results]}
 p,d=usable[0];j=p.parent;acp=[json.loads(l) for l in (j/'trajectory/acp_trajectory.jsonl').read_text().splitlines() if l.strip()];llm=[json.loads(l) for l in (j/'trajectory/llm_trajectory.jsonl').read_text().splitlines() if l.strip()];messages=[x for x in acp if x.get('type')=='agent_message'];last=messages[-1].get('text','') if messages else ''
 reward=d['rewards']['reward'];bad_api=[i for i,x in enumerate(llm) if x.get('response',{}).get('status_code')!=200];future=__import__('re').search(r"\b(?:I[’']ll|I will|Next I|Let me)\b|接下来|马上",last,__import__('re').I)
 bad_tool=[x.get('tool_call_id') for x in acp if x.get('type')=='tool_call' and (not x.get('content') or x.get('status') not in ['completed','failed'])]
 ctrf=j/'verifier/ctrf.json';summary=json.loads(ctrf.read_bytes())['results']['summary'] if ctrf.exists() else {}
 reasons=[]
 if bad_api:reasons.append('api_non_200')
 if reward<1 and (future or __import__('re').search(r'"(?:command|recipient_name|recipient)"\s*:',last)):reasons.append('abnormal_final_promise_or_unperformed_text_call')
 if bad_tool:reasons.append('incomplete_tools')
 if summary.get('tests',0)<1 or summary.get('passed',0)+summary.get('failed',0)<1:reasons.append('no_executed_tests')
 return {'valid':not reasons,'reason':reasons,'reward':reward,'result_file':str(p),'final_message':last,'api_error_request_indices':bad_api,'test_summary':summary,'artifact_proof':'see rerun_artifacts; requires full audit before final adoption'}

with (O/'rerun.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for row in plan:
  if row['status'] in ['provisional_completed_requires_artifact_review','retry_cap_no_valid_result']:continue
  kind,id=row['kind'],row['experiment_id'];prepared=(m.PREPARED_ROOT if kind=='repaired' else m.PREPARED_CONTROLS_ROOT)/id;e=envmap[('repaired' if kind=='repaired' else 'control',id)];gate=reference_gate(e['image'])
  if not gate:row['status']='blocked_reference_not_passed';write(registry,{'entries':plan});continue
  accepted,path=gate;row['reference_evidence']=str(path);old=json.loads(Path(row['old_result']).parents[3].joinpath('RUN_RECORD.json').read_bytes()) if False else None
  for retry in range(len(row['new_attempts']),2):
   runroot=m.ROOT/'runs'/kind/id;attempt=m.next_attempt(runroot)
   digest=sha(prepared/'PREPARED_SHA256.json');record0=json.loads((Path(row['old_result']).parents[3]/'RUN_RECORD.json').read_bytes()) if (Path(row['old_result']).parents[3]/'RUN_RECORD.json').exists() else None
   link={'old_attempt':row['old_attempt'],'new_attempt':attempt.name,'old_result':row['old_result'],'reason':row['reasons'],'configuration_difference':{},'prepared_sha256':digest,'image':e['image'],'image_id':e['build']['image_id'],'reference_acceptance':str(path),'status':'running','budget_policy':'unchanged execution_env, original task agent/verifier timeouts and runner command; no feedback from previous attempts'}
   row['new_attempts'].append(link);row['status']='running';write(registry,{'entries':plan})
   cmd=[sys.executable,'-B',str(m.RUNNER),'eval','--prepared',str(prepared),'--jobs',str(attempt),'--agent','openhands','--model',m.ROUTE_MODEL,'--method',m.REPAIR_METHOD if kind=='repaired' else m.CONTROL_METHOD,'--bench',str(m.BENCH)]
   if kind=='repaired':cmd+=['--repair-model',m.REQUEST_MODEL]
   log=O/'rerun_logs'/f'{kind}__{id}__{attempt.name}.log';log.parent.mkdir(exist_ok=True)
   stopper=threading.Event();thread=threading.Thread(target=observe,args=(attempt,row['task_id'],stopper),daemon=True);thread.start()
   try:
    with log.open('wb') as f:r=subprocess.run(cmd,cwd=m.ROOT,env=modelenv,stdout=f,stderr=subprocess.STDOUT)
    link['runner_exit']=r.returncode;link['outcome']=classify(attempt) if r.returncode==0 else {'valid':False,'reason':'runner_exit_nonzero'}
   except Exception as ex:link['outcome']={'valid':False,'reason':repr(ex)}
   finally:stopper.set();thread.join(timeout=65)
   link['status']='closed';link['command']=cmd;link['log']=str(log);link['log_sha256']=sha(log)
   if attempt.exists():write(attempt/'STRICT_AUDIT_RERUN_LINK.json',link)
   if link['outcome']['valid']:row['status']='provisional_completed_requires_artifact_review';row['provisionally_selected_attempt']=attempt.name
   write(registry,{'entries':plan});print(json.dumps({'id':id,'attempt':attempt.name,'valid':link['outcome']['valid'],'reward':link['outcome'].get('reward'),'reason':link['outcome'].get('reason')}),flush=True)
   if link['outcome']['valid']:break
  if row['status']!='provisional_completed_requires_artifact_review':row['status']='retry_cap_no_valid_result';write(registry,{'entries':plan})
print(json.dumps({'audit_rerun_batch_finished':True,'registry':str(registry)}),flush=True)
