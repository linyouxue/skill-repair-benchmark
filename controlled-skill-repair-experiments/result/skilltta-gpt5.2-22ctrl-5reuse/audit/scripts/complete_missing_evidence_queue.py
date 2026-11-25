"""Recollect unavailable execution proof, same frozen conditions, finite retry cap."""
import json,sys,subprocess,time
from pathlib import Path
L=Path(__file__).parent;S=L/'audit-evidence';O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit')
while True:
 reg=json.loads((O/'rerun_registry.json').read_text())
 if not any(e['status']=='running' for e in reg['entries']):break
 time.sleep(5)
initial=json.loads((S/'initial_audit.json').read_text());live=json.loads((S/'live_audit_report.json').read_text());existing={e['experiment_id'] for e in reg['entries']};added=[]
for e in live['entries']:
 if e['kind']!='repaired' or e['validity']!='historical_evidence_insufficient' or e['experiment_id'] in existing:continue
 old=next(x for x in initial['entries'] if x['experiment_id']==e['experiment_id'])
 added.append({'experiment_id':e['experiment_id'],'kind':'repaired','task_id':e['task_id'],'old_attempt':old['attempt'],'old_result':old['formal_result'],'reasons':['historical_required_actual_image_or_artifact_provenance_unavailable_not_certifiable_under_user_strict_audit'],'status':'awaiting_reference_gate','new_attempts':[],'eligibility':'Evidence-unavailable result is not certified valid. User explicitly requests completing these 22 conditions; recollect proof with unchanged Skill/model/budget, at most two new attempts; never rerun a strictly admitted normal failure for its score.'})
reg['entries'].extend(added);tmp=O/'rerun_registry.json.next';tmp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');tmp.replace(O/'rerun_registry.json');(S/'historical_evidence_recollection_plan.json').write_text(json.dumps({'added_conditions':added,'no_score_based_selection':True},ensure_ascii=False,indent=2)+'\n')
print('Added evidence recollection conditions',len(added),flush=True)
helpers=[]
for name in ['capture_verifier_and_patches.py','observe_skill_discovery_paths.py','preserve_new_attempts.py','preserve_finished_inner_rollouts.py','mirror_live_raw_records.py','observe_flink_evidence.py','observe_runtime_profiles.py','observe_installed_dependencies.py']:
 p=L/name
 if not p.exists():continue
 log=(L/('recollection-helper-'+name+'.log')).open('ab');q=subprocess.Popen([sys.executable,str(p)],stdout=log,stderr=subprocess.STDOUT,cwd='/private/tmp');helpers.append({'script':str(p),'pid':q.pid});log.close()
(S/'recollection_helpers.json').write_text(json.dumps(helpers,indent=2)+'\n')
q=subprocess.run([sys.executable,str(L/'frozen_rerun_invalid.py')],cwd='/private/tmp');print('Evidence recollection runner exit',q.returncode,flush=True)
