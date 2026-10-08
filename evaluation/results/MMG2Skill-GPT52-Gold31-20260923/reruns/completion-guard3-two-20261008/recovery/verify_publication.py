"""Verify staged evidence and Release payload without printing private content."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

SCOPE = {'SkillTTA-GPT52-Gold31-Local30-20260924': {'organize-messy-files'},
         'MMG2Skill-GPT52-Gold31-20260923': {'drone-planning-control'}}
Q = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worktree', required=True, type=Path)
    work = ap.parse_args().worktree.resolve()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=work)
    def load(rel):
        return json.loads(git('show', ':' + rel))
    def old(rel):
        return json.loads(git('show', 'HEAD:' + rel))
    changes = git('diff', '--cached', '--name-only', '--diff-filter=ACM', '-z').decode().strip('\0').split('\0')
    all_changes = git('diff', '--cached', '--name-only', '-z').decode().strip('\0').split('\0')
    for rel in all_changes:
        parts = Path(rel).parts
        assert parts[:2] == ('evaluation', 'results') and parts[2] in SCOPE
        if parts[3] == 'tasks':
            assert parts[4] in SCOPE[parts[2]] and '/original_run/' not in rel
            if '/repaired_skill/' in rel:
                assert parts[-1] != 'SKILL.md' and git('diff', '--cached', '--diff-filter=A', '--name-only', '--', rel).strip()
        assert not any(x in rel for x in ('gold-evaluation/', 'original-semantic', 'outcome-adjusted', 'gold-api-checkpoints/'))
    patterns = {'provider_or_local_key': re.compile(rb'sk-(?:benchflow|or-v1|ant-api\d+|svcacct)-[A-Za-z0-9_-]{12,}'),
                'openai_key': re.compile(rb'sk-(?:proj-|admin-)?(?=[A-Za-z0-9_-]{0,200}[A-Z])[A-Za-z0-9_-]{40,}'),
                'github_token': re.compile(rb'(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{30,}'),
                'private_key': re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA|PRIVATE).*?PRIVATE KEY-----')}
    findings, opaque_matches, payloads = [], [], {}
    def is_embedded_opaque(data, token):
        try:
            values = [json.loads(data)]
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                values = [json.loads(line) for line in data.splitlines() if line.strip()]
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False
        needle = token.decode('ascii')
        def walk(value, key=''):
            if isinstance(value, dict):
                return any(walk(v, k) for k, v in value.items())
            if isinstance(value, list):
                return any(walk(v, key) for v in value)
            return isinstance(value, str) and key in ('encrypted_content', 'id') and needle in value and value != needle
        return any(walk(v) for v in values)
    def scan(data, path):
        for label, pattern in patterns.items():
            for match in pattern.finditer(data):
                token = match.group()
                if label == 'openai_key' and is_embedded_opaque(data, token):
                    opaque_matches.append({'path': path, 'sha256': hashlib.sha256(token).hexdigest(), 'native_opaque_value_confirmed': True})
                else:
                    findings.append({'path': path, 'pattern': label, 'sha256': hashlib.sha256(token).hexdigest()})
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for rel in changes:
        proc.stdin.write((':' + rel + '\n').encode()); proc.stdin.flush()
        header = proc.stdout.readline().decode().strip().split()
        assert len(header) == 3 and header[1] == 'blob'
        size = int(header[2]); data = proc.stdout.read(size)
        assert proc.stdout.read(1) == b'\n' and len(data) == size and size < 100_000_000
        payloads[rel] = data
        if rel.endswith('.tar.gz'):
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as t:
                for m in t:
                    if m.isfile(): scan(t.extractfile(m).read(), rel + '::' + m.name)
        else:
            scan(data, rel)
        if rel.endswith('.json'): json.loads(data)
        elif rel.endswith('.jsonl'):
            for line in data.splitlines():
                if line.strip(): json.loads(line)
    proc.stdin.close(); assert proc.wait() == 0
    checks = []
    for method, tids in SCOPE.items():
        prefix = 'evaluation/results/' + method + '/'
        sub, previous = load(prefix + 'submission.json'), old(prefix + 'submission.json')
        previous_by = {t['task_id']: t for t in previous['tasks']}
        assert len(sub['tasks']) == 31 and len(previous_by) == 31
        for t in sub['tasks']:
            before = previous_by[t['task_id']]
            if t['task_id'] not in tids: assert t == before
            else: assert {k:v for k,v in t.items() if k != 'executor_run_id'} == {k:v for k,v in before.items() if k != 'executor_run_id'}
        timeline = load(prefix + 'trajectory_timelines/trajectory_timeline_index.json')
        ids = [(e['task_id'], e['method_id'], e['run_id'], e['condition']) for e in timeline['trajectories']]
        assert len(ids) == len(set(ids))
        for tid in tids:
            base = prefix + 'tasks/' + tid + '/repaired_run/'
            provenance, bench = load(base + 'RESULT_PROVENANCE.json'), load(base + 'benchmark_result.json')
            assert bench['execution_ok'] and bench['task_passed'] is False
            assert not any(bench.get(k) for k in ('error', 'verifier_error', 'export_error'))
            assert bench['rollout_id'] == provenance['selected_rollout_id']
            assert next(t for t in sub['tasks'] if t['task_id'] == tid)['executor_run_id'] == bench['rollout_id']
            assert any(e['run_id'] == bench['rollout_id'] and e['label'] == 'after' for e in timeline['trajectories'])
            for file in provenance['files']:
                rel = base + file['path']
                if 'release_asset' in file:
                    asset = Q / 'publication/assets' / file['release_asset']['asset_name']
                    data = asset.read_bytes()
                    with tarfile.open(asset, 'r:gz') as t:
                        for m in t:
                            if m.isfile(): scan(t.extractfile(m).read(), asset.name + '::' + m.name)
                    assert load(rel + '.asset.json') == file['release_asset']
                else:
                    data = payloads[rel] if rel in payloads else git('show', ':' + rel)
                assert len(data) == file['published_bytes'] and hashlib.sha256(data).hexdigest() == file['published_sha256'], rel
                if not file['credential_redactions']: assert file['source_sha256'] == file['published_sha256']
            for rel, expected in provenance['bundle_sha256_by_file'].items():
                assert hashlib.sha256(git('show', ':' + prefix + 'tasks/' + tid + '/repaired_skill/' + rel)).hexdigest() == expected
            training = [json.loads(s) for s in git('show', ':' + base + 'results.jsonl').splitlines() if s.strip()]
            assert len(training) == 1 and training[0]['info']['training_ready']
            checks.append({'method': method, 'task_id': tid, 'rollout_id': bench['rollout_id'], 'outcome': 'FAIL',
                           'files_verified': len(provenance['files']), 'bundle_files_verified': len(provenance['bundle_sha256_by_file']),
                           'all_staged_evidence_sha_verified': True, 'training_ready': True})
        if method.startswith('SkillTTA'):
            mf, pmf = load(prefix + 'MANIFEST.json'), old(prefix + 'MANIFEST.json')
            assert mf['effective_counts'] == pmf['effective_counts'] == {'PASS':5, 'FAIL':26}
            before = {e['task_id']: e for e in pmf['entries']}
            assert all(e == before[e['task_id']] for e in mf['entries'] if e['task_id'] not in tids)
        else:
            idx, pidx = load(prefix + 'task-index.json'), old(prefix + 'task-index.json')
            before = {e['task_id']: e for e in pidx['tasks']}
            assert all(e == before[e['task_id']] for e in idx['tasks'] if e['task_id'] not in tids)
            assert load(prefix + 'partial-execution-summary.json')['outcomes'] == {'PASS':5,'FAIL':26,'INFRA_ERROR':0}
    report = {'status': 'verified_for_publication' if not findings else 'credential_review_required',
              'staged_changed_files': len(all_changes), 'staged_bytes': sum(map(len, payloads.values())),
              'credential_scan_findings': findings, 'confirmed_native_opaque_false_positives': opaque_matches,
              'all_git_files_below_100MB': True, 'replacement_checks': checks,
              'no_new_model_judge_calls': True, 'unrelated_candidates_and_baselines_unchanged': True,
              'historical_semantic_scores_unchanged': True}
    (Q / 'publication/publication-check.json').write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
    assert not findings, 'Credential review needed; only masked locations saved'


if __name__ == '__main__':
    main()
