"""Regression for real MMG nested H1 parsing and missing /app export failures."""
import json,os,subprocess,tempfile
from pathlib import Path
import experiment as e
from runtime_fixes import parse_existing_skills,snapshot_command
root=e.ROOT
tasks={t['task_id']:t for t in e.read(root/'manifest.json')['tasks']}
for tid in ['azure-bgp-oscillation-route-leak','drone-planning-control','python-scala-translation','enterprise-information-search','pddl-airport-planning']:
    p=root/'generation'/tid/'refine_calls/call-001.response.json'
    text=e.read(p)['choices'][0]['message']['content']
    skills,mapping=e.original_skills(tasks[tid]);parsed=parse_existing_skills(text,mapping)
    assert {s.name for s in parsed}==set(mapping)
    if tid=='python-scala-translation': assert any('# Python' in s.content for s in parsed)
    if tid=='azure-bgp-oscillation-route-leak': assert '# Azure BGP Oscillation & Route Leak Analysis' in parsed[0].content
    print(tid,'parsed',len(parsed),'exact original skill identities; nested body preserved')
    with tempfile.TemporaryDirectory() as tmp:
        e.ROOT=Path(tmp);skills.skills=parsed;e.overlay_bundle(tasks[tid],skills,mapping)
    e.ROOT=root
toy='# first\n> description\n\n# Body heading\n```python\n# fake\n> still code\n```\n'
assert '# fake' in parse_existing_skills(toy,{'first'})[0].content
try:parse_existing_skills('# unexpected\n> d\nx',{'first'})
except AssertionError:pass
else:raise AssertionError('Unknown envelope accepted')
command='mkdir -p /home/agent; echo actual-output >/root/answer.txt; '+snapshot_command('/root')+'; tar -tzf /tmp/mmg-before-verifier.tar.gz; test ! -e /app'
result=subprocess.run(['docker','run','--rm','--network','none','ubuntu:24.04','bash','-c',command],capture_output=True,text=True)
assert result.returncode==0,(result.stdout,result.stderr)
assert 'root/answer.txt' in result.stdout
print('Real Docker /root archive succeeds without /app; output file included')
from benchflow.agents.openhands_runtime_cache import validate_openhands_runtime_archive
metadata=validate_openhands_runtime_archive(Path(os.environ['BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE']))
print('Pinned local OpenHands archive validated',metadata)
e.write(root/'recovery-checks-20260923.json',{'nested_h1_and_fenced_comments':'passed','five_saved_refiner_responses':'passed','missing_app_docker_snapshot':'passed','local_runtime':metadata})
