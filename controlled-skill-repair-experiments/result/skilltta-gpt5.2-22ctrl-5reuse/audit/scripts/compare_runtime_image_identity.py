"""Compare actual retained image RootFS layers and functional image configuration.
No container execution, dependency hashing scans or model calls.
"""
import json,os,subprocess,hashlib
from pathlib import Path
L=Path(__file__).parent.resolve();S=L/'audit-evidence';B=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52');E=os.environ.copy();E.update(DOCKER_HOST='unix:///Users/king/.docker/run/docker.sock',DOCKER_CONFIG=str(B/'docker-config'));E.pop('DOCKER_CONTEXT',None);expected={r['id']:r for r in json.loads((S/'actual_runtime_images.json').read_text())['records']};cache={};out=[]
fields=['Env','User','WorkingDir','Entrypoint','Cmd','Shell','StopSignal','Healthcheck','Volumes','ExposedPorts']
for p in (S/'image_provenance').rglob('*.json'):
 if getattr(p.stat(),'st_flags',0)&0x40000000:continue
 d=json.loads(p.read_text());id=p.parents[1].name;image=d.get('runtime_image_id');info=(d.get('image_inspect') or [None])[0]
 if not image or not info or id not in expected:continue
 target=expected[id]['image_id']
 if target not in cache:
  q=subprocess.run(['docker','image','inspect',target],env=E,capture_output=True,text=True,timeout=20)
  cache[target]=json.loads(q.stdout)[0] if q.returncode==0 else None
 accepted=cache[target]
 if not accepted:out.append({'id':id,'attempt':p.parent.name,'rollout':p.stem,'expected_recipe_image':target,'equivalence_unproven':'expected metadata image unavailable'});continue
 configdiff=[k for k in fields if accepted.get('Config',{}).get(k)!=info.get('Config',{}).get(k)];a=accepted.get('RootFS',{}).get('Layers',[]);b=info.get('RootFS',{}).get('Layers',[]);same=a==b and bool(a);platform=all(accepted.get(k)==info.get(k) for k in ['Architecture','Os','Variant']);functional=not configdiff and platform and same
 out.append({'id':id,'attempt':p.parent.name,'rollout':p.stem,'observed_image_id':image,'observed_container_id':d.get('container_id'),'expected_recipe_image_id':target,'image_id_equal':target==image,'rootfs_layer_digests_equal':same,'platform_equal':platform,'architecture':info.get('Architecture'),'os':info.get('Os'),'rootfs_layer_count':len(b),'observed_rootfs_layer_sha256':hashlib.sha256(json.dumps(b,separators=(',',':')).encode()).hexdigest(),'functional_config_fields_compared':fields,'functional_config_differences':configdiff,'functional_config_sha256':hashlib.sha256(json.dumps({k:info.get('Config',{}).get(k) for k in fields},sort_keys=True).encode()).hexdigest(),'same_initial_filesystem_and_functional_config':functional,'observed_identity_source':str(p),'expected_recipe_source':str(S/'actual_runtime_images.json'),'scope':'Exact image RootFS layer vectors and functional startup configuration. Image ID metadata may differ. Does not assert runtime mounts, later package installs, live input mutations, or historical deleted image identity.'})
(S/'runtime_image_identity_review.json').write_text(json.dumps({'records':out,'exact_initial_image_equivalence_cases':sum(r.get('same_initial_filesystem_and_functional_config',False) for r in out),'no_model_calls_or_containers_run':True},ensure_ascii=False,indent=2)+'\n');print('actual images checked',len(out),'exact initial RootFS+config',sum(r.get('same_initial_filesystem_and_functional_config',False) for r in out),'unproved/different',[(r['id'],r['attempt'],r.get('functional_config_differences')) for r in out if not r.get('same_initial_filesystem_and_functional_config')])
