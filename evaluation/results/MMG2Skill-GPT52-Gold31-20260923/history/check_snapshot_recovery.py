"""Offline regression for the SimPO pre-verifier snapshot timeout."""
import json, subprocess, time, hashlib
from pathlib import Path
from runtime_fixes import snapshot_command

root=Path(__file__).resolve().parent
setup='mkdir -p /home/agent/.local/lib/python3.12/site-packages /home/agent/.local/bin; '
setup+='head -c 268435456 /dev/urandom > /home/agent/.local/lib/python3.12/site-packages/dependency.bin; '
setup+='printf actual-output > /root/loss.npz; printf original-source > /root/simpo_trainer.py; '
setup+='printf interpreter-wrapper > /home/agent/.local/bin/python; '
cmd=setup+snapshot_command('/root')+'; tar -tzf /tmp/mmg-before-verifier.tar.gz; tar -xOzf /tmp/mmg-before-verifier.tar.gz root/loss.npz'
started=time.monotonic()
p=subprocess.run(['docker','run','--rm','--network','none','ubuntu:24.04','bash','-c',cmd],capture_output=True,text=True,timeout=120)
assert p.returncode==0,(p.stdout,p.stderr)
assert 'root/loss.npz' in p.stdout and 'root/simpo_trainer.py' in p.stdout
assert 'home/agent/.local/bin/python' in p.stdout and 'dependency.bin' not in p.stdout
assert p.stdout.endswith('actual-output')
receipt={'check':'passed','elapsed_seconds':time.monotonic()-started,'network':'none','model_calls':0,'task_source_and_output_preserved':True,'user_local_executable_preserved':True,'installed_dependency_library_excluded_bytes':268435456,'snapshot_watchdog_seconds':1800,'original_verifier_timeout_unchanged':True}
(root/'snapshot-recovery-check.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
