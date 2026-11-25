"""One same-config D3 confirmation for physically unparsable critical JavaScript."""
import json,time,sys,subprocess,fcntl
from pathlib import Path
L=Path(__file__).parent;O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit');S=L/'audit-evidence'
while True:
 reg=json.loads((O/'rerun_registry.json').read_text())
 if not any(r['status'] in ['running','awaiting_reference_gate','blocked_reference_not_passed'] for r in reg['entries']):
  with (O/'rerun.lock').open('a') as f:
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN);break
   except BlockingIOError:pass
 time.sleep(5)
r=next(x for x in reg['entries'] if x['experiment_id']=='location-data-to-d3');assert len(r['new_attempts'])==1
r['reasons'].append('normal_zero_score_critical_javascript_parser_rejection_one_remaining_confirmatory_attempt');r['status']='awaiting_reference_gate';r['confirmation_of']='attempt-005';r['adoption_policy']='First strictly normal valid result is retained; confirmation never replaces it for score.'
p=O/'rerun_registry.json.tmp';p.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');p.replace(O/'rerun_registry.json')
helpers=[]
for n in ['capture_verifier_and_patches.py','observe_skill_discovery_paths.py','preserve_new_attempts.py']:
 log=(L/('d3confirmation-helper-'+n+'.log')).open('ab');q=subprocess.Popen([sys.executable,str(L/n)],stdout=log,stderr=subprocess.STDOUT,cwd='/private/tmp');log.close();helpers.append({'name':n,'pid':q.pid})
(S/'d3_confirmation_plan.json').write_text(json.dumps({'reason':'User protocol prioritizes one same-config confirmation for critical missing/unparseable artifact when a predefined slot remains. Actual node --check and official browser both reject generated JS.','first_valid_attempt':'attempt-005','max_new_attempts_total':2,'same_frozen_configuration':True,'selection':'Retain first valid failure; preserve confirmation as separate measurement.','helpers':helpers},indent=2)+'\n')
q=subprocess.run([sys.executable,str(L/'frozen_rerun_invalid.py')],cwd='/private/tmp');print('D3 confirmation queue exit',q.returncode,flush=True)
