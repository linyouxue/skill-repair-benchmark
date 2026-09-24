"""Regression checks for no-tutorial and full-bundle MMG adapter, 2026-09-23."""
import tempfile
from pathlib import Path
import experiment as e
from anything2skill.parser.data_types import Skill, Skills

with tempfile.TemporaryDirectory() as tmp:
    e.ROOT=Path(tmp)
    original=e.ROOT/'originals/t/skills'
    (original/'test/scripts').mkdir(parents=True)
    (original/'test/SKILL.md').write_text('---\nname: test\ndescription: original\nlicense: keep-this\n---\n\nOriginal body\n')
    (original/'test/scripts/helper.py').write_bytes(b'print("support file must survive")\n')
    task={'task_id':'t','original_bundle':str(original),'skill_files':['test/SKILL.md']}
    skills,mapping=e.original_skills(task)
    assert e.overlay_bundle(task,skills,mapping)==[]
    updated=Skills('t','',[Skill('test','original','Changed body')])
    assert e.overlay_bundle(task,updated,mapping)==['test/SKILL.md']
    assert 'license: keep-this' in (e.ROOT/'submission/tasks/t/skills/test/SKILL.md').read_text()
    assert (e.ROOT/'submission/tasks/t/skills/test/scripts/helper.py').read_bytes()==(original/'test/scripts/helper.py').read_bytes()
    try: e.overlay_bundle(task,Skills('t','',[Skill('../escape','x','x')]),mapping)
    except AssertionError: pass
    else: raise AssertionError('Path/name escape accepted')
print('Full bundle, no-op byte preservation, metadata, and path guards passed')
