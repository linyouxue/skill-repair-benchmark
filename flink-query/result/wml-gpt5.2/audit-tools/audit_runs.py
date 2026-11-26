import collections
import hashlib
import importlib.util
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
def read(path):
    return json.loads(path.read_text())
def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def tree(directory):
    return {str(p.relative_to(directory)): sha(p) for p in directory.rglob('*') if p.is_file()}
def body(record):
    value=record.get('body') or {}
    return value if isinstance(value,dict) else {}
def calls_in_response(response):
    for output in response.get('output') or []:
        if isinstance(output,dict) and output.get('type')=='function_call':
            yield output.get('call_id') or output.get('id')
    for choice in response.get('choices') or []:
        for call in (choice.get('message') or {}).get('tool_calls') or []:
            yield call.get('id')

frozen=tree(root/'frozen-skills')
assert frozen==tree(root/'candidate/skills')
canonical=root.parent/'skill-repair-benchmark/flink-query'
old_images={'repair-01':'0dd9c1fd6e1a','repair-03':'5d59c6bddfaf','repair-04':'ce7d928d0a17','scale-04':'13fc53986f25','stages-04':'fef91463d4d8','stages-07':'3ee9df792413','combined-04':'eb851425b096'}
rows=[]
for path in sorted((root/'jobs').glob('*/*/*/benchmark_result.json')):
    job=path.parent
    bid=job.name
    split=job.parent.parent.name
    task=root/'exports'/split/'tasks/flink-query'
    verifier=task/'verifier'
    for file in ('test.sh','native_grade.py','score_flink.py'):
        assert sha(verifier/file)==sha(canonical/'verifier'/file)
    for file in ('expected.json','negative_ids.json','stage_job_ids.json'):
        official=(canonical if split=='repair' else canonical/'evaluation'/split)/'verifier'/file
        assert sha(verifier/file)==sha(official)
    for stream in ('task_events','job_events'):
        filename=Path(stream)/'part-00001-of-00500.csv.gz'
        official=canonical/('environment/workspace/data' if split=='repair' else f'evaluation/{split}/inputs/data')/filename
        assert sha(official)==sha(task/'environment/workspace/data'/filename)
    b=read(path)
    raw=read(job/'result.json')
    config=read(job/'config.json')
    request=read(job/'executor_request.json')
    acp=lines(job/'trajectory/acp_trajectory.jsonl')
    llm=lines(job/'trajectory/llm_trajectory.jsonl')
    training=lines(job/'results.jsonl')
    acp_ids={v.get('tool_call_id') for v in acp if v.get('type')=='tool_call' and v.get('status') in ('completed','failed')}
    announced={k for call in llm for k in calls_in_response(body(call.get('response') or {})) if k}
    tool_responses={m.get('tool_call_id') or m.get('call_id') for call in llm for m in (body(call.get('request') or {}).get('messages') or [])+(body(call.get('request') or {}).get('input') or [] if isinstance(body(call.get('request') or {}).get('input'),list) else []) if isinstance(m,dict) and (m.get('role')=='tool' or m.get('type')=='function_call_output')}
    report_path=job/'verifier/accuracy.json'
    report=read(report_path) if report_path.is_file() else {}
    actual=job/'verifier/actual-flink.txt'
    ctrf_path=job/'verifier/ctrf.json'
    counts=read(ctrf_path)['results']['summary'] if ctrf_path.exists() else None
    rescored=None
    if actual.is_file():
        spec=importlib.util.spec_from_file_location('official_scorer',verifier/'score_flink.py')
        scorer=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scorer)
        rescored=scorer.score(actual,read(verifier/'expected.json'),read(verifier/'negative_ids.json'))
        assert rescored['accuracy']==report['accuracy']==b['reward']==float((job/'verifier/reward.txt').read_text())
        assert all(rescored[k]==report[k] for k in ('correct_items','total_items','delivery_issues','job_feedback','negative_feedback'))
    if report and 'reward' in report:
        assert report['reward']==b['reward']==float((job/'verifier/reward.txt').read_text())
    artifact_files=[p for p in (job/'artifacts').rglob('*') if p.is_file()]
    events=[dict(line=i, text=v.get('text'), outcome=v.get('stop_reason')) for i,v in enumerate(acp,1) if v.get('type') in ('agent_message','agent_iteration_outcome')]
    files=('config.json','executor_request.json','result.json','benchmark_result.json','results.jsonl','trajectory/acp_trajectory.jsonl','trajectory/llm_trajectory.jsonl','verifier/accuracy.json','verifier/ctrf.json','verifier/reward.txt','verifier/actual-flink.txt','verifier/maven.stdout','verifier/maven.stderr','verifier/flink.stdout','verifier/flink.stderr','verifier/test-stdout.txt')
    rows.append(dict(id=bid,split=split,model=b['model'],endpoint=b['provider_base_url'],agent=raw['agent'],
        reasoning_effort=config['reasoning_effort'],budget=raw['executor'].get('max_parent_iterations_per_step'),
        environment_image=f'flink-generalization:7621ba5-{split}',historical_image_id_prefix=old_images.get(bid.removeprefix('wml-flink-')),
        current_reference_image=(root/'audit'/f'reference-{split}'/'image.txt').read_text().split()[0],
        started=raw['started_at'],finished=raw['finished_at'],error=b['error'],error_category=b.get('error_category'),
        execution_ok=b['execution_ok'],passed=b['task_passed'],reward=b['reward'],
        verifier_seconds=raw['timing'].get('verifier'), verifier_error=b.get('verifier_error'),
        verifier_failure_class=report.get('failure_class'),verifier_tests=counts, stop=b.get('termination_reason'),
        actual_bytes=actual.stat().st_size if actual.is_file() else None,
        tuple_rows=sum(bool(re.fullmatch(r'\(\s*-?\d+\s*,\s*-?\d+\s*\)',line.strip())) for line in actual.read_text().splitlines()) if actual.is_file() else None,
        rescored={k:rescored[k] for k in ('correct_items','total_items','correct_jobs','total_jobs','correct_negative_jobs','negative_jobs','delivery_issues')} if rescored else None,
        exported_artifacts=[str(p.relative_to(job)) for p in artifact_files],
        request_model=b['model'], response_models=dict(collections.Counter(str(body(call.get('response') or {}).get('model') or (call.get('metadata') or {}).get('provider_model')) for call in llm)),
        llm_http=dict(collections.Counter(str((call.get('response') or {}).get('status_code')) for call in llm)),
        acp_lines=len(acp),llm_lines=len(llm),last_response_time=(llm[-1].get('response') or {}).get('timestamp') if llm else None,
        iterations=b['agent_iterations'],provider_requests=b['provider_requests'],tool_calls=raw['n_tool_calls'],
        unresolved_structured_calls=sorted(announced-acp_ids-tool_responses),training_ready=[x.get('info',{}).get('training_ready') for x in training],
        skill_snapshot_matches=tree(job/'inputs/skills')==frozen,
        skill_preload_matches=raw['executor'].get('skill_context_preload_matches_expected'),
        skill_bundle_sha256=raw['executor'].get('skill_bundle_sha256'),
        timeline=events[-2:], paths={str(job/f):sha(job/f) for f in files if (job/f).is_file()}))
(root/'audit'/'attempts.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print([(row['id'],row['llm_http'],row['unresolved_structured_calls'],row['tuple_rows']) for row in rows])
