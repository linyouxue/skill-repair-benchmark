"""No-model regression: resume dispatches reserves once and preserves four results."""
import asyncio
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import experiment as runner

real_root = runner.ROOT
manifest = runner.read(real_root / 'manifest.json')
original = runner.read(real_root / 'recovery-history/reserves-apt-proxy-drop-20261008/batch_state.json')
slot = 'skilltta__reserves-at-risk-calc'
row = next(r for r in manifest['tasks'] if r['slot'] == slot)
finished = {s: copy.deepcopy(v) for s, v in original['tasks'].items() if v['phase'] == 'finished'}
dispatched = []


class SimulatedProcess:
    pid = 999999999

    def __init__(self, argv, **kwargs):
        dispatched.append(argv[argv.index('--worker') + 1])

    def poll(self):
        return 0


original_iterdir = Path.iterdir
original_check_output = runner.subprocess.check_output


def safe_iterdir(path):
    return iter(()) if path == Path('/proc') else original_iterdir(path)


def safe_check_output(argv, **kwargs):
    return '' if argv[:2] == ['docker', 'ps'] else original_check_output(argv, **kwargs)


with tempfile.TemporaryDirectory(prefix='guard3-resume-no-model-') as directory:
    runner.ROOT = Path(directory)
    (runner.ROOT / 'worker_logs').mkdir()
    original['tasks'][slot] = {'phase': 'pending', 'rollout': 'pending'}
    runner.write(runner.ROOT / 'manifest.json', manifest)
    runner.write(runner.ROOT / 'batch_state.json', original)
    runner.write(runner.ROOT / 'preflight.json', {'model_probe': True})
    runner.write(runner.ROOT / 'resume-plan.json', {
        'passed': True, 'slots': [slot], 'rollout_ids': {slot: row['rollout_id']},
        'batch_state_sha256': hashlib.sha256((runner.ROOT / 'batch_state.json').read_bytes()).hexdigest(),
    })
    with patch.object(Path, 'iterdir', safe_iterdir), patch.object(runner, 'external_workers', return_value=[]), patch.object(runner.subprocess, 'Popen', SimulatedProcess), patch.object(runner.subprocess, 'check_output', safe_check_output):
        asyncio.run(runner.controller(resume=True))
        assert dispatched == [slot], dispatched
        state = runner.read(runner.ROOT / 'batch_state.json')
        assert {s: state['tasks'][s] for s in finished} == finished
        try:
            asyncio.run(runner.controller(resume=True))
        except AssertionError as exc:
            assert 'unconsumed' in str(exc)
        else:
            raise AssertionError('Consumed plan dispatched a second attempt')
    runner.ROOT = real_root
runner.write(real_root / 'resume-dispatch-offline-check.json', {
    'passed': True, 'dispatched_slots': dispatched, 'completed_slots_unchanged': list(finished),
    'second_resume_rejected': True, 'model_calls': 0, 'real_workers_started': 0,
})
print(json.dumps({'passed': True, 'only_reserves_dispatched': True, 'four_completed_unchanged': True, 'second_resume_rejected': True, 'model_calls': 0}))
