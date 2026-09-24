"""Offline scoring only. Report is provisional until genuine verifier/trajectory audit."""
import copy, json, subprocess, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,data): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def score(tp,fp,fn):
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
state=read(ROOT/'batch_state.json')
assert state['gold_evaluation']=='complete'
manifest=read(ROOT/'manifest.json'); sub=read(ROOT/'submission/submission.json')
registry={'method_id':sub['method_id'],'benchmark_version':sub['benchmark_version'],'tasks':[]}
for task in manifest['tasks']:
    row=state['tasks'][task['task_id']]
    if row.get('result_path'): registry['tasks'].append({'task_id':task['task_id'],'benchmark_result':row['result_path']})
out=ROOT/'final-review';write(out/'executor-results.json',registry)
args=[sys.executable,str(ROOT/'evaluate_skill_diagnosis_repair.py'),'--gold',str(ROOT/'gold.subset.json'),'--submission',str(ROOT/'submission/submission.json'),'--judge-responses',str(ROOT/'gold-evaluation/judge_responses.json'),'--output',str(out/'gold-v1.4'),'--max-input-chars','2000000']
if len(registry['tasks'])==len(sub['tasks']): args+=['--executor-results',str(out/'executor-results.json')]
if not (out/'gold-v1.4/summary.json').exists(): subprocess.run(args,check=True)
summary=read(out/'gold-v1.4/summary.json');details=read(out/'gold-v1.4/details.json')
byid={t['task_id']:t for t in details['tasks']};rows=[]
for task in manifest['tasks']:
    tid=task['task_id'];s=state['tasks'][tid]; baseline=read(Path(task['run_path'])/'benchmark_result.json')
    row={'task_id':tid,'phase':s['phase'],'outcome':s.get('rollout','NOT_RUN'),'baseline_passed':baseline.get('task_passed'),'f_to_p':False}
    if tid in byid:
        detail=byid[tid];row['gold_defects']=detail['gold_defect_count'];row['original_gold']=detail['metrics'];row['outcome_adjusted']=copy.deepcopy(detail['metrics'])
        row['f_to_p']=baseline.get('execution_ok') is True and baseline.get('task_passed') is False and row['outcome']=='PASS'
        if row['f_to_p']:
            for kind in ('diagnosis','repair'): row['outcome_adjusted'][kind]=score(detail['gold_defect_count'],0,0)
        # Independent adjudications, review/confidence, regressions and new defects stay unchanged.
        tp=row['outcome_adjusted']['diagnosis']['tp']
        row['outcome_adjusted']['location_accuracy']=detail['metrics']['location_correct_count']/tp if tp else None
    if s.get('result_path'):
        run=Path(s['result_path']).parent;raw=read(run/'result.json');result=read(run/'benchmark_result.json')
        row.update(n_skill_invocations=raw.get('n_skill_invocations'),skill_exposure_verified=result.get('skill_exposure_verified'),result_path=s['result_path'])
    rows.append(row)
adjusted=copy.deepcopy(summary['metrics'])
scored=[r for r in rows if 'outcome_adjusted' in r]
for kind in ('diagnosis','repair'): adjusted[kind]=score(*(sum(r['outcome_adjusted'][kind][k] for r in scored) for k in ('tp','fp','fn')))
tp=adjusted['diagnosis']['tp'];adjusted['location_accuracy']=adjusted['location_correct_count']/tp if tp else None
write(out/'report.json',{'status':'provisional_pending_verifier_and_trajectory_audit','original_summary':summary,'outcome_adjusted_metrics':adjusted,'execution_outcomes':dict(Counter(r['outcome'] for r in rows)),'unvalidated_task_ids':[r['task_id'] for r in rows if r['outcome'] not in ('PASS','FAIL')],'tasks':rows})
print('Offline original and F->P full-TP variants written; audit required before final claims.')
