"""Finalize only the 22 repaired condition dispositions from strict recorded gates."""
import json,csv
from pathlib import Path
W=Path(__file__).parent;D=W/'SkillTTA-GPT52-Controlled22-NoHint5';L=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124');S=L/'audit-evidence';live=json.loads((S/'live_audit_report.json').read_text());normal=json.loads((S/'normal_rollout_adjudication.json').read_text())['entries'];registry=json.loads((L/'rerun_registry.json').read_text());byreg={r['experiment_id']:r for r in registry['entries']};rows=[]
for old in [e for e in live['entries'] if e['kind']=='repaired']:
 id=old['experiment_id'];reg=byreg.get(id);strict={(x['outer_attempt'],x['rollout']):x for x in normal if x['id']==id and x['strict_valid_run']};chosen=None
 for link in (reg or {}).get('new_attempts',[]):
  match=next((x for (attempt,rollout),x in strict.items() if attempt==link['new_attempt'] and x.get('raw_reward') is not None),None)
  if match:chosen=match;break
 if chosen:
  attempt=chosen['effective_attempt_id'];reward=chosen['raw_reward'];status='valid_pass' if reward==1 else 'valid_failure';basis='first strictly admitted new attempt by registry order'
 elif id=='location-dialogue-parser':status='verifier_semantics_disputed';attempt=None;reward=None;basis='End false-negative independently reproduced; original score preserved, no model-failure attribution'
 elif id in ['location-manufacturing-equipment-maintenance','location-pddl-airport-planning']:
  status='historical_resource_evidence_insufficient';attempt=None;reward=None;basis='Normal task outcome bytes/score retained but actual model cgroup profile is unavailable; not strict-adoptable'
 elif reg and reg.get('status')=='retry_cap_no_valid_result':status='retry_cap_no_valid_result';attempt=None;reward=None;basis='Invalid attempts reached the two-new-attempt cap; no valid result'
 elif old['validity']=='historical_evidence_insufficient':status='historical_evidence_insufficient';attempt=None;reward=None;basis='Required historical/actual environment/artifact evidence is unavailable'
 elif old['validity']=='verifier_semantics_disputed':status='verifier_semantics_disputed';attempt=None;reward=None;basis='Verifier semantics prevent model-failure attribution'
 else:status='no_strict_valid_result_pending_adjudication';attempt=None;reward=None;basis='No strictly admitted rollout in retained evidence'
 rows.append({'trial_id':id,'task_id':old['task_id'],'condition':old.get('condition'),'audit_status':status,'adopted_attempt':attempt,'adopted_reward':reward,'raw_historical_reward':old['original_reward_unmodified'],'repaired_bundle':'tasks/'+id+'/repaired_skill','evidence':'tasks/'+id+'/audit.json','decision_basis':basis,'first_strict_candidate':chosen['effective_attempt_id'] if chosen else None,'first_strict_candidate_reward':chosen['raw_reward'] if chosen else None})
assert len(rows)==22
counts={k:sum(x['audit_status']==k for x in rows) for k in sorted({x['audit_status'] for x in rows})};assert sum(counts.values())==22
with (D/'controlled22_results.json').open('w') as f:json.dump({'entries':rows},f,ensure_ascii=False,indent=2);f.write('\n')
with (D/'controlled22_results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
sub=json.loads((D/'submission.json').read_text())
for x in sub['tasks']:
 r=next(z for z in rows if z['trial_id']==x['trial_id']);x.update(executor_run_id=r['adopted_attempt'],adopted_reward=r['adopted_reward'],audit_status=r['audit_status'],audit_basis=r['decision_basis'])
(D/'submission.json').write_text(json.dumps(sub,ensure_ascii=False,indent=2)+'\n');summary={'conditions':22,'categories':counts,'strict_valid_results':sum(x['audit_status'] in ['valid_pass','valid_failure'] for x in rows),'strict_passes':sum(x['audit_status']=='valid_pass' for x in rows),'strict_failures':sum(x['audit_status']=='valid_failure' for x in rows),'no_adoptable_result':sum(x['audit_status'] not in ['valid_pass','valid_failure'] for x in rows),'rule':'First strictly valid eligible attempt by registry order; no cherry-picking by reward. Nonvalid confirmation/replays remain archived.'};(D/'SCOPE22_FINAL_STATUS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
