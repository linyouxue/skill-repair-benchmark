"""One-shot recovery for the already identified worker with missing launch environment."""
import json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TID='flink-query'
source=ROOT/'runs/mmg2skill-opus47-gold15-20260924'/f'{TID}-mmg2skill-opus47-r001/benchmark_result.json'
for _ in range(360):
 if source.exists():
  row=json.loads(source.read_text())
  if row.get('error')!='Local pinned OpenHands archive required' or row.get('provider_requests'):
   print('Terminal result differs from exact pre-model failure; no automatic recovery.',flush=True);break
  state=json.loads((ROOT/'batch_state.json').read_text())['tasks'][TID]
  if state.get('rollout')=='INFRA_ERROR':
   subprocess.run([sys.executable,str(ROOT/'recover_launch_environment.py')],check=True)
   break
 time.sleep(5)
else:print('Observation window ended; hourly workflow will inspect without restarting live build.',flush=True)
