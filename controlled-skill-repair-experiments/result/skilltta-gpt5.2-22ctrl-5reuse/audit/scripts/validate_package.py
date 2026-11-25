import json,hashlib,csv,re
from pathlib import Path
B=Path(__file__).parent;D=B/'SkillTTA-GPT52-Controlled22-NoHint5';F=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52/final/SkillTTA-gpt52-tatumass-Controlled55');errors=[]
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
s=json.loads((D/'submission.json').read_text());assert len(s['tasks'])==22
trial_ids=[r['trial_id'] for r in s['tasks']]
counts={'location':sum(x.startswith('location-') for x in trial_ids),'single':sum(x.startswith('single-') and not x.endswith('-all') for x in trial_ids),'all_faults':sum(x.startswith('single-') and x.endswith('-all') for x in trial_ids)}
if counts!={'location':5,'single':12,'all_faults':5}:errors.append('Condition5/12/5 counts mismatch')
for r in s['tasks']:
 p=D/r['repaired_bundle'];origin=F/r['repaired_bundle']
 if not p.is_dir() or hashes(p)!=hashes(origin):errors.append(r['trial_id']+': changed/incomplete repaired bundle')
 if not list(p.rglob('SKILL.md')):errors.append(r['trial_id']+': SKILL.md absent')
 manifest=D/'tasks'/r['trial_id']/'CANDIDATE_SHA256.json'
 if manifest.exists() and hashes(p)!=json.loads(manifest.read_text()):errors.append(r['trial_id']+': candidate manifest mismatch')
 for stage in ['synthesis.json','diagnosis.json','repair_round_1.json','repair_round_2.json']:
  if not (D/'tasks'/r['trial_id']/'method_evidence'/stage).is_file():errors.append(r['trial_id']+': stage missing '+stage)
n=json.loads((D/'no_hint_controls/submission.json').read_text())
if len(n['tasks'])!=5:errors.append('No-hint count not5')
for r in n['tasks']:
 p=D/'no_hint_controls'/r['repaired_bundle']
 if not p.is_dir():errors.append('No-hint bundle link unresolved '+r['task_id'])
# Scan exact known API key without displaying it. Never redact or rewrite source evidence.
known=[]
keyfile=Path('/Users/king/Documents/Codex/2026-09-20/https-github-com-xiaolin9595-workflow-localized/opus47-wml.env')
if keyfile.exists() and not getattr(keyfile.stat(),'st_flags',0)&0x40000000:
 for line in keyfile.read_text().splitlines():
  if line.startswith('WML_API_KEY='):
   k=line.partition('=')[2].strip().strip('\"').strip("'")
   if len(k)>12:known.append(k.encode())
leaks=[];files=list(p for p in D.rglob('*') if p.is_file())
for p in files:
 if p.name.endswith('.env'):leaks.append(str(p.relative_to(D)));continue
 if p.stat().st_size<100000000:
  data=p.read_bytes()
  if any(k in data for k in known) or re.search(rb'sk-(?:or-v1-|ant-api03-)[A-Za-z0-9_-]{25,}',data):leaks.append(str(p.relative_to(D)))
if leaks:errors.append('Credential matches in copied files; delivery must not be published until safe source handling resolved')
report={'condition_counts':counts,'controlled_conditions':22,'no_hint_conditions':5,'repaired_bundles_byte_identical':not any('bundle' in e for e in errors),'file_count':len(files),'exact_known_secret_scan_performed':bool(known),'credential_matches':leaks,'package_structure_errors':errors,'package_structure_passed':not errors,'not_experiment_validity_certificate':True}
(D/'PACKAGE_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
