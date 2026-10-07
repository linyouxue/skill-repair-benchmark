"""Evaluate real historical output and diagnostic mutants, without model calls."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent.parents[1]
CID = '6f7a78f160b4'
ROLL = 'latex-formula-extraction-opus47-manual-round-1-r001-recovery002'

def main():
    revision = (ROOT/'test_outputs.py').read_text(encoding='utf-8')
    actual = (ROOT/'actual-after-reverification.md').read_text(encoding='utf-8')
    original = BASE/'expanded_original_skill_runs/opus47-openrouter-v1.1-20260919/runs/opus47-original-skill/latex-formula-extraction-opus47-original-skill-r001/verifier/latex_formula_extraction.md'
    assert original.is_file()
    rows = [v for v in actual.splitlines() if v.strip()]
    assert '+' in rows[-1]
    changed = list(rows)
    changed[-1] = changed[-1].replace('+','-',1)
    # Find the malformed submitted source without consulting oracle formulas.
    malformed = next(i for i,f in enumerate(rows[:-1]) if r'\left[' in f and r'\right)' in f and r'\dagger' in f)
    missing = [f for i,f in enumerate(rows) if i != malformed]
    controls = {
        'original-real-output': original.read_bytes(),
        'changed-correction-operand': ('\n'.join(changed)+'\n').encode(),
        'missing-preserved-original': ('\n'.join(missing)+'\n').encode(),
    }
    assert hashlib.sha256(controls['original-real-output']).hexdigest() == '9c7f554270cbd9a634cec5a4bfbb5ede1884d49156c9bf38adf655ed226abdec'
    c=json.loads(subprocess.check_output(['docker','inspect',CID],text=True))[0]
    assert c['Config']['Labels']['com.docker.compose.project']==ROLL and not c['State']['Running']
    subprocess.run(['docker','start',CID],check=True,stdout=subprocess.DEVNULL)
    summaries={}
    try:
        for name,data in controls.items():
            folder=ROOT/'negative-controls'/name
            assert not folder.exists()
            folder.mkdir(parents=True)
            (folder/'actual.md').write_bytes(data)
            (folder/'test_outputs.py').write_text(revision.replace(
                'ANSWER_FILE = Path("/root/latex_formula_extraction.md")',
                'ANSWER_FILE = Path("/tmp/verifier-negative/actual.md")',1),encoding='utf-8')
            subprocess.run(['docker','exec','-u','0',CID,'mkdir','-p','/tmp/verifier-negative','/logs/verifier-negative'],check=True)
            for f in ('actual.md','test_outputs.py'):
                subprocess.run(['docker','cp',str(folder/f),CID+':/tmp/verifier-negative/'+f],check=True,stdout=subprocess.DEVNULL)
            command='export PATH=/usr/local/bin:$PATH; uvx --with pytest==8.4.1 --with pytest-json-ctrf==0.3.5 --with pillow==10.4.0 --with playwright==1.57.0 pytest --ctrf /logs/verifier-negative/ctrf.json /tmp/verifier-negative/test_outputs.py -rA -v > /logs/verifier-negative/test-stdout.txt 2>&1'
            result=subprocess.run(['docker','exec','-u','0','-e','HTTP_PROXY=http://host.docker.internal:7890','-e','HTTPS_PROXY=http://host.docker.internal:7890',CID,'bash','-c',command])
            assert result.returncode==1, (name,result.returncode)
            for f in ('ctrf.json','test-stdout.txt'):
                subprocess.run(['docker','cp',CID+':/logs/verifier-negative/'+f,str(folder/f)],check=True,stdout=subprocess.DEVNULL)
            j=json.loads((folder/'ctrf.json').read_text())['results']
            summaries[name]={'exit_code':result.returncode,'summary':j['summary'],
                'tests':[{'name':v['name'],'status':v['status']} for v in j['tests']],
                'input_sha256':hashlib.sha256(data).hexdigest(),'diagnostic_only':True}
        assert summaries['original-real-output']['summary']['failed']==2
        assert summaries['changed-correction-operand']['summary']['failed']==1
        assert summaries['missing-preserved-original']['summary']['failed']==2
        (ROOT/'negative-control-receipt.json').write_text(json.dumps(summaries,indent=2)+'\n')
        print(json.dumps({name:v['summary'] for name,v in summaries.items()}))
    finally:
        subprocess.run(['docker','stop','--time','10',CID],check=True,stdout=subprocess.DEVNULL)

if __name__=='__main__':
    main()
