"""Store accepted publication checks and normalize only derived layout metadata."""
import argparse
import json
import os
from pathlib import Path
import shutil

Q = Path(__file__).resolve().parents[1]
METHODS = ('MMG2Skill-GPT52-Gold31-20260923', 'SkillTTA-GPT52-Gold31-Local30-20260924')
ap = argparse.ArgumentParser()
ap.add_argument('--worktree', required=True, type=Path)
work = ap.parse_args().worktree.resolve()
assert work.name == 'guard3-results-20261008'
if os.name == 'nt':
    work = Path('\\\\?\\' + str(work))
check = json.loads((Q / 'publication/publication-check.json').read_text(encoding='utf-8'))
assert check['status'] == 'verified_for_publication' and not check['credential_scan_findings']
for name in METHODS:
    root = work / 'evaluation/results' / name
    timeline = root / 'trajectory_timelines/trajectory_timeline_index.json'
    before = timeline.read_bytes()
    clean = before.replace(b'\r\n', b'\n')
    assert json.loads(clean) == json.loads(before)
    timeline.write_bytes(clean)
    if name.startswith('SkillTTA'):
        p = root / 'STATUS.csv'
        p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))
    pub = root / 'reruns/completion-guard3-two-20261008'
    report = {**check, 'replacement_checks': [r for r in check['replacement_checks'] if r['method'] == name],
              'scope_note': 'Global pre-publication scan; this method directory stores only its corresponding replacement evidence.'}
    (pub / 'publication-check.json').write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8', newline='\n')
    for source in ('verify_publication.py', 'record_verified_layout.py'):
        shutil.copyfile(Path(__file__).parent / source, pub / 'recovery' / source)
print('Accepted publication checks stored; only derived line endings normalized.')
