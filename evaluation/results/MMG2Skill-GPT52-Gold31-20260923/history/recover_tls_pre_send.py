"""Recover only the two proven TLS-before-request failures on 2026-09-23."""
import json,os,signal,shutil,subprocess,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
r=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
    t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');t.replace(p)
targets={'shock-analysis-supply':'refine_calls','software-dependency-audit':'analysis_calls'}
evidence={}
for tid,stage in targets.items():
    log=(r/'worker_logs'/f'{tid}.log').read_text(encoding='utf-8')
    assert 'stream = stream.start_tls(**kwargs)' in log
    assert 'httpcore.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING]' in log
    d=r/'generation'/tid/stage
    pending=[p for p in d.glob('*.pending.json') if not p.with_name(p.name.replace('.pending.json','.response.json')).exists()]
    assert len(pending)==1,(tid,pending)
    p=pending[0];err=p.with_name(p.name.replace('.pending.json','.error.json'))
    assert read(err)['type']=='APIConnectionError'
    evidence[tid]={'pending':p,'error':err,'completed_response_sha256':{str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest() for x in (r/'generation'/tid).rglob('*.response.json')}}
probe=subprocess.run(['curl','-x','http://127.0.0.1:7890','-sS','-o','/dev/null','--connect-timeout','15','--max-time','30','-w','%{http_code} %{ssl_verify_result}','https://openrouter.ai/api/v1/models'],capture_output=True,text=True,timeout=35)
assert probe.returncode==0 and probe.stdout=='200 0',(probe.returncode,probe.stdout,probe.stderr)
pid=int((r/'batch.pid').read_text());cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
assert str(r/'experiment.py').encode() in cmd and b'--resume-queue' in cmd
os.kill(pid,signal.SIGSTOP);replaced=False
try:
    state=read(r/'batch_state.json');q=read(r/'recovery_queue.json')
    assert all(state['tasks'][t]['phase']=='error' for t in targets)
    dest=r/'recovery-history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-tls-pre-send-recovery');dest.mkdir(parents=True)
    for p in [r/'batch_state.json',r/'recovery_queue.json']:shutil.copy2(p,dest/p.name)
    for tid,ev in evidence.items():
        sub=dest/tid;sub.mkdir()
        for p in [r/'task_state'/f'{tid}.json',r/'worker_logs'/f'{tid}.log']:shutil.copy2(p,sub/p.name)
        for key in ['pending','error']:ev[key].rename(sub/ev[key].name)
        q[tid]={'stage':'provider_checkpoint','reason':'Proxy CONNECT succeeded but TLS start_tls failed before any model HTTP request bytes; verified same route GET /api/v1/models HTTP200 TLS0. Retry only missing stage, preserve all successful responses.'}
    write(r/'recovery_queue.json',q)
    write(dest/'recovery.json',{'targets':list(targets),'free_probe':probe.stdout,'failure_stage':'TLS handshake before HTTP model POST','successful_responses':{t:e['completed_response_sha256'] for t,e in evidence.items()},'healthy_workers_preserved':{k:v.get('worker_pid') for k,v in state['tasks'].items() if v['phase'] in ['analysis','refine','fresh_rollout','starting']}})
    os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
    for _ in range(50):
        if not Path(f'/proc/{pid}').exists():break
        time.sleep(.1)
    assert not Path(f'/proc/{pid}').exists()
    subprocess.run(['bash',str(r/'launch.sh'),'--resume-queue'],check=True);replaced=True
    print(json.dumps({'archive':str(dest),'checkpoint_requeued':list(targets),'old_controller':pid}))
finally:
    if not replaced and Path(f'/proc/{pid}').exists():os.kill(pid,signal.SIGCONT)
