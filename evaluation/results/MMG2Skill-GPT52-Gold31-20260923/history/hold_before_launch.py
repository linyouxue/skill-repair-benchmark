"""Preserve the disk-gated launch; do not interrupt any worker or paid request."""
import json, os, signal
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent
state=json.loads((root/'batch_state.json').read_text())
assert not (root/'generation').exists() and not (root/'runs').exists()
assert all(row['phase'] in {'pending','blocked_disk','blocked_resource','blocked_protocol'} for row in state['tasks'].values())
pid=json.loads((root/'batch.pid').read_text())
proc=Path('/proc')/str(pid)
if proc.exists():
    command=(proc/'cmdline').read_bytes().split(b'\0')
    assert str(root/'experiment.py').encode() in command and b'--run' in command
    os.kill(pid,signal.SIGTERM)
state.update(status='blocked_before_paid_experiment',blocking_reason='C: has about 9.2GiB available; requires storage recovery before launch',experiment_model_calls=0,provider_probe_calls=1,updated_at=datetime.now(timezone.utc).isoformat())
(root/'batch_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
print('Launch held before all experiment requests; provider connectivity probe retained.')
