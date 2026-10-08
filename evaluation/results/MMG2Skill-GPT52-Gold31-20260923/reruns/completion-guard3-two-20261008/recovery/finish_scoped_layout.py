"""Preserve unrelated baseline Markdown bytes and finalize bounded publication layout."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

SCOPE = {'SkillTTA-GPT52-Gold31-Local30-20260924': 'organize-messy-files',
         'MMG2Skill-GPT52-Gold31-20260923': 'drone-planning-control'}
Q = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worktree', required=True, type=Path)
    work = ap.parse_args().worktree.resolve()
    assert work.name == 'guard3-results-20261008'
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=work)
    base = Path('\\\\?\\' + str(work)) if os.name == 'nt' else work
    changes = git('diff', '--name-only', '-z').decode().strip('\0').split('\0')
    restored = []
    for rel in changes:
        if not rel:
            continue
        parts = Path(rel).parts
        assert parts[:2] == ('evaluation', 'results') and parts[2] in SCOPE
        if parts[3] == 'trajectory_timelines' and rel.endswith('.md') and not Path(rel).name.startswith(SCOPE[parts[2]] + '__'):
            (base / rel).write_bytes(git('show', 'HEAD:' + rel))
            restored.append(rel)
        elif len(parts) == 4 and parts[3] in ('README.md', 'submission.json', 'task-index.json', 'partial-execution-summary.json', 'MANIFEST.json', 'protocol.json'):
            p = base / rel
            p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))
    for name in SCOPE:
        dest = base / 'evaluation/results' / name / 'reruns/completion-guard3-two-20261008/recovery'
        for script in ('prepare_replacements.py', 'export_timelines.py', 'finish_scoped_layout.py'):
            shutil.copyfile(Path(__file__).parent / script, dest / script)
    print(json.dumps({'unrelated_generated_timelines_preserved': len(restored), 'raw_evidence_and_skill_bytes_not_modified': True}))


if __name__ == '__main__':
    main()
