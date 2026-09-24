"""Regression for Syzkaller's unmatched body fence and explicit Skill boundary."""
from pathlib import Path
import json,re
import experiment as e
from runtime_fixes import parse_existing_skills
r=e.ROOT;checks={}
for task in e.read(r/'manifest.json')['tasks']:
    tid=task['task_id'];p=r/'generation'/tid/'refine_calls/call-001.response.json'
    if not p.exists():continue
    _,mapping=e.original_skills(task)
    text=e.read(p)['choices'][0]['message']['content'];parsed=parse_existing_skills(text,mapping)
    for s in parsed:
        existing=r/'submission/tasks'/tid/'skills'/mapping[s.name][0]
        if existing.exists():
            body=re.sub(r'^---\s*\n.*?\n---[^\S\n]*\n','',existing.read_text(encoding='utf-8'),count=1,flags=re.S).strip()
            assert s.content.strip()==body,(tid,s.name)
    checks[tid]=len(parsed)
    if tid=='syzkaller-ppdev-syzlang':
        assert len(parsed)==3
        assert 'PPCLAIM is defined for none of the arches\n```' in parsed[0].content
        assert parsed[0].content.count('```')%2==1, 'Do not repair the model body'
        assert '## Tutorial (source of truth)' in parsed[2].content
toy='# known\n> description\n\n```python\n# example\n> inside code\n```\n'
assert '# example' in parse_existing_skills(toy,{'known'})[0].content
receipt={'passed':True,'saved_responses_checked':checks,'model_body_unmodified':True,'paid_calls':0}
e.write(r/'skill-boundary-check.json',receipt);print(json.dumps(receipt))
