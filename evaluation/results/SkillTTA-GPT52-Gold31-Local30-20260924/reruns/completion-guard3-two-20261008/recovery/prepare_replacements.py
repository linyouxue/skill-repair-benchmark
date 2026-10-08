"""Publish the two audited guard3 runs. No model, verifier, or judge invocation."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

Q = Path(__file__).resolve().parents[1]
DEST = {'skilltta': 'SkillTTA-GPT52-Gold31-Local30-20260924', 'mmg2skill': 'MMG2Skill-GPT52-Gold31-20260923'}
TOKEN = re.compile(rb'sk-benchflow-[A-Za-z0-9_-]{12,}')
REDACTION = b'***REDACTED***'
PUB = 'reruns/completion-guard3-two-20261008'
TAG = 'guard3-two-evidence-20261008'


def long(p):
    value = str(p)
    if os.name == 'nt' and value.startswith('/mnt/c/'):
        value = 'C:/' + value[len('/mnt/c/'):]
    p = Path(value).absolute()
    if os.name == 'nt' and not str(p).startswith('\\\\?\\'):
        p = Path('\\\\?\\' + str(p))
    return p


def read(p):
    return json.loads(long(p).read_text(encoding='utf-8'))


def write(p, value):
    p = long(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(p):
    h = hashlib.sha256()
    with long(p).open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def snapshot_copy(src, dst):
    before, altered = [], []
    with tarfile.open(long(src), 'r:gz') as original, long(dst).open('wb') as output:
        with gzip.GzipFile(fileobj=output, mode='wb', mtime=0, compresslevel=6) as gz:
            with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as public:
                for member in original:
                    if member.isfile():
                        data = original.extractfile(member).read()
                        clean, count = TOKEN.subn(REDACTION, data)
                        before.append((member.name, hashlib.sha256(clean).hexdigest()))
                        if count:
                            altered.append({'member': member.name, 'credential_redactions': count,
                                            'original_sha256': hashlib.sha256(data).hexdigest(),
                                            'published_sha256': hashlib.sha256(clean).hexdigest()})
                            member.size = len(clean)
                        public.addfile(member, io.BytesIO(clean))
                    else:
                        public.addfile(member)
    with tarfile.open(long(dst), 'r:gz') as public:
        after = [(m.name, hashlib.sha256(public.extractfile(m).read()).hexdigest()) for m in public if m.isfile()]
    assert before == after
    assert altered and all(a['member'] == 'home/agent/.openhands/agent_settings.json' for a in altered)
    return altered


def copy_run(src, dst, method, work):
    src, dst = long(src), long(dst)
    assert dst.resolve().is_relative_to(long(work / 'evaluation/results').resolve())
    assert dst.name == 'repaired_run' and dst.parent.parent.name == 'tasks'
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    entries, assets = [], []
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
            clean, count = TOKEN.subn(REDACTION, f.read_bytes())
            out.write_bytes(clean)
            if count:
                redactions = [{'credential_redactions': count}]
        entry = {'path': rel.as_posix(), 'source_bytes': f.stat().st_size, 'source_sha256': sha(f),
                 'published_bytes': out.stat().st_size, 'published_sha256': sha(out), 'credential_redactions': redactions}
        if not redactions:
            assert entry['source_sha256'] == entry['published_sha256']
        if out.stat().st_size >= 95_000_000:
            assert f.name == 'workspace-before-verifier.tar.gz'
            asset_name = f'{method}-organize-guard3-two-{entry["published_sha256"][:16]}-workspace-before-verifier.tar.gz'
            asset = long(Q / 'publication/assets' / asset_name)
            asset.parent.mkdir(parents=True, exist_ok=True)
            assert not asset.exists()
            out.replace(asset)
            asset_row = {'path': f'tasks/{dst.parent.name}/repaired_run/{rel.as_posix()}', 'asset_name': asset_name,
                         'url': f'https://github.com/linyouxue/skill-repair-benchmark/releases/download/{TAG}/{asset_name}',
                         'bytes': entry['published_bytes'], 'sha256': entry['published_sha256'],
                         'lossless': True, 'credential_redactions': redactions, 'original_private_sha256': entry['source_sha256']}
            entry['release_asset'] = asset_row
            write(out.with_name(out.name + '.asset.json'), asset_row)
            assets.append(asset_row)
        entries.append(entry)
    return entries, assets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worktree', required=True, type=Path)
    ap.add_argument('--resume-preparation', action='store_true')
    args = ap.parse_args()
    work = args.worktree.resolve()
    assert work.name == 'guard3-results-20261008' and (work / '.git').is_file()
    if not args.resume_preparation:
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=work)
    else:
        changed = subprocess.check_output(['git', 'diff', '--name-only'], cwd=work, text=True).splitlines()
        assert all(p.startswith(tuple('evaluation/results/' + n + '/' for n in DEST.values())) for p in changed)
    base_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work, text=True).strip()
    assert base_commit == 'c3159e6f805ab23dd3f911c4c12d7beef9c6d09c'
    manifest = read(Q / 'manifest.json')['tasks']
    summary = read(Q / 'final-review/execution-summary.json')
    assert summary['coverage']['healthy'] == 2 and summary['coverage']['unresolved_infrastructure'] == 0
    by_slot = {r['slot']: r for r in summary['rows']}
    for spec in manifest:
        method, tid = spec['method'], spec['task_id']
        row = by_slot[spec['slot']]
        root = long(work / 'evaluation/results' / DEST[method])
        task = root / 'tasks' / tid
        pub = root / PUB
        if args.resume_preparation and (pub / 'replacement-index.json').exists():
            done = read(pub / 'replacement-index.json')['replacements'][0]
            assert done['selected_rollout_id'] == spec['rollout_id']
            assert read(task / 'repaired_run/benchmark_result.json')['rollout_id'] == spec['rollout_id']
            continue
        assert not pub.exists() or all(p.name == 'bundle-reconciliation.json' for p in pub.iterdir())
        pub.mkdir(parents=True, exist_ok=True)
        old = read(task / 'repaired_run/benchmark_result.json')
        assert old['execution_ok'] and old['task_passed'] is False
        source = long(row['run_root'])
        current = read(source / 'benchmark_result.json')
        assert current['execution_ok'] and not any(current.get(k) for k in ('error', 'verifier_error', 'export_error'))
        assert current['rollout_id'] == spec['rollout_id']
        missing_bundle_files = []
        for rel, expected in spec['bundle_sha256_by_file'].items():
            authentic = source / 'inputs/skills' / rel
            assert sha(authentic) == expected
            published = task / 'repaired_skill' / rel
            if published.exists():
                assert sha(published) == expected
            else:
                missing_bundle_files.append(rel)
                published.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(authentic, published)
        write(pub / 'bundle-reconciliation.json', {'task_id': tid, 'full_bundle_files': len(spec['bundle_sha256_by_file']),
                                                  'previous_missing_supporting_files_restored': missing_bundle_files,
                                                  'existing_bundle_files_changed': 0,
                                                  'source': 'Authentic current rollout inputs/skills; all files equal frozen manifest SHA256.'})
        previous_state = read(task / 'task_state.json') if (task / 'task_state.json').exists() else None
        files, assets = copy_run(source, task / 'repaired_run', method, work)
        provenance = {'task_id': tid, 'method_id': spec['method_id'], 'canonical_run': f'tasks/{tid}/repaired_run',
                      'selected_rollout_id': spec['rollout_id'], 'previous_rollout_id': old['rollout_id'],
                      'previous_outcome': 'FAIL', 'outcome': row['outcome'], 'replaces_commit': base_commit,
                      'historical_evidence': 'Previous canonical files remain in Git history and immutable private source runs.',
                      'completion_guard_limit': 3, 'parent_iterations': 60, 'method_bundle_frozen': True,
                      'bundle_sha256_by_file': spec['bundle_sha256_by_file'], 'source_run': row['run_root'], 'files': files,
                      'snapshot_publication': 'Authentic export; only obsolete local proxy credential redacted in agent_settings.json. All other member bytes preserved. Private original SHA and public derivative/member SHA recorded.',
                      'semantic_gold': 'Unchanged: frozen method candidate reused; no judge calls or inference from execution result.'}
        write(task / 'repaired_run/RESULT_PROVENANCE.json', provenance)
        write(task / 'task_state.json', {'task_id': tid, 'phase': 'finished', 'fresh_rollout_id': spec['rollout_id'],
                                       'rollout': row['outcome'], 'result_path': f'tasks/{tid}/repaired_run/benchmark_result.json',
                                       'worker_pid': None, 'completion_guard_limit': 3,
                                       'source': 'Published selection from accepted real-run audit, not live controller state.'})
        write(pub / tid / 'previous-benchmark-result.json', old)
        write(pub / tid / 'previous-task-state.json', previous_state)
        audit_name = 'organize-audit.json' if method == 'skilltta' else 'drone-audit.json'
        write(pub / tid / 'audit.json', read(Q / 'final-review' / audit_name))
        replacement = {k: provenance[k] for k in ('task_id', 'method_id', 'canonical_run', 'selected_rollout_id', 'previous_rollout_id', 'previous_outcome', 'outcome', 'completion_guard_limit', 'parent_iterations', 'method_bundle_frozen')}
        write(pub / 'replacement-index.json', {'base_commit': base_commit, 'replacements': [replacement], 'publication_model_calls': 0})
        write(pub / 'protocol.json', {**read(Q / 'protocol.json'), 'publication_scope': [spec['slot']]})
        write(pub / 'manifest.json', {'tasks': [spec]})
        write(pub / 'execution-summary.json', {**{k: v for k, v in summary.items() if k not in ('scope', 'coverage', 'rows')},
                                             'scope': [spec['slot']], 'coverage': {'expected': 1, 'healthy': 1, 'pass': 0, 'fail': 1, 'unresolved_infrastructure': 0},
                                             'fresh_provider_responses': row['provider_responses'], 'fresh_saved_cost_usd': row['cost_usd'], 'rows': [row]})
        recovery = pub / 'recovery'
        recovery.mkdir()
        selected = ['experiment.py', 'launch.sh', 'runtime_fixes.py', 'startup-evidence.json', 'resume-dispatch-offline-check.json', 'completion-receipt.json']
        if method == 'skilltta':
            selected += ['recover_organize_build.py', 'continue_organize_offline_check.py', 'check_resume_dispatch.py', 'organize-build-recovery-check.json', 'recovery-startup-evidence.json', 'resume-plan.json']
        for name in selected:
            src = Q / name if name != 'completion-receipt.json' else Q / 'final-review' / name
            if src.exists():
                (recovery / name).write_bytes(TOKEN.sub(REDACTION, long(src).read_bytes()))
        if method == 'skilltta':
            src_root = long(Q / 'recovery-history/organize-pre-model-paper-download')
            for src in src_root.rglob('*'):
                if src.is_file():
                    out = recovery / 'organize-pre-model-paper-download' / src.relative_to(src_root)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(TOKEN.sub(REDACTION, src.read_bytes()))
        shutil.copyfile(long(__file__), recovery / 'prepare_replacements.py')
        sub = read(root / 'submission.json')
        next(t for t in sub['tasks'] if t['task_id'] == tid)['executor_run_id'] = spec['rollout_id']
        write(root / 'submission.json', sub)
        if method == 'skilltta':
            mf = read(root / 'MANIFEST.json')
            e = next(e for e in mf['entries'] if e['task_id'] == tid)
            e.update(raw_outcome=row['outcome'], effective_outcome=row['outcome'], rollout_id=spec['rollout_id'],
                     execution_ok=True, reward=current['reward'], provider_requests=current['provider_requests'],
                     agent_iterations=current['agent_iterations'], completion_guard_limit=3,
                     rerun_provenance=f'tasks/{tid}/repaired_run/RESULT_PROVENANCE.json')
            mf['canonical_run_variations'] = 'Five current tasks use guard3: four under reruns/completion-guard3-20261008 plus Organize under reruns/completion-guard3-two-20261008. Other tasks retain published protocols.'
            write(root / 'MANIFEST.json', mf)
            with (root / 'STATUS.csv').open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['task_id', 'raw_outcome', 'effective_outcome', 'rollout_id', 'reward', 'agent_iterations', 'provider_requests'])
                writer.writeheader()
                for e in mf['entries']:
                    writer.writerow({k: e.get(k) for k in writer.fieldnames})
            protocol = read(root / 'protocol.json')
            protocol['current_published_scope']['guard3_variations'] = ['reruns/completion-guard3-20261008/protocol.json', PUB + '/protocol.json']
            write(root / 'protocol.json', protocol)
            assert assets
            write(root / 'large-files.json', {'release_tag': TAG, 'assets': assets, 'compressed_text': []})
            # Established downloader restores public snapshot bytes, with exact size/SHA checks.
            shutil.copyfile(long(work / 'evaluation/results' / DEST['mmg2skill'] / 'restore_files.py'), root / 'restore_files.py')
        else:
            idx = read(root / 'task-index.json')
            e = next(e for e in idx['tasks'] if e['task_id'] == tid)
            e.update(phase='finished', outcome=row['outcome'], execution_ok=True, task_passed=False,
                     selected_result=f'tasks/{tid}/repaired_run/benchmark_result.json', source_selected_result=f'tasks/{tid}/repaired_run/benchmark_result.json',
                     raw_run_source=f'tasks/{tid}/repaired_run', completion_guard_limit=3, selected_rollout_id=spec['rollout_id'],
                     rerun_provenance=f'tasks/{tid}/repaired_run/RESULT_PROVENANCE.json')
            write(root / 'task-index.json', idx)
            agg = read(root / 'partial-execution-summary.json')
            if tid not in agg['completion_guard3_replacements']:
                agg['completion_guard3_replacements'].append(tid)
            write(root / 'partial-execution-summary.json', agg)
        v = row['verifier']['summary']
        special = ('Drone had one textual file_editor response at LLM15, resumed a real tool call at LLM16, and reached real finish at LLM37. Textual calls did not disappear, but no early stop or guard exhaustion recurred.' if method == 'mmg2skill' else
                   'Organize had no textualized tool call. One ordinary progress announcement continued into real terminal work; real finish occurred at LLM13. All 103 fixed input files are byte-identical and sorted once. Two package document templates outside subject folders are an audit observation, not confirmed hidden-checker causality.')
        text = f'''# Guard3 canonical replacement — {tid}\n\nThe user explicitly authorized replacing this task's canonical repaired execution with the audited rerun. Original baselines, method diagnoses, full repaired Skill bundle and historical semantic scores are unchanged. Previous canonical evidence is available at commit `{base_commit}` and in private source runs.\n\n- Method: {row['method']}\n- Current rollout: `{spec['rollout_id']}`\n- Result: valid FAIL, original verifier {v['passed']}/{v['tests']}\n- True successful responses: {row['provider_responses']}; parent steps {row['parent_steps']}/60\n- Guard continuations: 1/3, not exhausted; no unresolved infrastructure error\n- Full Skill body injection verified; n_skill_invocations=0\n\n{special}\n\nOnly this user-approved fresh uses guard3 with the same 60-step budget. GPT-5.2 provider reasoning is omitted; actual session output ceiling is 32768. The generic executor_request protocol still says default guard1, and SDK saved reasoning defaults high while provider fields omit explicit reasoning. Provider callbacks preserve total_tokens only; the training input/output split is not measured. Fresh randomness prevents isolating guard's causal effect. No method, original, embedding, or judge calls occurred during publication.\n\nThe authentic exported tar is published after redacting only the obsolete local proxy credential in agent_settings.json; all other member bytes are preserved. RESULT_PROVENANCE.json connects source/public hashes. Organize's large public tar is a Release asset: run `python restore_files.py --download-assets` from its method directory to restore and verify it. Drone's snapshot is stored directly in Git. Source originals stay private and immutable; outputs are never reconstructed from prose.\n\nOrganize's first new r001 failed before any model request during fixed-input PDF download. Its bounded recovery downloaded the same original URLs through the existing proxy, verified 100 PDF SHAs, 3 document SHAs and 5 pinned dependencies, then dispatched only r002. Evidence and recovery scripts are preserved; do not blindly execute archived launch scripts. The completed 30-minute monitor remains deleted.\n\nThe canonical two-run trajectories and training rows are complete. Readable timelines are generated by evaluation/results/export_trajectory.py. This publication updates execution evidence, not semantic Gold scores.\n'''
        (pub / 'README.md').write_text(text, encoding='utf-8')
        readme = root / 'README.md'
        old_text = readme.read_text(encoding='utf-8')
        if method == 'skilltta':
            old_text = old_text.replace('The four current guard3 replacements also include', 'The five current guard3 replacements also include')
        old_text += f'\n## 2026-10-08 additional guard3 replacement\n\n[{tid}: audited canonical rerun]({PUB}/README.md) · [Replacement index]({PUB}/replacement-index.json).\n\n{special} The task remains a valid FAIL ({v["passed"]}/{v["tests"]}); overall counts remain 5 PASS / 26 FAIL. Full frozen method bundle and historical semantic scores remain unchanged. The previous canonical execution is retained in Git history.\n'
        if missing_bundle_files:
            old_text += f'\nRestored {len(missing_bundle_files)} supporting bundle files missing from the previous Git snapshot directly from the authentic rollout inputs; no existing bundle file was modified. The full {len(spec["bundle_sha256_by_file"])}-file bundle matches the frozen source SHA256 map. See [bundle reconciliation]({PUB}/bundle-reconciliation.json).\n'
        if assets:
            old_text += '\nThe authentic large snapshot is hosted as a Release asset; `python restore_files.py --download-assets` restores the standard task path and checks size/SHA. See [large-files.json](large-files.json).\n'
        readme.write_text(old_text, encoding='utf-8')
    print(json.dumps({'prepared': 2, 'base_commit': base_commit, 'release_tag': TAG}, ensure_ascii=True))


if __name__ == '__main__':
    main()
