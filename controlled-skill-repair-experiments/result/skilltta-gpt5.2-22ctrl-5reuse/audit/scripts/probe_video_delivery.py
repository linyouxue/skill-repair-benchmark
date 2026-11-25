"""Read-only ffprobe of an actual final-trajectory-matched model artifact; no edits."""
import sys,json,hashlib,subprocess,os
from pathlib import Path
L=Path(__file__).parent;S=L/'audit-evidence';id,attempt=sys.argv[1:3];root=L/'new-attempts/repaired'/id/attempt;j=next(root.glob('jobs/*/task__*'));tr=j/'trajectory/acp_trajectory.jsonl';h=hashlib.sha256(tr.read_bytes()).hexdigest();snap=None
for p in (S/'rerun_artifacts'/id/attempt).rglob('SNAPSHOT.json'):
 if getattr(p.stat(),'st_flags',0)&0x40000000:continue
 d=json.loads(p.read_text())
 if d.get('acp_sha256_at_collection')==h:snap=(p,d);break
assert snap,'No snapshot matches completed ACP'
p,d=snap;a=next(x for x in d['artifacts'] if x['source_path']=='/root/compressed_video.mp4' and x['copy_exit']==0);video=Path(a['destination']);image=d['image_id'];E=os.environ.copy();E.update(DOCKER_HOST='unix:///Users/king/.docker/run/docker.sock',DOCKER_CONFIG=str(L.parents[1]/'docker-config'));E.pop('DOCKER_CONTEXT',None);cmd=['docker','run','--rm','--network','none','--entrypoint','ffprobe','-v',str(video)+':/audit/input.mp4:ro',image,'-v','error','-show_format','-show_streams','-of','json','/audit/input.mp4'];q=subprocess.run(cmd,env=E,capture_output=True,text=True,timeout=60);r={'id':id,'attempt':attempt,'artifact':str(video),'bytes':video.stat().st_size,'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'ffprobe_command':cmd,'exit_code':q.returncode,'stderr':q.stderr,'output':json.loads(q.stdout) if q.returncode==0 else None,'image_provenance':image,'trajectory_sha256_matches_snapshot':True,'snapshot':str(p),'note':'Read-only ffprobe of original model artifact; no creation/re-encoding/output edits.'};dest=S/'video_physical_parsing'/id/(attempt+'.json');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(id,attempt,'ffprobe_exit',q.returncode,'duration',(r.get('output') or {}).get('format',{}).get('duration'))
