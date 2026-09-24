"""One-time authorized fresh-only recovery; adopt all healthy workers."""
import json,os,signal,shutil,subprocess,time
from pathlib import Path
from datetime import datetime,timezone

r=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
def write(p,x):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
tid='simpo-code-reproduction'
old=r/'runs/mmg2skill-gpt52-gold31-20260923'/f'{tid}-mmg2skill-gpt52-r001'
rid=f'{tid}-mmg2skill-gpt52-r002'
assert not (old.parent/rid).exists(), 'Recovery already launched; do not repeat'
assert read(r/'snapshot-recovery-check.json')['check']=='passed'
b=read(old/'benchmark_result.json')
assert b['verifier_error']=='verifier crashed: Command timed out after 240 seconds'
assert not list((old/'artifacts').iterdir()) and not list((old/'verifier').iterdir())
assert read(r/'generation'/tid/'adapter_result.json')['status']=='complete'
pid=int((r/'batch.pid').read_text())
cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes()
assert str(r/'experiment.py').encode() in cmd and b'--resume-queue' in cmd
os.kill(pid,signal.SIGSTOP)
replaced=False
try:
    state=read(r/'batch_state.json')
    assert state['tasks'][tid]['rollout']=='INFRA_ERROR'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-simpo-snapshot-recovery')
    dest=r/'recovery-history'/stamp;dest.mkdir(parents=True)
    for p in [r/'batch_state.json',r/'recovery_queue.json',r/'task_state'/f'{tid}.json',old/'benchmark_result.json',old/'result.json',r/'snapshot-recovery-check.json']:
        name='task_state.json' if p.parent.name=='task_state' else p.name
        shutil.copy2(p,dest/name)
    reason='Snapshot tar exceeded 240s before verifier; no artifact export and original container deleted. Exclude installed user-site libraries, gzip level 1, packaging-only 1800s watchdog checked offline. Reuse completed method/bundle; fresh-only r002; original verifier unchanged.'
    q=read(r/'recovery_queue.json');q[tid]={'reason':reason,'stage':'fresh','fresh_rollout_id':rid};write(r/'recovery_queue.json',q)
    write(dest/'recovery.json',{'task_id':tid,'reason':reason,'old_run_retained':str(old),'new_rollout_id':rid,'method_repeated':False,'healthy_workers_preserved':{k:v.get('worker_pid') for k,v in state['tasks'].items() if v['phase'] in ['analysis','refine','fresh_rollout','starting']}})
    os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
    for _ in range(50):
        if not Path(f'/proc/{pid}').exists():break
        time.sleep(.1)
    assert not Path(f'/proc/{pid}').exists(), 'Previous controller still exists'
    subprocess.run(['bash',str(r/'launch.sh'),'--resume-queue'],check=True)
    replaced=True
    print(json.dumps({'recovery_archive':str(dest),'old_controller':pid,'fresh_only_queued':rid}))
finally:
    if not replaced and Path(f'/proc/{pid}').exists():os.kill(pid,signal.SIGCONT)
