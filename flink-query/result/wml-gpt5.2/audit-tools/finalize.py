import json, statistics
from pathlib import Path

root = Path(__file__).resolve().parent
rows = json.loads((root/'attempts.json').read_text())
adopted = {'scale': 'wml-flink-scale-04', 'stages': 'wml-flink-stages-07', 'combined': 'wml-flink-combined-04'}
for row in rows:
    name = row['id']
    if name in adopted.values():
        row['audit_status'] = 'valid_fail'
    elif name == 'wml-flink-repair-04':
        row['audit_status'] = 'abnormal_end'
    elif row['error'] or any(code != '200' for code in row['llm_http']):
        row['audit_status'] = 'infrastructure_invalid'
    else:
        row['audit_status'] = 'manual_review_required'
if not any(row['id']=='wml-flink-repair-09' for row in rows):
    rows.append({'id':'wml-flink-repair-09','split':'repair','audit_status':'running'})
def select(key):
    return {row['split']:row['reward'] for row in rows if row['audit_status']==key}
scores=select('valid_fail')
refs={}
for split in ('repair','scale','stages','combined'):
    d=root/('reference-stages-r03' if split=='stages' else f'reference-{split}')
    refs[split]=dict(image=(d/'image.txt').read_text().split()[0],exit_code=int((d/'exit').read_text()),accuracy=float((d/'reward.txt').read_text()),evidence=str(d))
data = dict(
    task_id='flink-query', method='WML', expected_splits=4, valid_results=len(scores),
    valid_passes=0, valid_failures=len(scores), slots_without_valid_result=4-len(scores),
    infrastructure_invalid_attempts=sum(x['audit_status']=='infrastructure_invalid' for x in rows),
    abnormal_completion_attempts=sum(x['audit_status']=='abnormal_end' for x in rows),
    artifact_missing_scored_attempts=sum(x.get('actual_bytes') is None and x.get('verifier_tests') is not None for x in rows),
    completed_attempts=sum(x['audit_status']!='running' for x in rows), started_attempts=len(rows),
    audit_reruns_started=sum(x['id'] in ('wml-flink-repair-08','wml-flink-repair-08-retry02','wml-flink-repair-09') for x in rows),
    excluded_setup_launches=[{'launch':'repair-08-retry03','evidence':str(root/'repair-08-retry03.log'),'reason':'Tag removed by Docker teardown before rollout. Restored exact retained image and used repair-09.'}],
    reference_checks=refs, adopted_attempts=adopted, scores=scores,
    generalization_mean=statistics.mean(scores.values()), attempts=rows)
data.update(
    abnormal_trajectory_attempts=sum(
        row['audit_status']=='abnormal_end' or row.get('error_category')=='idle_timeout'
        for row in rows
    ),
    model_reruns_including_history=data['started_attempts']-data['expected_splits'],
    environment_tasks_passed=int(all(v['exit_code']==0 and v['accuracy']==1 for v in refs.values())),
)
data['environment_tasks_failed']=1-data['environment_tasks_passed']
(root/'audit-summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
