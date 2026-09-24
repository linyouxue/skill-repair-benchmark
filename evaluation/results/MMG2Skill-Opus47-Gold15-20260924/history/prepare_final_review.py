"""Offline preparation and structural verification before semantic adjudication."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXECUTOR=ROOT.parents[2]/'skill-repair-benchmark'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def local(s):return Path(s.replace('/mnt/c/','C:/',1)) if sys.platform=='win32' else Path(s)
state=read(ROOT/'batch_state.json');manifest=read(ROOT/'manifest.json')
assert len(state['tasks'])==15 and all(t['phase']=='finished' and t['rollout'] in ('PASS','FAIL') for t in state['tasks'].values())
out=ROOT/'final-review';out.mkdir(exist_ok=True)
old=read(ROOT/'monitoring/20260924T0253-structure.json')
already={Path(x['root'].replace('\\','/')).name for x in old['rollouts'] if x['healthy']}
remaining=[local(t['result_path']).parent for t in state['tasks'].values() if local(t['result_path']).parent.name not in already]
target=out/'remaining-structure.json'
if not target.exists():
 result=subprocess.run([sys.executable,'-X','utf8',str(EXECUTOR/'.agents/skills/benchflow-experiment-review/scripts/validate_run_artifacts.py'),*map(str,remaining),'--json'],capture_output=True,text=True,encoding='utf-8')
 target.write_text(result.stdout,encoding='utf-8');assert result.returncode==0,result.stderr
more=read(target);assert more['healthy'] and old['healthy']
write(out/'structure-audit.json',{'healthy':True,'checked':15,'reports':['../monitoring/20260924T0253-structure.json','remaining-structure.json'],'rollouts':old['rollouts']+more['rollouts']})
rows=[];integrity=[]
for t in manifest['tasks']:
 tid=t['task_id'];adapter=read(ROOT/'generation'/tid/'adapter_result.json');assert adapter['status']=='complete'
 original=local(t['original_bundle']);bundle=ROOT/'submission/tasks'/tid/'skills'
 src={p.relative_to(original).as_posix():p for p in original.rglob('*') if p.is_file()};dst={p.relative_to(bundle).as_posix():p for p in bundle.rglob('*') if p.is_file()}
 assert set(src)==set(dst),tid
 changed=[rel for rel in src if src[rel].read_bytes()!=dst[rel].read_bytes()]
 assert all(Path(rel).name=='SKILL.md' for rel in changed),tid
 assert sorted(changed)==sorted(adapter['updated_files']),tid
 run=local(state['tasks'][tid]['result_path']).parent;br=read(run/'benchmark_result.json');raw=read(run/'result.json')
 assert br['execution_ok'] and not any(br.get(k) for k in ('error','verifier_error','export_error'))
 assert (run/'artifacts/workspace-before-verifier.tar.gz').stat().st_size>0
 integrity.append({'task_id':tid,'files':len(src),'changed_skill_files':changed,'n_skill_invocations':raw.get('n_skill_invocations'),'skill_exposure_verified':br.get('skill_exposure_verified'),'model':br['model'],'snapshot_bytes':(run/'artifacts/workspace-before-verifier.tar.gz').stat().st_size})
 rows.append(adapter['submission_row'])
write(out/'bundle-and-exposure-audit.json',{'tasks':integrity,'only_existing_skill_md_changed':True})
submission={'method_id':'mmg2skill-opus47-gold15-20260924','benchmark_version':manifest['benchmark_version'],'tasks':rows}
path=ROOT/'submission/submission.json'
if path.exists():assert read(path)==submission
else:write(path,submission)
gold=read(ROOT/'gold.full.json');ids={r['task_id'] for r in rows};gold['tasks']=[t for t in gold['tasks'] if t['task_id'] in ids]
assert len(gold['tasks'])==15 and sum(len(t['defects']) for t in gold['tasks'])==32
path=ROOT/'gold.subset.json'
if path.exists():assert read(path)==gold
else:write(path,gold)
print(json.dumps({'structure_checked':15,'bundles':15,'gold_defects':32,'paid_calls':0}))
