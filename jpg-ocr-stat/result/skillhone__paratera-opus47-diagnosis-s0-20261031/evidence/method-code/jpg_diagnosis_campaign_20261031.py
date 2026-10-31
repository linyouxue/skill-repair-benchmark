"""Host-only preparation, failure export and independent final evaluations."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

import adapter

HERE = Path(__file__).resolve().parent
PYTHON = Path('/home/linyuanjing/.venvs/skill-repair-benchmark-a16/bin/python')
PREVIOUS = Path('/home/linyuanjing/jpg-skillhone-opus47-20261030')


def command(args, cwd=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def prepare(root):
    if root.exists() and any(root.iterdir()):
        raise FileExistsError('Inspect the existing campaign before recovery; no duplicate launch')
    source = HERE / 'datasets'
    if adapter.git(source, 'rev-parse', 'HEAD') != '556fd216287be7e58480ed5a6dd935ca3370e639':
        raise ValueError('Published source revision changed; inspect before launch')
    root.mkdir(exist_ok=True)
    # Reuse the existing complete, frozen group2 export; unrelated live-tree
    # edits and lazily fetched Git blobs must not hold up the repair chain.
    existing = HERE/'campaigns/jpg-ocr-stat/eval'
    if adapter.read_json(existing/'campaign.json')['source_commit'] != adapter.git(source, 'rev-parse', 'HEAD'):
        raise ValueError('Existing group2 export uses another source revision')
    group_task = existing/'tasks/test/group_02/jpg-ocr-stat'
    images = group_task/'environment/workspace/dataset/img'
    if len(list(images.iterdir())) != 20:
        raise ValueError('Incomplete existing group2 export')
    for image in images.iterdir():
        if image.read_bytes() != (source/'jpg-ocr-stat/evaluation/group_02/images'/image.name).read_bytes():
            raise ValueError('Existing group2 export has different pixels')
    if (group_task/'verifier/stat_oracle.xlsx').read_bytes() != (source/'jpg-ocr-stat/evaluation/group_02/stat_oracle.xlsx').read_bytes():
        raise ValueError('Existing group2 export has another scoring reference')
    shutil.copytree(group_task, root/'final-eval/tasks/group_02/jpg-ocr-stat')
    command(['git', 'clone', '--quiet', '--no-hardlinks', '--single-branch', '--branch', 'main', PREVIOUS/'skill', root/'skill'])
    adapter.git(root/'skill', 'remote', 'remove', 'origin')
    adapter.git(root/'skill', 'config', 'user.name', 'Local SkillHone experiment')
    adapter.git(root/'skill', 'config', 'user.email', 'local@invalid')
    seed = adapter.git(root/'skill', 'rev-parse', 'HEAD')
    shutil.copytree(PREVIOUS/'eval', root/'eval', ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    for name in ['adapter.py', 'jpg_runtime_20261030.py', 'openhands_jpg_vision_hook.py']:
        shutil.copy2(HERE/name, root/'eval'/name)
    config = adapter.read_json(root/'eval/campaign.json')
    config.update(seed_commit=seed, reuse_probe_results=False, allowed_splits=['probe'])
    config.pop('probe_cache_dir', None)
    adapter.write_json(root/'eval/campaign.json', config)
    adapter.commit_repo(root/'eval')
    state = root/'state'
    (state/'harness').mkdir(parents=True)
    (state/'harness/node_modules').symlink_to(PREVIOUS/'state/harness/node_modules', target_is_directory=True)
    shutil.copytree(PREVIOUS/'state/harness/home/profiles', state/'harness/home/profiles')
    (state/'harness/home/AGENTS.md').write_text(
        'This is a new isolated SkillHone diagnosis-driven repair. No Codex chat is provided. '
        'Read TRAINING.md and the complete published training diagnosis. Inspect actual receipt pixels with native read_image. '
        'Only edit existing skills/**/SKILL.md bodies; preserve frontmatter, support files, training data and licenses. '
        'Do not add files, scripts, tests or references. Do not encode receipt-specific answers. '
        'Only the host-provided training feedback under .git/iteration-feedback is additionally allowed. '
        'Never inspect Eval repositories, verifier/oracle, group_02 or other held-out data or results. '
        'Do not spawn subagents, invoke SkillHone, modify its records, merge or push.\n', encoding='utf-8')
    feedback = adapter.read_json(root/'skill/training-context/diagnosis/outputs/allowed_feedback.json')
    s0 = {'kind': 'imported_historical_diagnosis', 'source_commit': config['source_commit'],
          'source_run': 'jpg-ocr-stat-opus47-original-skill-r003-infra-recovery',
          'score': feedback['reward'], 'original_native_reward': feedback['original_reward'],
          'score_semantics': feedback['kind'], 'n_total': 1, 'n_passed': 0,
          'feedback_path': 'training-context/diagnosis/outputs/allowed_feedback.json',
          'new_model_calls': 0, 'not_a_new_paratera_baseline': True}
    adapter.write_json(root/'s0.json', s0)
    adapter.write_json(root/'preparation.json', {'root': str(root), 'seed': seed,
        'source_commit': config['source_commit'], 'model': 'paratera/Claude-Opus-4.7',
        'repair_rounds_max': 5, 'additional_original_runs': 2, 'group_02_runs': 3,
        'parent_iterations': 65, 'max_parallel_evaluations': 3,
        'group_02_available_to_repair': False, 'check': adapter.check(root/'eval', root/'skill')})
    node = HERE/'.runtime/node-v24.19.0-linux-x64/bin/node'
    import register
    register.cli(node, HERE/'SkillHone', state, root/'skill', 'config', 'set', '--merge', 'review', '--trigger', 'queued')
    register.cli(node, HERE/'SkillHone', state, root/'skill', 'benchmark', 'init', '--eval-repo', str(root/'eval'), '--runner', register.runner(PYTHON))
    return {'prepared': True, 'seed': seed, 's0_score': s0['score'], 'new_model_calls': 0}


def validate(root, workspace):
    adapter.check(root/'eval', workspace)
    for source in (root/'eval/reference_skills').rglob('SKILL.md'):
        actual = workspace/'skills'/source.relative_to(root/'eval/reference_skills')
        original_text = source.read_text()
        if original_text.startswith('---\n'):
            front = original_text.split('---', 2)[1]
            if not actual.read_text().startswith('---' + front + '---'):
                raise ValueError('Only Skill body edits are permitted')
    return {'candidate_scope_valid': True}


def stage_failure(root, benchmark_id, output):
    # Only actual model-visible streams and allowed field feedback cross into
    # the repair workspace. No verifier stdout, gold, code or generalization.
    benchmark = root/'state/projects'
    matches = [root/'recovered-probe.json'] if benchmark_id == 'round-1-recovered-probe' else list(benchmark.glob(f'*/benchmark/results/{benchmark_id}.json'))
    if len(matches) != 1:
        raise ValueError('Cannot uniquely locate the actual probe result')
    result = adapter.read_json(matches[0])
    if result.get('n_total') != 1 or len(result['traces']) != 1:
        raise ValueError('Expected one complete original task per development round')
    run = Path(result['traces'][0]['result_json']).parent
    output.mkdir(parents=True, exist_ok=False)
    names = ['trajectory/acp_trajectory.jsonl', 'trajectory/llm_trajectory.jsonl', 'trainer/atif.json']
    copied = []
    for name in names:
        source = run/name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = output/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(name)
    shutil.copy2(run/'verifier/accuracy.json', output/'allowed_feedback.json')
    with tarfile.open(run/'artifacts/pre-verifier-workspace.tar.gz') as archive:
        matches = [m for m in archive.getmembers() if m.name.lstrip('./') == 'workspace/stat_ocr.xlsx' and m.isfile()]
        if matches:
            (output/'stat_ocr.xlsx').write_bytes(archive.extractfile(matches[0]).read())
    adapter.write_json(output/'index.json', {'kind': 'actual_failed_original_probe',
        'source_run': str(run),
        'score': result['score'], 'streams': copied,
        'feedback': 'allowed_feedback.json', 'model_calls_added_by_export': 0})
    return {'exported_failure': True, 'score': result['score'], 'streams': len(copied)}


def image_audit(root, round_dir):
    path = round_dir/'dsh-image-audit.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    outgoing = [r for r in rows if r['phase'] == 'request']
    responses = [r for r in rows if r['phase'] == 'response']
    evidence = {'requests_observed': len(outgoing),
        'requests_with_actual_image_blocks': sum(r['image_blocks'] > 0 for r in outgoing),
        'max_inline_image_blocks': max((r['inline_image_blocks'] for r in outgoing), default=0),
        'native_read_image_calls_in_request_history': max((r.get('read_image_calls_in_history', 0) for r in outgoing), default=0),
        'successful_responses_after_image_requests': sum(r['status'] == 200 and r['image_blocks'] > 0 for r in responses),
        'all_22_images_read_claimed': False}
    evidence['actual_image_send_verified'] = evidence['max_inline_image_blocks'] > 0 and evidence['successful_responses_after_image_requests'] > 0
    adapter.write_json(round_dir/'dsh-image-evidence.json', evidence)
    return evidence


def final_pool(root, phase):
    selection = adapter.read_json(root/'selection.json')
    if adapter.git(root/'skill', 'rev-parse', 'HEAD') != selection['commit']:
        raise ValueError('Selected Skill changed after freezing')
    adapter.check(root/'eval', root/'skill')
    evaluation = root/'eval'
    if phase == 'original':
        task = evaluation/'tasks/probe/jpg-ocr-stat'
        count = 2
    else:
        task = root/'final-eval/tasks/group_02/jpg-ocr-stat'
        if not task.exists():
            adapter.export_group(root/'evaluation-source/jpg-ocr-stat', 'group_02', task)
        count = 3
    output = root/'final-evaluations'/phase
    output.mkdir(parents=True, exist_ok=True)
    config = adapter.read_json(evaluation/'campaign.json')
    jobs = []
    for repeat in range(1, count+1):
        response = output/f'repeat-{repeat}.response.json'
        if response.exists():
            jobs.append((None, response, None))
            continue
        request_file = output/f'repeat-{repeat}.request.json'
        if request_file.exists():
            raise RuntimeError('An existing unfinished final evaluation requires infrastructure recovery')
        request = {'executor_root': config['executor_root'], 'task_dir': str(task), 'task_id': 'jpg-ocr-stat',
            'execution_budget_scope': 'jpg-isolated-worker-65', 'parent_iterations': 65,
            'model': 'paratera/Claude-Opus-4.7', 'reasoning_effort': None,
            'jobs_root': str(output/'jobs'), 'skill_bundle': str(root/'skill/skills'),
            'stage': f'frozen-{phase}-repeat-{repeat}',
            'rollout_id': f'jpg-frozen-{phase}-r{repeat}-{uuid.uuid4().hex[:10]}'}
        adapter.write_json(request_file, request)
        jobs.append((request_file, response, output/f'repeat-{repeat}.log'))
    def execute(job):
        request, response, log = job
        if request is not None:
            with log.open('w') as stream:
                child = subprocess.Popen([str(PYTHON), str(evaluation/'adapter.py'), '_worker', str(request), str(response)],
                    cwd=config['executor_root'], stdout=stream, stderr=subprocess.STDOUT)
                adapter.write_json(response.with_suffix('.launch.json'), {'pid': child.pid, 'request': str(request)})
                status = child.wait()
            if status:
                return {'execution_ok': False, 'request': str(request), 'exit_code': status}
        return dict(adapter.read_json(response), execution_ok=True, response=str(response))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [future.result() for future in as_completed([pool.submit(execute, job) for job in jobs])]
    adapter.write_json(output/'summary.json', {'selected_commit': selection['commit'], 'phase': phase,
        'n_expected': count, 'n_valid': sum(r['execution_ok'] for r in results), 'results': results,
        'used_for_selection': False})
    if not all(r['execution_ok'] for r in results):
        raise RuntimeError('Final evaluation infrastructure requires recovery; completed valid results retained')
    return {'phase': phase, 'n_valid': count, 'mean_reward': sum(r['reward'] for r in results)/count}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'validate', 'failure', 'image-audit', 'final'])
    parser.add_argument('root', type=Path)
    parser.add_argument('extra', nargs='*')
    args = parser.parse_args()
    if args.action == 'prepare': value = prepare(args.root)
    elif args.action == 'validate': value = validate(args.root, Path(args.extra[0]))
    elif args.action == 'failure': value = stage_failure(args.root, args.extra[0], Path(args.extra[1]))
    elif args.action == 'image-audit': value = image_audit(args.root, Path(args.extra[0]))
    else: value = final_pool(args.root, args.extra[0])
    print(json.dumps(value, ensure_ascii=True))
