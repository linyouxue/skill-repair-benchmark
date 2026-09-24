"""Recompute both published scoring variants offline from saved judge responses."""
import copy, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'recomputed-gold-v1.4'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def score(tp,fp,fn):
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)

if __name__ == '__main__':
    # The frozen scorer intentionally refuses to overwrite existing evidence.
    suffix=1
    while OUT.exists() and any(OUT.iterdir()):
        suffix+=1
        OUT=ROOT/f'recomputed-gold-v1.4-{suffix:03d}'
    subprocess.run([sys.executable, str(ROOT/'evaluate_skill_diagnosis_repair.py'), '--gold',str(ROOT/'gold.json'),'--submission',str(ROOT/'submission.json'),'--judge-responses',str(ROOT/'gold-evaluation/judge_responses.json'),'--executor-results',str(ROOT/'executor-results.json'),'--output',str(OUT),'--max-input-chars','2000000'],check=True,cwd=ROOT)
    summary=read(OUT/'summary.json'); details=read(OUT/'details.json')
    index={t['task_id']:t for t in read(ROOT/'task-index.json')['tasks']}
    gold={t['task_id']:t for t in read(ROOT/'gold.json')['tasks']}
    adjusted=copy.deepcopy(details); overrides=[]
    for task in adjusted['tasks']:
        row=index[task['task_id']]; task['original_semantic_judgment_preserved']=True
        task['outcome_policy_overrides']=[]
        baseline=read(ROOT/row['original_run']/'benchmark_result.json')
        current=read(ROOT/row['selected_result'])
        if baseline['execution_ok'] is True and baseline['task_passed'] is False and current['execution_ok'] is True and current['task_passed'] is True:
            for kind in ('diagnosis','repair'): task['metrics'][kind]=score(task['gold_defect_count'],0,0)
            for defect in gold[task['task_id']]['defects']:
                entry=dict(task_id=task['task_id'],defect_id=defect['defect_id'],diagnosis='TP',repair='TP',policy='user_requested_all_gold_defects_for_valid_F_to_P',semantic_judgment_overwritten=False)
                task['outcome_policy_overrides'].append(entry); overrides.append(entry)
        tp=task['metrics']['diagnosis']['tp']
        task['metrics']['location_accuracy']=task['metrics']['location_correct_count']/tp if tp else None
    metrics=copy.deepcopy(summary['metrics'])
    for kind in ('diagnosis','repair'):
        metrics[kind]=score(*(sum(t['metrics'][kind][k] for t in adjusted['tasks']) for k in ('tp','fp','fn')))
    tp=metrics['diagnosis']['tp']; metrics['location_accuracy']=metrics['location_correct_count']/tp if tp else None
    policy=dict(policy='F_to_P_all_gold_defects_TP',not_a_semantic_rejudge=True,location_policy='original correct count divided by adjusted diagnosis TP',preserved=['judgments','confidence','review_items','regression','failed_gold_repair_count','harmful_extra_repair_count','possible_new_defect_count'],metrics=metrics,overridden_defects=overrides)
    adjusted['outcome_policy']=policy
    write(OUT/'outcome-adjusted-summary.json',policy); write(OUT/'outcome-adjusted-details.json',adjusted)
    assert summary['metrics']==read(ROOT/'final-review/original-semantic-summary.json')['metrics']
    assert metrics==read(ROOT/'final-review/outcome-adjusted-summary.json')['metrics']
    print('Both variants match published metrics. No API calls.')
