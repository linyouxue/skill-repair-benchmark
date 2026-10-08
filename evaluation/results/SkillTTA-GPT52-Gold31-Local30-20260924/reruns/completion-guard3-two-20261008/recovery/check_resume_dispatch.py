"""No-model check: resume only verified Organize, never redispatch finished Drone."""
import hashlib
from pathlib import Path

import experiment as runner

ROOT = Path(__file__).resolve().parent
state = runner.read(ROOT / 'batch_state.json')
plan = runner.read(ROOT / 'resume-plan.json')
assert plan['passed'] and not plan.get('consumed_at')
assert plan['batch_state_sha256'] == hashlib.sha256((ROOT / 'batch_state.json').read_bytes()).hexdigest()
rows = runner.read(ROOT / 'manifest.json')['tasks']
pending, skipped = [], []
for row in rows:
    saved = state['tasks'][row['slot']]
    run = Path(row['rerun_root']) / 'runs' / row['method_id'] / row['rollout_id']
    if saved['phase'] == 'finished':
        result = runner.read(run / 'benchmark_result.json')
        assert result['execution_ok'] and isinstance(result['task_passed'], bool)
        assert not any(result.get(k) for k in ['error', 'verifier_error', 'export_error'])
        assert Path(saved['result_path']) == run / 'benchmark_result.json'
        assert saved['fresh_rollout_id'] == row['rollout_id']
        for name in ['trajectory/acp_trajectory.jsonl', 'trajectory/llm_trajectory.jsonl', 'results.jsonl']:
            assert (run / name).is_file() and (run / name).stat().st_size > 0
        skipped.append(row['slot'])
    else:
        assert saved['phase'] == 'pending' and not run.exists()
        assert row['slot'] in plan['slots'] and plan['rollout_ids'][row['slot']] == row['rollout_id']
        assert runner.file_manifest(Path(row['rerun_root']) / 'submission/tasks' / row['task_id'] / 'skills') == row['bundle_sha256_by_file']
        proof = runner.read(Path(row['rerun_root']) / 'runtime-cache/organize-messy-files/prebuilt-image.json')
        assert proof['passed'] and proof['clean_output_directories'] and proof['model_calls'] == 0
        assert len(proof['input_sha256_by_file']) == 103
        pending.append(row['slot'])
assert pending == ['skilltta__organize-messy-files']
assert skipped == ['mmg2skill__drone-planning-control']
assert set(pending) == set(plan['slots'])
runner.write(ROOT / 'resume-dispatch-offline-check.json', {'at': runner.now(), 'passed': True,
             'pending_slots': pending, 'completed_slots_skipped': skipped, 'model_calls': 0,
             'parent_budget': 60, 'guard_limit': 3, 'prebuilt_original_input_count': 103,
             'no_existing_provider_attempt_to_resend': True, 'uses_launch_sh_for_controller_recovery': True})
print('Offline dispatch check passed: only Organize r002, completed Drone skipped')
