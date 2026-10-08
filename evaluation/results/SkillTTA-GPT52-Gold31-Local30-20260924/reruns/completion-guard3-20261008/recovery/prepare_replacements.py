"""Publish only the five audited guard3 runs into a clean results worktree.

No model, verifier, or judge invocation. Source evidence is never modified.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile

Q = Path(__file__).resolve().parent.parent
DEST = {
    'skilltta': 'SkillTTA-GPT52-Gold31-Local30-20260924',
    'mmg2skill': 'MMG2Skill-GPT52-Gold31-20260923',
}
LOCAL_TOKEN = re.compile(rb'sk-benchflow-[A-Za-z0-9_-]{12,}')
REDACTION = b'***REDACTED***'


def long(p):
    p = Path(p).absolute()
    return Path('\\\\?\\' + str(p)) if not str(p).startswith('\\\\?\\') else p


def read(p):
    return json.loads(long(p).read_text(encoding='utf-8'))


def write(p, d):
    p = long(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(p):
    return hashlib.sha256(long(p).read_bytes()).hexdigest()


def snapshot_copy(src, dst):
    """Preserve real tar members; redact local proxy credentials only."""
    altered = []
    before = []
    with tarfile.open(long(src), 'r:gz') as original:
        with long(dst).open('wb') as output:
            with gzip.GzipFile(fileobj=output, mode='wb', mtime=0, compresslevel=6) as gz:
                with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as published:
                    for member in original:
                        if member.isfile():
                            data = original.extractfile(member).read()
                            cleaned, count = LOCAL_TOKEN.subn(REDACTION, data)
                            before.append((member.name, hashlib.sha256(cleaned).hexdigest()))
                            if count:
                                altered.append({'member': member.name,
                                                'credential_redactions': count,
                                                'original_sha256': hashlib.sha256(data).hexdigest(),
                                                'published_sha256': hashlib.sha256(cleaned).hexdigest()})
                                member.size = len(cleaned)
                            published.addfile(member, io.BytesIO(cleaned))
                        else:
                            published.addfile(member)
    with tarfile.open(long(dst), 'r:gz') as published:
        after = [(m.name, hashlib.sha256(published.extractfile(m).read()).hexdigest())
                 for m in published if m.isfile()]
    assert before == after, 'Snapshot member content verification failed'
    assert altered and all(x['member'] == 'home/agent/.openhands/agent_settings.json'
                           for x in altered), 'Unexpected snapshot credential locations'
    return altered


def copy_run(src, dst):
    src, dst = long(src), long(dst)
    # Deletion is limited to a canonical run inside the explicitly named worktree.
    assert dst.name == 'repaired_run' and dst.parent.parent.name == 'tasks'
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    files = []
    for f in sorted(src.rglob('*')):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        redactions = []
        if f.name == 'workspace-before-verifier.tar.gz':
            redactions = snapshot_copy(f, out)
        else:
            data = f.read_bytes()
            cleaned, count = LOCAL_TOKEN.subn(REDACTION, data)
            out.write_bytes(cleaned)
            if count:
                redactions = [{'credential_redactions': count}]
        entry = {'path': rel.as_posix(), 'source_bytes': f.stat().st_size,
                 'source_sha256': sha(f), 'published_bytes': out.stat().st_size,
                 'published_sha256': sha(out), 'credential_redactions': redactions}
        if not redactions:
            assert entry['source_sha256'] == entry['published_sha256']
        files.append(entry)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worktree', required=True, type=Path)
    args = ap.parse_args()
    work = args.worktree.resolve()
    assert work.name == 'guard3-results-20261008' and (work / '.git').is_file()
    base = work / 'evaluation/results'
    manifest = read(Q / 'manifest.json')['tasks']
    summary = read(Q / 'final-review/execution-summary.json')
    rows = {r['slot']: r for r in summary['rows']}
    base_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work, text=True).strip()
    assert summary['coverage']['healthy'] == 5 and summary['coverage']['unresolved_infrastructure'] == 0
    for method, name in DEST.items():
        root = base / name
        scope = [r for r in manifest if r['method'] == method]
        pub = root / 'reruns/completion-guard3-20261008'
        pub.mkdir(parents=True, exist_ok=True)
        replacement_rows = []
        for spec in scope:
            r = rows[spec['slot']]
            tid = spec['task_id']
            task = root / 'tasks' / tid
            src = Path(r['run_root'])
            raw = read(src / 'benchmark_result.json')
            assert raw['execution_ok'] and not any(raw.get(k) for k in ['error','verifier_error','export_error'])
            assert raw['rollout_id'] == spec['rollout_id']
            old = read(task / 'repaired_run/benchmark_result.json')
            assert old['task_passed'] is False
            for rel, expected in spec['bundle_sha256_by_file'].items():
                assert sha(task / 'repaired_skill' / rel) == expected
                assert sha(src / 'inputs/skills' / rel) == expected
            state = task / 'task_state.json'
            if state.exists():
                write(pub / tid / 'previous-task-state.json', read(state))
            files = copy_run(src, task / 'repaired_run')
            provenance = {
                'task_id': tid, 'method_id': spec['method_id'],
                'canonical_run': f'tasks/{tid}/repaired_run',
                'selected_rollout_id': spec['rollout_id'],
                'previous_rollout_id': old['rollout_id'],
                'previous_outcome': 'FAIL', 'outcome': r['outcome'],
                'replaces_commit': base_commit,
                'historical_evidence': 'Previous canonical files remain in Git history and immutable local source batches.',
                'completion_guard_limit': 3, 'parent_iterations': 60,
                'method_bundle_frozen': True, 'bundle_sha256_by_file': spec['bundle_sha256_by_file'],
                'source_run': r['run_root'],
                'files': files,
                'snapshot_publication': 'Authentic exported snapshot, with only the now-stopped local proxy credential redacted in agent_settings.json. Original private tar retained; original/published hashes and altered member hashes recorded. No reconstruction from trajectory.',
                'semantic_gold': 'Not recomputed; this update replaces execution evidence only.',
            }
            write(task / 'repaired_run/RESULT_PROVENANCE.json', provenance)
            write(pub / tid / 'audit.json', r)
            write(pub / tid / 'previous-benchmark-result.json', old)
            write(state, {'task_id': tid, 'phase': 'finished', 'fresh_rollout_id': spec['rollout_id'],
                          'rollout': r['outcome'], 'result_path': f'tasks/{tid}/repaired_run/benchmark_result.json',
                          'worker_pid': None, 'source': 'Published selection derived from audited raw result; not live controller state.',
                          'completion_guard_limit': 3})
            replacement_rows.append({k:provenance[k] for k in ['task_id','method_id','canonical_run','selected_rollout_id','previous_rollout_id','previous_outcome','outcome','completion_guard_limit','parent_iterations','method_bundle_frozen']})
        write(pub / 'replacement-index.json', {'base_commit': base_commit, 'replacements': replacement_rows,
                                              'new_publication_model_calls': 0})
        write(pub / 'protocol.json', read(Q / 'protocol.json'))
        write(pub / 'manifest.json', {'tasks': scope})
        write(pub / 'execution-summary.json', {**{k:v for k,v in summary.items() if k not in ['rows','scope','coverage']},
              'scope': [r['slot'] for r in scope],
              'coverage': {'expected': len(scope), 'healthy': len(scope),
                           'pass': sum(rows[r['slot']]['outcome']=='PASS' for r in scope),
                           'fail': sum(rows[r['slot']]['outcome']=='FAIL' for r in scope),
                           'unresolved_infrastructure': 0},
              'fresh_provider_responses': sum(rows[r['slot']]['provider_responses'] for r in scope),
              'rows': [rows[r['slot']] for r in scope]})
        for file in ['executor-guard3.patch','experiment.py','launch.sh','runtime_fixes.py',
                     'recover_pre_model_infra.py','recover_reserves_build.py','prebuild_skillsbench_task.py',
                     'check_resume_dispatch.py','infra-recovery-check.json','reserves-build-recovery-check.json',
                     'resume-dispatch-offline-check.json','resume-plan.json','prior-guard-evidence.json']:
            source = Q / file
            if source.exists():
                data = source.read_bytes()
                (pub / 'recovery').mkdir(exist_ok=True)
                (pub / 'recovery' / file).write_bytes(LOCAL_TOKEN.sub(REDACTION,data))
        # Each task's execution selection is current; diagnoses and method bundles do not change.
        submission = read(root / 'submission.json')
        for t in submission['tasks']:
            if t['task_id'] in {x['task_id'] for x in scope}:
                t['executor_run_id'] = next(x['rollout_id'] for x in scope if x['task_id']==t['task_id'])
        write(root / 'submission.json', submission)
        if method == 'skilltta':
            mf = read(root / 'MANIFEST.json')
            for entry in mf['entries']:
                spec = next((x for x in scope if x['task_id']==entry['task_id']), None)
                if not spec:
                    continue
                r = rows[spec['slot']]
                b = read(Path(r['run_root']) / 'benchmark_result.json')
                entry.update({'raw_outcome': r['outcome'], 'effective_outcome': r['outcome'],
                              'rollout_id': spec['rollout_id'], 'execution_ok': True, 'reward': b['reward'],
                              'provider_requests': b['provider_requests'], 'agent_iterations': b['agent_iterations'],
                              'completion_guard_limit': 3,
                              'rerun_provenance': f'tasks/{entry["task_id"]}/repaired_run/RESULT_PROVENANCE.json'})
                entry.pop('trajectory_timeline_after',None)
            mf['effective_counts'] = {o:sum(t['effective_outcome']==o for t in mf['entries']) for o in ['PASS','FAIL']}
            mf['canonical_run_variations'] = 'Four listed tasks use guard3; other current tasks retain their published protocols. See reruns/completion-guard3-20261008.'
            write(root / 'MANIFEST.json', mf)
            with (root / 'STATUS.csv').open('w',encoding='utf-8',newline='') as f:
                cw=csv.DictWriter(f,fieldnames=['task_id','raw_outcome','effective_outcome','rollout_id','reward','agent_iterations','provider_requests'])
                cw.writeheader()
                for t in mf['entries']:
                    cw.writerow({k:t.get(k) for k in cw.fieldnames})
            protocol=read(root/'protocol.json')
            protocol['current_published_scope'] = {'valid_tasks':31,'includes_Druid':True,'canonical_counts':mf['effective_counts'],
                                                  'guard3_variation':'reruns/completion-guard3-20261008/protocol.json'}
            write(root/'protocol.json',protocol)
        else:
            idx=read(root/'task-index.json')
            for t in idx['tasks']:
                if t['task_id']=='dialogue-parser':
                    t.update({'outcome':'FAIL','phase':'finished','execution_ok':True,'task_passed':False,
                              'selected_result':'tasks/dialogue-parser/repaired_run/benchmark_result.json',
                              'source_selected_result':'tasks/dialogue-parser/repaired_run/benchmark_result.json',
                              'raw_run_source':'tasks/dialogue-parser/repaired_run',
                              'completion_guard_limit':3, 'selected_rollout_id':scope[0]['rollout_id'],
                              'rerun_provenance':'tasks/dialogue-parser/repaired_run/RESULT_PROVENANCE.json'})
            write(root/'task-index.json',idx)
            agg=read(root/'partial-execution-summary.json')
            agg.update({'status':'execution_complete_semantic_pending','semantic_gold_status':'not_run',
                        'missing_valid_execution':[], 'completion_guard3_replacements':['dialogue-parser'],
                        'publication_model_calls':0})
            write(root/'partial-execution-summary.json',agg)
        text = ['# Completion guard3 replacements — 2026-10-08','',
                'The user authorized fresh reruns of these previously failed tasks with completion guard 3. '
                'The listed runs now replace their prior canonical `tasks/<task_id>/repaired_run` selections. '
                'This is a mixed-protocol execution snapshot, not a claim that every task was run with guard3.','',
                '| Task | Prior result | Current result | Current rollout |','|---|---|---|---|']
        text += [f'| {r["task_id"]} | FAIL | {r["outcome"]} | `{r["selected_rollout_id"]}` |' for r in replacement_rows]
        text += ['', 'All current runs have valid original verifier outcomes, complete ACP and LLM trajectories, training rows, '
                 'authentic exported workspaces and full frozen method inputs. Valid FAILs are retained. '
                 'Prior canonical runs remain in Git history at commit `'+base_commit+'` and private source batches.', '',
                 'Protocol: `openrouter/openai/gpt-5.2`, explicit reasoning omitted, output ceiling 32768, guard continuation limit3, '
                 'one shared60-iteration parent budget. Method generation/bundles and original baselines were reused. '
                 'No new method, retrieval, embedding or judge calls; no remaining infrastructure fault. '
                 'Independent fresh randomness means the result change does not isolate the causal effect of guard3.','',
                 'Raw generic `executor_request.protocol` still states default guard1; actual config/result/ACP prove guard3. '
                 'Saved SDK reasoning_effort defaults to high while captured provider fields omit explicit reasoning; omission is not proof of none. '
                 'Provider callbacks log total_tokens only; training input/output splits are placeholders. '
                 'All selected runs have n_skill_invocations=0 and full Skill body preload exposure. '
                 'Python→Scala inherits reconstructed input/custom verifier limitations. '
                 'Reserves retains historical cache proof fields; its new build verification and authentic run are authoritative.','',
                 'The public snapshots redact only the obsolete local BenchFlow proxy credential from agent_settings.json. '
                 'RESULT_PROVENANCE.json records source/public file and member hashes; real workspace content is retained, never reconstructed. '
                 'Raw source snapshots remain private and immutable. Other run files are byte-identical, except any explicitly listed credential redaction.','',
                 'The first attempt failed before model execution due to Docker network pool/build connectivity. '
                 'Reserves reused cached Ubuntu packages after a pre-model APT proxy interruption; targeted offline input/pin/output checks passed. '
                 'Recovery evidence and scripts are under recovery/. The30-minute monitor was deleted after audit. '
                 'Do not execute archived launch scripts blindly.','',
                 'Semantic Gold scores are not recomputed or inferred from execution PASS. Existing diagnoses and any historical scoring are retained.','']
        (pub/'README.md').write_text('\n'.join(text),encoding='utf-8')
    print(json.dumps({'prepared':5,'base_commit':base_commit,'worktree':str(work)},ensure_ascii=True))


if __name__ == '__main__':
    main()
