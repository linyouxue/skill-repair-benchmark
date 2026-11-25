import json,hashlib,urllib.request,time,concurrent.futures
from pathlib import Path
B=Path(__file__).parent;D=B/'nohint-source';tree=json.loads((B/'github-nohint-tree.json').read_text());ids={'dialogue-parser','data-to-d3','flink-query','manufacturing-equipment-maintenance','pddl-airport-planning'}
selected=[x for x in tree['tree'] if x['type']=='blob' and ((x['path'].startswith('tasks/') and x['path'].split('/')[1] in ids) or x['path'] in ['README.md','submission.json','MANIFEST.json','STATUS.csv','protocol.json','verifier-adjudications.json','large-files.json','task-index.json'])]
base='https://raw.githubusercontent.com/linyouxue/skill-repair-benchmark/main/evaluation/results/SkillTTA-GPT52-Gold31-Local30-20260924/'
def one(x):
 p=D/x['path'];p.parent.mkdir(parents=True,exist_ok=True)
 try:
  data=p.read_bytes() if p.exists() else urllib.request.urlopen(base+x['path'],timeout=40).read()
  gitsha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if gitsha!=x['sha']:raise ValueError('Git blob hash mismatch')
  p.write_bytes(data);return {'path':x['path'],'git_blob_sha':gitsha,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'verified':True,'url':base+x['path']}
 except Exception as e:return {'path':x['path'],'verified':False,'error':repr(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 rows=list(ex.map(one,selected))
(D/'DOWNLOAD_PROVENANCE.json').write_text(json.dumps({'source_tree_sha':'39beaed75f42297cdd9d49f56a78ff82423c274e','records':rows,'all_verified':all(x['verified'] for x in rows)},indent=2)+'\n');print('downloaded',sum(x['verified'] for x in rows),'of',len(rows),flush=True)
for r in rows:
 if not r['verified']:print(r,flush=True)
