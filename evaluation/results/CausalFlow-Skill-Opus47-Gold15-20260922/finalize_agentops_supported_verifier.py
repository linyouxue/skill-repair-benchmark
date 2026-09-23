"""Validate recovered verifier evidence and publish a clearly labelled result overlay."""
import copy, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'verifier-recovery-agentops-supported-matrix-20260923'
SOURCE=ROOT/'runs/causalflow-skill-opus47-gold15-20260922/fix-build-agentops-causalflow-opus47-r001'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
state=read(OUT/'state.json')
assert state['status']=='complete' and state['exit_code']==0 and state['reward']=='0'
provenance=read(OUT/'provenance.json')
assert provenance['wall_time_sec'] < 240
for name in ['test.sh','test_outputs.py']:
    assert sha(OUT/'verifier-original'/name)==sha(OUT/'verifier-revised'/name)
assert sha(SOURCE/'verifier/diffs/AgentOps-AI/agentops/patch_1.diff')==provenance['patch_sha256']
assert sha(SOURCE/'verifier/failed_reasons.txt')==provenance['note_sha256']
tox=read(OUT/'verifier-output/tox-results.json')
environments=['py38','py39','py310','py311','py312']
matrix={}
for env in environments:
    evidence=tox['testenvs'][env]
    assert all(command['retcode']==0 for command in evidence['setup'])
    assert not evidence['result']['skipped'] and evidence['result']['exit_code']==1
    tests=evidence['test']
    assert len(tests)==1 and tests[0]['retcode']==1
    assert '1 failed, 9 passed' in tests[0]['output']
    assert 'TestEvents.test_record_timestamp' in tests[0]['output']
    assert 'assert event.init_timestamp != event.end_timestamp' in tests[0]['output']
    matrix[env]=dict(python=evidence['python']['version'],passed=9,failed=1,setup_success=True,
        failure='tests/test_events.py::TestEvents::test_record_timestamp',test_duration=tests[0]['elapsed'])
ctrf=read(OUT/'verifier-output/ctrf.json')['results']
assert ctrf['summary']['tests']==3 and ctrf['summary']['passed']==2 and ctrf['summary']['failed']==1
result=copy.deepcopy(read(SOURCE/'benchmark_result.json'))
result.update(execution_ok=True,task_passed=False,reward=0.0,error=None,error_category=None,
    verifier_error=None,verifier_error_category=None,protocol_revision='agentops-supported-python-v1',
    verifier_matrix_complete=True,verifier_matrix=environments,
    verifier_recovery_wall_time_sec=provenance['wall_time_sec'],
    verifier_result_json=str(OUT/'verifier-output/ctrf.json'),
    audit_source_benchmark_result=str(SOURCE/'benchmark_result.json'),
    recovery_provenance=str(OUT/'provenance.json'),
    original_six_environment_protocol_status='INFRA_ERROR; retained unchanged',
    execution_protocol_note='Only verifier environment matrix revised: py37-py312 to py38-py312. Not a pure infrastructure fix under the original six-environment protocol.')
write(OUT/'benchmark_result.json',result)
request=read(SOURCE/'executor_request.json')
request['verifier_recovery']={'protocol_revision':result['protocol_revision'],'provenance':str(OUT/'provenance.json'),'no_new_model_calls':True}
write(OUT/'executor_request.json',request)
write(OUT/'matrix-verification.json',dict(status='valid_fail_under_revised_matrix',matrix=matrix,
    outer_verifier_summary=ctrf['summary'],new_model_calls=0,new_gold_calls=0,
    original_protocol_retained=True))
print(json.dumps(matrix,indent=2))
