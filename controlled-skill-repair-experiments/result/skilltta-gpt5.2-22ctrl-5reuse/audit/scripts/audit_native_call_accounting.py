"""Cross-check every SDK-native function call and ACP response, including terminal finish."""
import json,gzip,hashlib,re
from pathlib import Path
L=Path(__file__).parent;S=L/'audit-evidence';O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit');initial=json.loads((S/'initial_audit.json').read_text());reg=json.loads((O/'rerun_registry.json').read_text());cases=[];seen=set()
def stream(p):
 if not p.exists():p=p.with_suffix(p.suffix+'.gz')
 if not p.exists() or getattr(p.stat(),'st_flags',0)&0x40000000:return None
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(l) for l in f if l.strip()]
def review(id,attempt,job,origin):
 key=(id,attempt,job.name)
 if key in seen:return
 seen.add(key);acp=stream(job/'trajectory/acp_trajectory.jsonl');llm=stream(job/'trajectory/llm_trajectory.jsonl')
 if acp is None or llm is None:cases.append({'id':id,'outer_attempt':attempt,'rollout':job.name,'origin':origin,'trajectory_evidence_gap':True});return
 tools={e.get('tool_call_id'):(i,e) for i,e in enumerate(acp) if e.get('type')=='tool_call'};messages=[(i,e) for i,e in enumerate(acp) if e.get('type')=='agent_message'];final=messages[-1][1].get('text','') if messages else '';calls=[];unmatched=[];finish=[];statuses=[]
 for request_index,x in enumerate(llm):
  body=x.get('response',{}).get('body',{});statuses.append({'request_index':request_index,'timestamp':x.get('request',{}).get('timestamp'),'callback_status':x.get('response',{}).get('status_code'),'response_status':body.get('status'),'response_error':bool(body.get('error'))})
  for c in body.get('output',[]):
   if c.get('type')!='function_call':continue
   cid=c.get('call_id');event=tools.get(cid);r={'call_id':cid,'name':c.get('name'),'request_index':request_index,'timestamp':x.get('request',{}).get('timestamp'),'has_acp_tool_result':event is not None}
   if event:r.update(acp_event_index=event[0],acp_status=event[1].get('status'),acp_content_present=bool(event[1].get('content')))
   else:
    try:args=json.loads(c.get('arguments','{}'))
    except:args={}
    if c.get('name')=='finish' and args.get('message') and args['message'] in final:r['maps_to_terminal_agent_message']=True;finish.append(r)
    else:unmatched.append(r)
   calls.append(r)
 native_ids={r['call_id'] for r in calls};acp_not_native=[{'call_id':cid,'event_index':i,'title':e.get('title'),'status':e.get('status')} for cid,(i,e) in tools.items() if cid not in native_ids];pending=[{'call_id':cid,'event_index':i,'status':e.get('status'),'content_present':bool(e.get('content'))} for cid,(i,e) in tools.items() if e.get('status') not in ['completed','failed'] or not e.get('content')];last=llm[-1] if llm else {};lastbody=last.get('response',{}).get('body',{});case={'id':id,'outer_attempt':attempt,'rollout':job.name,'origin':origin,'acp_path':str(job/'trajectory/acp_trajectory.jsonl'),'llm_path':str(job/'trajectory/llm_trajectory.jsonl'),'acp_events':len(acp),'native_calls':calls,'mapped_finish_control_actions':finish,'unmatched_actual_function_calls':unmatched,'acp_calls_without_visible_native_call':acp_not_native,'pending_acp_tools':pending,'has_terminal_agent_message':bool(messages),'final_event_index':messages[-1][0] if messages else None,'final_visible_message':final,'final_callback_request_timestamp':last.get('request',{}).get('timestamp'),'final_provider_completed_at':lastbody.get('completed_at'),'final_response_status':lastbody.get('status'),'callback_records':statuses,'bad_callback_indices':[s['request_index'] for s in statuses if s['callback_status']!=200 or s['response_error'] or s['response_status'] in ['failed','incomplete','cancelled']],'future_action_language_candidate':bool(re.search(r"\b(?:I[’']ll|I will|Next I|Let me)\b|接下来|马上",final,re.I)),'textual_pseudotool_candidate':bool(re.search(r'"(?:command|recipient_name|recipient|parameters)"\s*:',final)),'no_unpaired_calls':not unmatched and not pending,'automated_flags_only':'Future language/tool text require semantic review with actual artifacts; optional suggestions may be legitimate. SDK callbacks are not raw HTTP. Missing ACP timestamps not invented.'};cases.append(case)
for r in initial['entries']:
 root=Path(r['formal_result']).parent.parents[2]
 for j in root.glob('jobs/*/task__*'):
  if (j/'result.json').exists():review(r['experiment_id'],r['attempt'],j,'original primary outer group including invalid internal retries')
for r in reg['entries']:
 for a in r['new_attempts']:
  root=L/'new-attempts'/r['kind']/r['experiment_id']/a['new_attempt']
  if not (root/'AUDIT_PRESERVATION_SHA256.json').exists():continue
  for j in root.glob('jobs/*/task__*'):
   if (j/'result.json').exists():review(r['experiment_id'],a['new_attempt'],j,'new actual completed rollout')
(S/'native_call_accounting.json').write_text(json.dumps({'entries':cases,'case_count':len(cases),'unmatched_call_cases':sum(bool(r.get('unmatched_actual_function_calls')) for r in cases),'pending_tool_cases':sum(bool(r.get('pending_acp_tools')) for r in cases),'AI_assisted_not_human':True},ensure_ascii=False,indent=2)+'\n');print('rollouts',len(cases),'unmatched native',sum(bool(r.get('unmatched_actual_function_calls')) for r in cases),'pending ACP',sum(bool(r.get('pending_acp_tools')) for r in cases),'gaps',sum(bool(r.get('trajectory_evidence_gap')) for r in cases))
