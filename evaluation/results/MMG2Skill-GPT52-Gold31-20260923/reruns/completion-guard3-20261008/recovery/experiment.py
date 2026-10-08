"""Five explicitly authorized guard3 fresh reruns; reuse frozen method bundles."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
EXECUTOR = PROJECT.parent / 'skill-repair-benchmark'
CF = PROJECT / 'causalflow_runs/opus47-gold15-20260922'
MODEL = 'openai/gpt-5.2'
SELECTION = {
    'skilltta': ('skilltta_runs/gpt52-gold31-20260924', [
        'azure-bgp-oscillation-route-leak', 'energy-unit-commitment',
        'reserves-at-risk-calc', 'python-scala-translation']),
    'mmg2skill': ('mmg2skill_runs/gpt52-gold31-20260923', ['dialogue-parser']),
}
sys.path[:0] = [str(EXECUTOR / 'src'), str(CF / 'source'), str(CF / '.deps')]


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def file_manifest(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


def base_runtime():
    return load('_guard3_cf_preflight', CF / 'experiment.py').previous().runtime()


def prepare():
    assert not (ROOT / 'manifest.json').exists(), 'Already prepared: preserve frozen inputs'
    old = base_runtime()
    rows = []
    for method, (relative, tids) in SELECTION.items():
        source = PROJECT / relative
        manifest = read(source / 'manifest.json')
        target = source / 'reruns/completion-guard3-20261008'
        assert not target.exists(), f'Existing rerun root: {target}'
        target.mkdir(parents=True)
        (target / 'infra-cache').symlink_to(source / 'infra-cache', target_is_directory=True)
        write(target / 'manifest.json', {**manifest, 'tasks': [t for t in manifest['tasks'] if t['task_id'] in tids]})
        recovery = {}
        for tid in tids:
            task = next(t for t in manifest['tasks'] if t['task_id'] == tid)
            state = read(source / 'task_state' / f'{tid}.json')
            previous_result = Path(state['result_path'])
            result = read(previous_result)
            assert result['execution_ok'] and result['task_passed'] is False
            assert not result.get('error') and not result.get('verifier_error') and not result.get('export_error')
            bundle = source / 'submission/tasks' / tid / 'skills'
            copied = target / 'submission/tasks' / tid / 'skills'
            shutil.copytree(bundle, copied)
            digest = file_manifest(bundle)
            assert digest == file_manifest(copied)
            assert digest == file_manifest(previous_result.parent / 'inputs/skills')
            adapter = source / 'generation' / tid / 'adapter_result.json'
            copied_adapter = target / 'generation' / tid / 'adapter_result.json'
            copied_adapter.parent.mkdir(parents=True)
            shutil.copyfile(adapter, copied_adapter)
            spec = old.base.parse_task_spec(Path(manifest['tasks_root']) / tid)
            rid = f'{tid}-{method}-gpt52-guard3-20261008-r001'
            row = {'slot': f'{method}__{tid}', 'method': method, 'task_id': tid,
                   'source_batch': str(source), 'rerun_root': str(target),
                   'method_id': manifest['method_id'], 'tasks_root': manifest['tasks_root'],
                   'rollout_id': rid, 'previous_result': str(previous_result),
                   'bundle_sha256_by_file': digest, 'method_reused': True,
                   'memory_mb': spec.memory_mb, 'cpus': spec.cpus, 'exclusive': spec.exclusive}
            rows.append(row)
            recovery[tid] = {'fresh_rollout_id': rid,
                             'reason': 'Explicit user-authorized fresh retry with guard3; preserve old valid FAIL'}
        write(target / 'recovery_queue.json', recovery)
        proof = source / 'runtime-cache/reserves-at-risk-calc/prebuilt-image.json'
        if 'reserves-at-risk-calc' in tids and proof.exists():
            dest = target / 'runtime-cache/reserves-at-risk-calc/prebuilt-image.json'
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(proof, dest)
    fixes = (PROJECT / SELECTION['skilltta'][0] / 'runtime_fixes.py').read_text()
    fixes = fixes.replace("tag='skilltta-initial-reserves-at-risk-calc:20260924'",
                          "tag='skilltta-guard3-initial-reserves-at-risk-calc:20261008'")
    (ROOT / 'runtime_fixes.py').write_text(fixes, encoding='utf-8')
    protocol = {'authorized_at_local_date': '2026-10-08', 'scope': [r['slot'] for r in rows],
                'authorization': 'User explicitly requested these five reruns with completion gate raised to 3',
                'model': MODEL, 'reasoning': 'omitted', 'max_output_tokens': 32768,
                'parent_iterations': 60, 'text_only_retry_limit_per_step': 3,
                'uses_remaining_parent_iteration_budget': True,
                'protocol_variation': 'User-authorized guard3; historical guard1 results retained',
                'method_generation_calls': 0, 'original_skill_runs': 0,
                'local_max_workers': 2, 'global_max_workers': 3, 'memory_mb': 11264,
                'auto_gold': False, 'auto_publish': False, 'auto_retry_on_error': False,
                'source_executor_commit': subprocess.check_output(['git', '-C', str(EXECUTOR), 'rev-parse', 'HEAD'], text=True).strip(),
                'known_limitations': 'Inherited original harness limitations, including Python-to-Scala reconstructed inputs, remain disclosed.'}
    write(ROOT / 'protocol.json', protocol)
    write(ROOT / 'manifest.json', {'tasks': rows, 'prepared_at': now()})
    (ROOT / 'worker_logs').mkdir()
    print('prepared five frozen-bundle fresh reruns', flush=True)


def preflight(probe=False):
    from benchflow.benchmark_executor import completion_guard_metadata
    old = base_runtime()
    assert completion_guard_metadata(3)['enabled']
    rows = read(ROOT / 'manifest.json')['tasks']
    for row in rows:
        target = Path(row['rerun_root'])
        assert file_manifest(target / 'submission/tasks' / row['task_id'] / 'skills') == row['bundle_sha256_by_file']
        assert (Path(row['tasks_root']) / row['task_id'] / 'environment/Dockerfile').is_file()
        if row['task_id'] == 'python-scala-translation':
            from skillsbench_replay.task_dependency_cache import dependency_archive
            archive, _ = dependency_archive(target / 'infra-cache', row['task_id'])
            assert archive.is_file()
    archives = [os.environ['BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE'],
                old.infra_support.PYTHON_ARCHIVE, old.infra_support.UV_ARCHIVE,
                old.infra_support.CRYPTO_WHEEL]
    assert all(Path(p).is_file() for p in archives)
    active = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    assert not active, 'Preflight expects no unaccounted active containers'
    proof = {'at': now(), 'tasks': rows, 'guard': completion_guard_metadata(3),
             'runtime_archives_present': True, 'frozen_bundles_verified': True,
             'docker_server': subprocess.check_output(['docker', 'version', '--format', '{{.Server.Version}}'], text=True).strip(),
             'model_probe': False}
    write(ROOT / 'preflight.json', proof)
    if probe:
        assert not (ROOT / 'preflight-model/pending.json').exists(), 'Prior probe must be reconciled'
        cf = load('_guard3_cf_probe', CF / 'experiment.py')
        cf.ensure_openrouter_key()
        from openai import OpenAI
        request = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'Reply only OK.'}], 'max_tokens': 16}
        write(ROOT / 'preflight-model/request.json', request)
        write(ROOT / 'preflight-model/pending.json', {'started_at': now()})
        client = OpenAI(api_key=os.environ['OPENROUTER_API_KEY'], base_url='https://openrouter.ai/api/v1', timeout=120, max_retries=0)
        try:
            reply = client.chat.completions.create(**request).model_dump(exclude_none=True)
            write(ROOT / 'preflight-model/response.json', reply)
            assert reply['choices'][0]['message'].get('content')
        except Exception as exc:
            write(ROOT / 'preflight-model/error.json', {'type': type(exc).__name__, 'error': str(exc), 'at': now()})
            raise
        finally:
            client.close()
        proof['model_probe'] = True
        proof['probe_model'] = reply['model']
        write(ROOT / 'preflight.json', proof)
    print(json.dumps({'offline_preflight': True, 'model_probe': proof['model_probe'],
                      'tasks': [{k: r[k] for k in ('slot', 'memory_mb', 'exclusive')} for r in rows]}), flush=True)


def worker(slot):
    row = next(r for r in read(ROOT / 'manifest.json')['tasks'] if r['slot'] == slot)
    source, target = Path(row['source_batch']), Path(row['rerun_root'])
    sys.path.insert(0, str(source))
    experiment = load('experiment', source / 'experiment.py')
    experiment.ROOT = target
    original_cf_module = experiment.cf_module

    def cf_module_guard3():
        cf = original_cf_module()
        fresh_runtime = cf.fresh_runtime

        def fresh_with_guard3(tid):
            old = fresh_runtime(tid)
            old.base.TASKS_ROOT = Path(row['tasks_root'])
            old.base.RUNS_ROOT = target / 'runs'
            original_compose_paths = old.base.DockerSandbox._docker_compose_paths
            overlay = ROOT / 'network-overlays' / f'{slot}.json'
            assert overlay.is_file(), 'Verified per-run network overlay is required'
            old.base.DockerSandbox._docker_compose_paths = property(
                lambda sandbox: original_compose_paths.fget(sandbox) + [overlay]
            )
            constructor = old.original_executor

            def guard3_executor(**kwargs):
                assert kwargs['experimental_text_only_retry_limit'] == 1
                kwargs['experimental_text_only_retry_limit'] = 3
                return constructor(**kwargs)

            old.original_executor = guard3_executor
            return old

        cf.fresh_runtime = fresh_with_guard3
        return cf

    experiment.cf_module = cf_module_guard3
    load('runtime_fixes', ROOT / 'runtime_fixes.py')
    try:
        if hasattr(experiment, 'ensure_runtime_environment'):
            experiment.ensure_runtime_environment()
        experiment.cf_module().ensure_openrouter_key()
        run = target / 'runs' / row['method_id'] / row['rollout_id']
        assert not run.exists(), 'Existing fresh attempt: never blindly repeat a paid run'
        task = next(t for t in read(target / 'manifest.json')['tasks'] if t['task_id'] == row['task_id'])
        asyncio.run(experiment.fresh(task))
    except BaseException as exc:
        experiment.progress(row['task_id'], 'error', rollout='NOT_RUN', error=f'{type(exc).__name__}: {exc}')
        traceback.print_exc()
        raise SystemExit(1)


def external_workers():
    occupied = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parts = (entry / 'cmdline').read_bytes().split(b'\0')
            if b'--worker' not in parts:
                continue
            script = next(Path(p.decode()) for p in parts if p.endswith(b'/experiment.py'))
            if script == Path(__file__).resolve():
                continue
            tid = parts[parts.index(b'--worker') + 1].decode()
            proof = read(script.parent / 'preflight.json')
            spec = next(s for s in proof['tasks'] if s['task_id'] == tid)
            occupied.append(spec)
        except (OSError, StopIteration, ValueError, KeyError, IndexError):
            if 'parts' in locals() and b'--worker' in parts:
                occupied.append({'memory_mb': 11264, 'exclusive': True})
    return occupied


async def controller(resume=False):
    lock = (ROOT / 'controller.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert read(ROOT / 'preflight.json')['model_probe']
    previous = None
    if (ROOT / 'batch_state.json').exists():
        assert resume, 'Explicit verified infrastructure recovery required'
        previous = read(ROOT / 'batch_state.json')
        plan = read(ROOT / 'resume-plan.json')
        assert plan['passed'] and not plan.get('consumed_at'), 'Verified unconsumed recovery plan required'
        assert plan['batch_state_sha256'] == hashlib.sha256((ROOT / 'batch_state.json').read_bytes()).hexdigest(), 'State changed after recovery checks'
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit() or int(entry.name) == os.getpid():
                continue
            try:
                assert str(Path(__file__).resolve()).encode() not in (entry / 'cmdline').read_bytes(), 'Existing controller/worker: do not duplicate'
            except OSError:
                pass
    else:
        assert not resume, 'No prior state to recover'
    rows = sorted(read(ROOT / 'manifest.json')['tasks'], key=lambda r: (r['exclusive'], r['memory_mb'], r['slot']))
    if previous is not None:
        pending = []
        for row in rows:
            saved = previous['tasks'][row['slot']]
            run = Path(row['rerun_root']) / 'runs' / row['method_id'] / row['rollout_id']
            if saved.get('phase') == 'finished':
                assert saved['fresh_rollout_id'] == row['rollout_id']
                assert Path(saved['result_path']) == run / 'benchmark_result.json'
                result = read(run / 'benchmark_result.json')
                assert result['execution_ok'] and isinstance(result['task_passed'], bool)
                assert not any(result.get(k) for k in ('error', 'verifier_error', 'export_error'))
                assert saved['rollout'] == ('PASS' if result['task_passed'] else 'FAIL')
                for name in ('trajectory/acp_trajectory.jsonl', 'trajectory/llm_trajectory.jsonl', 'results.jsonl'):
                    assert (run / name).is_file() and (run / name).stat().st_size > 0
            else:
                assert row['slot'] in plan['slots'] and saved['phase'] == 'pending'
                assert plan['rollout_ids'][row['slot']] == row['rollout_id']
                assert not run.exists(), 'Existing provider attempt requires checkpoint reconciliation'
                assert file_manifest(Path(row['rerun_root']) / 'submission/tasks' / row['task_id'] / 'skills') == row['bundle_sha256_by_file']
                pending.append(row)
        assert {r['slot'] for r in pending} == set(plan['slots']), 'Recovery must only dispatch explicitly checked slots'
        rows = pending
        state = previous
        state.update(status='running', resumed_at=now(), auto_gold=False, auto_publish=False)
        state.pop('finished_at', None)
        plan['consumed_at'] = now()
        write(ROOT / 'resume-plan.json', plan)
    else:
        state = {'status': 'running', 'started_at': now(), 'guard_limit': 3,
                 'tasks': {r['slot']: {'phase': 'pending', 'rollout': 'pending'} for r in rows},
                 'auto_gold': False, 'auto_publish': False}
    write(ROOT / 'batch.pid', os.getpid())
    live, logs = {}, {}
    while rows or live:
        for slot, (proc, row) in list(live.items()):
            path = Path(row['rerun_root']) / 'task_state' / f"{row['task_id']}.json"
            if path.exists():
                state['tasks'][slot].update(read(path))
            if proc.poll() is not None:
                if state['tasks'][slot]['phase'] not in ('finished', 'error'):
                    state['tasks'][slot].update(phase='error', rollout='NOT_RUN', error='Worker exited without terminal evidence')
                logs.pop(slot).close()
                live.pop(slot)
        with Path('/tmp/mmg2skill-resource-dispatch.lock').open('a') as dispatch:
            fcntl.flock(dispatch, fcntl.LOCK_EX)
            occupied = external_workers() + [row for _, row in live.values()]
            if rows and len(live) < 2 and len(occupied) < 3:
                row = rows[0]
                total = int(re.search(r'MemTotal:\s+(\d+)', Path('/proc/meminfo').read_text()).group(1)) // 1024
                fits = row['memory_mb'] + sum(s['memory_mb'] for s in occupied) <= min(total, 11264)
                exclusive = not occupied or (not row['exclusive'] and not any(s['exclusive'] for s in occupied))
                containers = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).splitlines()
                own_ids = [r['rollout_id'] for _, r in live.values()]
                accounted = all(any(rid in name for rid in own_ids) for name in containers)
                if fits and exclusive and accounted and shutil.disk_usage('/mnt/c').free >= 15 * 1024**3:
                    slot = row['slot']
                    log = (ROOT / 'worker_logs' / f'{slot}.log').open('ab', buffering=0)
                    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', slot],
                                            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                            start_new_session=True, cwd=ROOT)
                    live[slot] = (proc, row)
                    logs[slot] = log
                    rows.pop(0)
                    state['tasks'][slot].update(phase='starting', worker_pid=proc.pid)
            state['updated_at'] = now()
            write(ROOT / 'batch_state.json', state)
        if rows or live:
            await asyncio.sleep(5)
    state['status'] = 'ready_for_execution_audit' if all(r.get('phase') == 'finished' and r.get('rollout') in ('PASS', 'FAIL') for r in state['tasks'].values()) else 'blocked_incomplete_validation'
    state['finished_at'] = now()
    write(ROOT / 'batch_state.json', state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--resume-queue', action='store_true')
    parser.add_argument('--recover-reserves-build', action='store_true')
    parser.add_argument('--worker')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.preflight:
        preflight(args.probe)
    elif args.worker:
        worker(args.worker)
    elif args.recover_reserves_build:
        load('_guard3_reserves_build_recovery', ROOT / 'recover_reserves_build.py').recover()
    elif args.run or args.resume_queue:
        asyncio.run(controller(args.resume_queue))
    else:
        parser.error('select --prepare, --preflight, --run, or --worker')
