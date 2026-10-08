"""Use the repository exporter for unique current and historical readable runs."""
import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

SCOPE = {'SkillTTA-GPT52-Gold31-Local30-20260924': 'organize-messy-files',
         'MMG2Skill-GPT52-Gold31-20260923': 'drone-planning-control'}


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worktree', required=True, type=Path)
    work = ap.parse_args().worktree.resolve()
    assert work.name == 'guard3-results-20261008'
    if os.name == 'nt':
        work = Path('\\\\?\\' + str(work))
    base = work / 'evaluation/results'
    spec = importlib.util.spec_from_file_location('guard3_two_canonical_exporter', base / 'export_trajectory.py')
    exporter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = exporter
    spec.loader.exec_module(exporter)
    original_iter = exporter.iter_acp_files
    result = []
    for name, tid in SCOPE.items():
        root = base / name
        pub = root / 'reruns/completion-guard3-two-20261008'
        previous = read(root / 'trajectory_timelines/trajectory_timeline_index.json')
        preferred = {e['source'] for e in previous['trajectories']}
        groups = {}
        for p in original_iter(root):
            meta = exporter.discover_meta(p.parent.parent)
            groups.setdefault((meta.task_id, meta.method_id, meta.run_id, meta.condition), []).append(p)
        chosen = []
        for paths in groups.values():
            matches = [p for p in paths if p.relative_to(root).as_posix() in preferred]
            canonical = [p for p in paths if p.relative_to(root).as_posix().startswith('tasks/')]
            chosen.append((matches or canonical or paths)[0])
        exporter.iter_acp_files = lambda _: iter(sorted(chosen))
        log = Path(__file__).parent / (name + '-trajectory-export.log')
        with log.open('w', encoding='utf-8') as out, contextlib.redirect_stdout(out):
            assert exporter.main(['--root', str(root), '--dry-run']) == 0
            assert exporter.main(['--root', str(root)]) == 0
        index = read(root / 'trajectory_timelines/trajectory_timeline_index.json')
        outputs = {e['output'] for e in index['trajectories']}
        for old in previous['trajectories']:
            if old['output'] not in outputs:
                p = root / old['output']
                assert p.resolve().is_relative_to((root / 'trajectory_timelines').resolve())
                if p.exists():
                    p.unlink()
        replacement_index = read(pub / 'replacement-index.json')
        selected = replacement_index['replacements'][0]['selected_rollout_id']
        current = next(e for e in index['trajectories'] if e['run_id'] == selected)
        assert current['execution_ok'] and not current['trajectory_empty'] and current['label'] == 'after'
        replacement_index['replacements'][0]['trajectory_timeline_after'] = current['output']
        write(pub / 'replacement-index.json', replacement_index)
        counts = {label: sum(e['label'] == label for e in index['trajectories']) for label in ('before', 'after', 'unknown')}
        assert counts['before'] == 31 and counts['unknown'] == 0
        if name.startswith('SkillTTA'):
            mf = read(root / 'MANIFEST.json')
            next(e for e in mf['entries'] if e['task_id'] == tid)['trajectory_timeline_after'] = current['output']
            mf['trajectory_timelines'].update(counts)
            write(root / 'MANIFEST.json', mf)
        else:
            mf = read(root / 'task-index.json')
            next(e for e in mf['tasks'] if e['task_id'] == tid)['trajectory_timeline_after'] = current['output']
            write(root / 'task-index.json', mf)
        shutil.copyfile(__file__, pub / 'recovery/export_timelines.py')
        result.append({'method': name, 'counts': counts, 'current_after': current['output']})
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
