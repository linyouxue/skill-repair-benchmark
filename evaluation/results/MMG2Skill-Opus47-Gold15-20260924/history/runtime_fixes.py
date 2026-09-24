"""MMG transport/packaging fixes; never edit the model's returned skill body."""
import re
import shlex
from runtime_environment import ensure_runtime_environment

# Also runs when an already active Refiner finishes and imports this module.
# Its successful response is preserved; only the missing launcher environment is restored.
ensure_runtime_environment()

def ensure_reserves_initial_image(root, cf):
    import fcntl,json,os,subprocess,sys
    from pathlib import Path
    baseline=cf.read(root/'infra-cache/reserves-at-risk-calc/prebuilt-image.json')
    directory=root/'runtime-cache/reserves-at-risk-calc'; directory.mkdir(parents=True,exist_ok=True)
    proof_path=directory/'prebuilt-image.json'
    proof=cf.read(proof_path) if proof_path.exists() else baseline
    if subprocess.run(['docker','image','inspect',proof['image_id']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0: return proof
    tag='mmg2skill-initial-reserves-at-risk-calc:20260923'
    taskdir=Path(cf.read(root/'manifest.json')['tasks_root'])/'reserves-at-risk-calc'
    # Same build lock as the inherited executor. Rebuild inputs/dependencies only.
    with Path('/tmp/skillrepair-expanded-docker-start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (directory/'build.log').open('ab',buffering=0) as log:
            subprocess.run([sys.executable,str(cf.SOURCE/'repro_wrappers/prebuild_skillsbench_task.py'),'--task-dir',str(taskdir),'--tag',tag,'--apt-mirror-profile','tuna','--docker-build-proxy','on','--ensure-agent-python','--proxy-lowercase'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=2400)
    image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
    cid=subprocess.check_output(['docker','run','-d','--network','none','--entrypoint','sleep',image,'180'],text=True).strip()
    try:
        def command(*args):return subprocess.check_output(['docker','exec',cid,*args],text=True).strip()
        assert command('sha256sum','/root/data/test-rar.xlsx').split()[0]==baseline['input_sha256']
        versions=json.loads(command('python3','-c','import json,openpyxl,pandas,xlrd,requests,numpy;print(json.dumps({m.__name__:m.__version__ for m in (openpyxl,pandas,xlrd,requests,numpy)}))'))
        assert versions==baseline['packages']
        assert not command('find','/root/output','/app','-mindepth','1','-type','f')
        proof={**baseline,'image_id':image,'source_tag':tag,'previous_image_id':baseline['image_id'],'rebuild_note':'Rebuilt frozen original Dockerfile; exact input/package versions and empty output checked offline; no model calls','verified_at':cf.now()}
        cf.write(proof_path,proof)
        return proof
    finally:subprocess.run(['docker','rm','-f',cid],check=True,stdout=subprocess.DEVNULL)

def parse_existing_skills(text, expected_names):
    from anything2skill.parser.data_types import Skill
    from anything2skill.parser.skill_extractor import _parse_skill_body
    lines=text.splitlines(keepends=True); starts=[]; fence=None
    for i,line in enumerate(lines):
        stripped=line.lstrip()
        marker=re.match(r'(`{3,}|~{3,})',stripped)
        if marker:
            token=marker.group(1)
            if fence is None: fence=(token[0],len(token))
            elif token[0]==fence[0] and len(token)>=fence[1]: fence=None
            continue
        match=re.match(r'^# +(.+?)\s*$',line)
        # A body may itself contain an unmatched fence. The formatter's explicit
        # separator + known identity + description still identifies the next skill.
        following=next((x.strip() for x in lines[i+1:] if x.strip()),'') if match else ''
        previous=next((x.strip() for x in reversed(lines[:i]) if x.strip()),'') if match else ''
        boundary=bool(match and match.group(1) in expected_names and following.startswith('>') and previous=='---')
        if fence is not None and not boundary: continue
        if not match: continue
        if following.startswith('>'):
            name=match.group(1)
            assert name in expected_names, f'Unexpected Skill envelope: {name}'
            if boundary: fence=None
            starts.append((i,name))
    assert len(starts)==len(expected_names) and {n for _,n in starts}==set(expected_names), 'Missing or duplicate Skill envelope'
    skills=[]
    for j,(start,name) in enumerate(starts):
        end=starts[j+1][0] if j+1<len(starts) else len(lines)
        body=''.join(lines[start+1:end]).strip()
        body=re.sub(r'\n---\s*$', '', body).strip()
        description,content,images=_parse_skill_body(body,{})
        skills.append(Skill(name=name,description=description,content=content,images=images))
    return skills

def snapshot_command(workspace):
    # Dockerfiles use different WORKDIRs; archive real existing paths only.
    paths=list(dict.fromkeys([str(workspace or '/root'),'/app','/home/agent','/root']))
    assert all(p.startswith('/') and p!='/' and '..' not in p.split('/') for p in paths)
    script='set -eu; set --; '
    for path in paths:
        script+=f'if [ -e {shlex.quote(path)} ]; then set -- "$@" {shlex.quote(path.lstrip("/"))}; fi; '
    script+='[ "$#" -gt 0 ]; tar -I "gzip -1" -cf /tmp/mmg-before-verifier.tar.gz '
    # User-site CUDA/PyTorch libraries can dwarf the actual task workspace.
    # Retain local executables and task outputs; omit installed dependency libraries.
    script+='--exclude="*/.cache" --exclude="*/.venv" --exclude="root/.local" --exclude="*/.local/lib" --exclude="*/.m2" --exclude="*/.ivy2" -C / "$@"'
    return script
