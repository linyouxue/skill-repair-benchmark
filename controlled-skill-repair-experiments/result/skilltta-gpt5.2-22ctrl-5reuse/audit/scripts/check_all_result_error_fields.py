"""Audit all actual result error/info channels, not only reward fields."""
import json
from pathlib import Path
L=Path(__file__).parent;S=L/'audit-evidence';O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit');R=Path('/Users/king/Documents/Codex/2026-11-18/skilltta-controlled-gpt52/runs');out=[];seen=set()
def inspect(p,id,outer,origin):
 if str(p) in seen:return
 seen.add(str(p));st=p.stat()
 if getattr(st,'st_flags',0)&0x40000000:out.append({'id':id,'outer_attempt':outer,'result':str(p),'evidence_unavailable':True});return
 d=json.loads(p.read_text());keys=[k for k in d if k=='error' or k.endswith('_error') or k.endswith('_error_category') or k.endswith('_timeout_info') or k in ['api_error_info','suspected_api_error_info','transport_error_info','sandbox_startup_info','partial_trajectory']];faults={k:d[k] for k in keys if d[k]};t=d.get('trajectory_summary') or {};nested={k:v for k,v in t.items() if k in ['partial_trajectory'] and v};out.append({'id':id,'outer_attempt':outer,'rollout':p.parent.name,'origin':origin,'result':str(p),'raw_rewards':d.get('rewards'),'error_fields':faults,'nested_trajectory_flags':nested,'all_error_channels_empty':not faults and not nested,'n_tool_calls':d.get('n_tool_calls'),'trajectory_tool_count':t.get('tool_call_steps'),'tool_counts_agree':d.get('n_tool_calls')==t.get('tool_call_steps'),'not_final_admission':'This checks only formal error channels; native trace/API/artifact/env/Skill evidence remain separate gates.'})
for r in json.loads((S/'initial_audit.json').read_text())['entries']:
 root=Path(r['formal_result']).parent.parents[2]
 for p in root.glob('jobs/*/task__*/result.json'):inspect(p,r['experiment_id'],r['attempt'],'original primary outer group including internal attempts')
reg=json.loads((O/'rerun_registry.json').read_text())
for r in reg['entries']:
 for a in r['new_attempts']:
  cache=L/'new-attempts'/r['kind']/r['experiment_id']/a['new_attempt'];root=cache if (cache/'AUDIT_PRESERVATION_SHA256.json').exists() else R/r['kind']/r['experiment_id']/a['new_attempt']
  for p in root.glob('jobs/*/task__*/result.json'):inspect(p,r['experiment_id'],a['new_attempt'],'new actual rollout')
(S/'all_result_error_channels.json').write_text(json.dumps({'entries':out,'formal_error_rollouts':sum(not r.get('all_error_channels_empty',False) and not r.get('evidence_unavailable',False) for r in out),'no_reward_based_validity':True},indent=2,ensure_ascii=False)+'\n');print('actual results',len(out),'with formal errors',sum(bool(r.get('error_fields')) or bool(r.get('nested_trajectory_flags')) for r in out),'tool count mismatches',[(r['id'],r.get('rollout')) for r in out if r.get('tool_counts_agree') is False])
