"""Readable rerun chain/config comparisons derived from immutable raw attempts."""
import json
from pathlib import Path
W=Path(__file__).parent;D=W/'SkillTTA-GPT52-Controlled22-NoHint5';L=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124');S=L/'audit-evidence';live=json.loads((S/'live_audit_report.json').read_text());by={r['experiment_id']:r for r in live['entries']};reg=json.loads((L/'rerun_registry.json').read_text());out=[]
fields=['agent','model','environment','sandbox_user','skill_mode','skill_source','include_task_skills','timeout_sec','agent_idle_timeout_sec','concurrency','loop','sandbox_setup_timeout','agent_install_timeout','task_digest','agent_env','scenes']
def read(p):
 p=Path(p)
 if not p.exists() or getattr(p.stat(),'st_flags',0)&0x40000000:return None
 return json.loads(p.read_text())
for r in reg['entries']:
 if r['kind']!='repaired':continue
 e=by[r['experiment_id']];oldcfg=read(Path(e['original_result_path']).parent/'config.json');previous=r['old_attempt'];previous_outcome=None
 for a in r['new_attempts']:
  root=L/'new-attempts/repaired'/r['experiment_id']/a['new_attempt'];configs=[]
  for p in root.glob('jobs/*/task__*/config.json'):
   c=read(p)
   if c is None:continue
   diffs={f:{'old':oldcfg.get(f),'new':c.get(f)} for f in fields if oldcfg and oldcfg.get(f)!=c.get(f)}
   configs.append({'config_path':str(p),'model':c.get('model'),'agent':c.get('agent'),'wall_budget':c.get('timeout_sec'),'idle_budget':c.get('agent_idle_timeout_sec'),'endpoint':c.get('agent_env',{}).get('LLM_BASE_URL'),'compared_fields':fields,'configuration_differences':diffs if oldcfg else None})
  reason=a.get('reason',[])
  if a.get('confirmation_of') or ('confirm' in str(reason).lower()):trigger='protocol_confirmatory_rerun_of_normal_critical_artifact_failure'
  elif previous_outcome:trigger=previous_outcome.get('reason')
  else:trigger=reason
  out.append({'experiment_id':r['experiment_id'],'primary_original_attempt':r['old_attempt'],'trigger_attempt':a.get('confirmation_of') or previous,'new_attempt':a['new_attempt'],'trigger_reason':trigger,'recorded_source_reason':reason,'prior_outcome':previous_outcome,'new_status':a['status'],'new_outcome':a.get('outcome'),'runner_exit':a.get('runner_exit'),'prepared_sha256':a.get('prepared_sha256'),'source_recorded_config_difference':a.get('configuration_difference'),'independent_visible_config_comparisons':configs,'all_compared_configs_identical':bool(configs) and all(c['configuration_differences']=={} for c in configs),'configuration_absent_is_not_assumed_equal':not bool(configs),'retained_raw_attempt_path':'tasks/'+r['experiment_id']+'/attempts/'+a['new_attempt'],'final_adopted_attempt':e.get('adopted_attempt'),'final_adopted_reward':e.get('adopted_reward'),'all_previous_attempts_retained':True,'scope_note':'Config equality is configured settings only. Actual image/resources/dependencies and Skill file hashes have separate admission evidence; unlogged wire fields not inferred.'});previous=a['new_attempt'];previous_outcome=a.get('outcome') or {'status':a['status'],'reason':'Raw interrupted/failed attempt retained; see source link and logs.'}
(D/'RERUN_MAP.json').write_text(json.dumps({'entries':out,'derived_not_raw_replacement':True},ensure_ascii=False,indent=2)+'\n');print('Mapped',len(out),'scoped new attempts','nonidentical_or_missing',sum(not r['all_compared_configs_identical'] for r in out))
