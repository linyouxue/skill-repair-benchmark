"""Check the staged publication without printing private verifier payloads."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile

SCOPE={
 'SkillTTA-GPT52-Gold31-Local30-20260924':{'azure-bgp-oscillation-route-leak','energy-unit-commitment','reserves-at-risk-calc','python-scala-translation'},
 'MMG2Skill-GPT52-Gold31-20260923':{'dialogue-parser'},
}
# Exact false positives independently located in native provider encrypted_content
# and a provider opaque response id. Do not broadly exempt JSON fields or tokens.
CIPHER_FALSE_POSITIVES={
 '091cf35b9a47c3949baeaaf2f087e36c1d7643269e3492ccaf6add52d020fac9':'encrypted_content',
 'f5cf9ed8756335ce7ee30eb804b6c7ceceec555dcb683763ecd7b6ef2266bec9':'opaque_response_id',
 'c0fae55a12830573d7c29a909bef3fb434e25867de27a2a9cff9300d04f5df73':'responses_reasoning_item.encrypted_content',
 '20dedf69d94cb34050cfd6f4a48e0b09b63de32d27c0760556c1755ff9c8c52e':'responses_reasoning_item.encrypted_content',
}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worktree',required=True,type=Path)
    w=ap.parse_args().worktree.resolve()
    assert w.name=='guard3-results-20261008'
    def git(*args):return subprocess.check_output(['git',*args],cwd=w)
    def load(rel):return json.loads(git('show',':'+rel))
    publication_base=load('evaluation/results/SkillTTA-GPT52-Gold31-Local30-20260924/reruns/completion-guard3-20261008/replacement-index.json')['base_commit']
    def old(rel):return json.loads(git('show',publication_base+':'+rel))
    changes=git('diff','--cached',publication_base,'--name-only','--diff-filter=ACM','-z').decode('utf-8').strip('\0').split('\0')
    all_changes=git('diff','--cached',publication_base,'--name-only','-z').decode('utf-8').strip('\0').split('\0')
    for rel in all_changes:
        parts=Path(rel).parts
        assert parts[:2]==('evaluation','results') and parts[2] in SCOPE, rel
        if len(parts)>4 and parts[3]=='tasks':
            assert parts[4] in SCOPE[parts[2]], 'Unrelated task changed: '+rel
            assert '/original_run/' not in rel and '/repaired_skill/' not in rel
    patterns={
      'provider_or_local_key':re.compile(rb'sk-(?:benchflow|or-v1|ant-api\d+|svcacct)-[A-Za-z0-9_-]{12,}'),
      'openai_high_entropy_key':re.compile(rb'sk-(?:proj-|admin-)?(?=[A-Za-z0-9_-]{0,200}[A-Z])[A-Za-z0-9_-]{40,}'),
      'github_token':re.compile(rb'(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{30,}'),
      'private_key':re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA|PRIVATE).*?PRIVATE KEY-----'),
    }
    payloads={}
    proc=subprocess.Popen(['git','cat-file','--batch'],cwd=w,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    # A single Git process; don't print any raw run/verifier contents.
    for rel in changes:
        proc.stdin.write((':'+rel+'\n').encode('utf-8'));proc.stdin.flush()
        header=proc.stdout.readline().decode().strip().split()
        assert len(header)==3 and header[1]=='blob', (rel,header)
        size=int(header[2]);data=proc.stdout.read(size);assert proc.stdout.read(1)==b'\n'
        assert len(data)==size and size<100_000_000, rel
        payloads[rel]=data
    proc.stdin.close();assert proc.wait()==0
    findings=[]
    false_positives={k:0 for k in CIPHER_FALSE_POSITIVES}
    def scan(data,path):
        for label,pattern in patterns.items():
            for match in pattern.finditer(data):
                h=hashlib.sha256(match.group()).hexdigest()
                if label=='openai_high_entropy_key' and h in CIPHER_FALSE_POSITIVES:
                    false_positives[h]+=1
                else:findings.append({'path':path,'pattern':label})
    largest=[]
    for rel,data in payloads.items():
        largest.append((len(data),rel))
        if rel.endswith('.tar.gz'):
            with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:
                for m in t:
                    if m.isfile():
                        b=t.extractfile(m).read()
                        scan(b,rel+'::'+m.name)
        else:
            scan(data,rel)
        if rel.endswith('.json'):
            json.loads(data)
        elif rel.endswith('.jsonl'):
            for line in data.splitlines():
                if line.strip():json.loads(line)
    assert not findings, 'Potential credentials detected; inspect only masked locations: '+str(findings)
    checks=[]
    for name,tids in SCOPE.items():
        prefix='evaluation/results/'+name+'/'
        submission=load(prefix+'submission.json')
        original_submission=old(prefix+'submission.json')
        assert len(submission['tasks'])==31 and len({r['task_id'] for r in submission['tasks']})==31
        old_by={r['task_id']:r for r in original_submission['tasks']}
        for row in submission['tasks']:
            previous=old_by[row['task_id']]
            if row['task_id'] not in tids:assert row==previous
            else:assert {k:v for k,v in row.items() if k!='executor_run_id'}=={k:v for k,v in previous.items() if k!='executor_run_id'}
        index=load(prefix+'trajectory_timelines/trajectory_timeline_index.json')
        ids=[(x['task_id'],x['method_id'],x['run_id'],x['condition']) for x in index['trajectories']]
        assert len(ids)==len(set(ids))
        for tid in tids:
            base=prefix+'tasks/'+tid+'/repaired_run/'
            p=load(base+'RESULT_PROVENANCE.json')
            b=load(base+'benchmark_result.json')
            assert b['execution_ok'] and not any(b.get(k) for k in ['error','verifier_error','export_error'])
            assert b['rollout_id']==p['selected_rollout_id']
            assert next(x for x in submission['tasks'] if x['task_id']==tid)['executor_run_id']==b['rollout_id']
            assert any(x['run_id']==b['rollout_id'] and x['label']=='after' for x in index['trajectories'])
            for file in p['files']:
                rel=base+file['path'];data=payloads.get(rel)
                if data is None:data=git('show',':'+rel)
                assert hashlib.sha256(data).hexdigest()==file['published_sha256'], 'Git changed evidence bytes: '+rel
                if not file['credential_redactions']:assert file['source_sha256']==file['published_sha256']
            for rel,h in p['bundle_sha256_by_file'].items():
                data=git('show',':'+prefix+'tasks/'+tid+'/repaired_skill/'+rel)
                assert hashlib.sha256(data).hexdigest()==h
            checks.append({'method':name,'task_id':tid,'rollout_id':b['rollout_id'],
                           'outcome':'PASS' if b['task_passed'] else 'FAIL','files':len(p['files']),
                           'snapshot':next(x for x in p['files'] if x['path'].endswith('.tar.gz')),
                           'bundle_and_staged_evidence_hashes_verified':True})
        if name.startswith('SkillTTA'):
            mf=load(prefix+'MANIFEST.json');assert mf['effective_counts']=={'PASS':5,'FAIL':26}
            for e in mf['entries']:
                if e['task_id'] in tids:assert e['rollout_id']==next(x for x in submission['tasks'] if x['task_id']==e['task_id'])['executor_run_id']
        else:
            idx=load(prefix+'task-index.json');oldidx=old(prefix+'task-index.json')
            before={r['task_id']:r for r in oldidx['tasks']}
            for r in idx['tasks']:
                if r['task_id'] not in tids:assert r==before[r['task_id']]
            agg=load(prefix+'partial-execution-summary.json')
            assert agg['valid_execution_tasks']==31 and agg['outcomes']=={'PASS':5,'FAIL':26,'INFRA_ERROR':0}
            assert agg['semantic_metrics'] is None and not agg['missing_valid_execution']
    report={'status':'verified_for_publication','staged_changed_files':len(all_changes),
            'staged_nondeleted_files':len(payloads),'staged_bytes':sum(map(len,payloads.values())),
            'credential_scan_findings':findings,'all_new_files_below_100MB':True,
            'exact_ciphertext_false_positives':[{ 'sha256':k,'native_field_type':CIPHER_FALSE_POSITIVES[k], 'matches':v} for k,v in false_positives.items()],
            'changed_method_directories':list(SCOPE),'replacement_checks':checks,
            'unrelated_task_raw_evidence_and_frozen_bundles_unchanged':True,
            'semantic_judge_calls':0,'largest_new_files':sorted(largest,reverse=True)[:5]}
    Path(__file__).with_name('publication-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['replacement_checks','largest_new_files']},ensure_ascii=True))


if __name__=='__main__':main()
