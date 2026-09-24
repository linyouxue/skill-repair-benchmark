"""Resume Syzkaller from its existing paid Refiner response, once."""
import json,os,signal,shutil,subprocess,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
r=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(p)
tid='syzkaller-ppdev-syzlang';g=r/'generation'/tid
assert read(r/'skill-boundary-check.json')['passed']
assert not (g/'adapter_result.json').exists()
assert not (r/'runs/mmg2skill-gpt52-gold31-20260923'/f'{tid}-mmg2skill-gpt52-r001').exists()
pid=int((r/'batch.pid').read_text());cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
assert str(r/'experiment.py').encode() in cmd and b'--resume-queue' in cmd
os.kill(pid,signal.SIGSTOP);replaced=False
try:
    state=read(r/'batch_state.json');assert state['tasks'][tid]['phase']=='error'
    dest=r/'recovery-history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-skill-boundary-recovery');dest.mkdir(parents=True)
    for p in [r/'batch_state.json',r/'recovery_queue.json',r/'task_state'/f'{tid}.json',r/'worker_logs'/f'{tid}.log',r/'skill-boundary-check.json']:shutil.copy2(p,dest/p.name)
    reason='Saved response contains all 3 named Skill envelopes; unmatched body fence hid explicit separator/name/description boundaries. Reparse only, preserve malformed body and all paid responses.'
    q=read(r/'recovery_queue.json');q[tid]={'stage':'saved_response_parse','reason':reason};write(r/'recovery_queue.json',q)
    write(dest/'recovery.json',{'task_id':tid,'reason':reason,'successful_response_sha256':{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in g.rglob('*.response.json')},'extra_method_calls':0})
    os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
    for _ in range(50):
        if not Path(f'/proc/{pid}').exists():break
        time.sleep(.1)
    assert not Path(f'/proc/{pid}').exists()
    subprocess.run(['bash',str(r/'launch.sh'),'--resume-queue'],check=True);replaced=True
    print(json.dumps({'recovery_archive':str(dest),'old_controller':pid,'task':tid}))
finally:
    if not replaced and Path(f'/proc/{pid}').exists():os.kill(pid,signal.SIGCONT)
