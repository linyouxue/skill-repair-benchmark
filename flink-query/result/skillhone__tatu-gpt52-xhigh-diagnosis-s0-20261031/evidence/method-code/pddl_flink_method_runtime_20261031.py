"""Use the existing 60-step executor and accepted Tatu/archive/proxy hooks."""
from pathlib import Path
import json
import os
from pddl_flink_lane_20261031 import lane


def run_worker(request_file,response_file,original):
    request=json.loads(Path(request_file).read_text())
    response=Path(response_file)
    if response.exists():
        saved=json.loads(response.read_text())
        if Path(saved['result_json']).is_file():return
        raise RuntimeError('Existing response lost its native evidence; inspect before retry')
    if request['parent_iterations']!=60 or request['model']!='tatu/gpt-5.2' or request['reasoning_effort']!='xhigh':
        raise ValueError('PDDL/Flink protocol must remain GPT-5.2/xhigh/60')
    with lane(request['rollout_id']):
        import baseline_runtime as baseline
        baseline.EXECUTOR=Path(request['executor_root'])
        baseline.register_provider()
        os.environ.update(baseline.environment())
        baseline.install_hooks(Path(os.environ['SKILLHONE_SHARED_ROOT']))
        return original(request_file,response_file)
