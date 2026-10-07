"""Independent revision: faithful RGB comparison and source-bound typo repairs."""
from pathlib import Path
import ast
import difflib
import hashlib
import json
import runpy

ROOT=Path(__file__).resolve().parent
v1=runpy.run_path(str(ROOT.parent/'verifier-revision-v1/prepare_revision.py'))
before=v1['SOURCE'].read_text(encoding='utf-8')
helper=v1['HELPER']
insertion='@pytest.fixture(scope="session")\ndef mathjax_renderer():'
old='missing, extra = render_set_diff(expected_formulas, output_formulas, mathjax_renderer)'
new='missing, extra = render_set_diff_with_typo_repairs(expected_formulas, output_formulas, mathjax_renderer)'
pixel_old='diff = ImageChops.difference(img1, img2)'
pixel_new='diff = ImageChops.difference(img1, img2).convert("RGB")'
assert all(before.count(x)==1 for x in (insertion,old,pixel_old))
after=before.replace(insertion,helper+insertion).replace(old,new).replace(pixel_old,pixel_new)
assert after.replace(helper+insertion,insertion).replace(new,old).replace(pixel_new,pixel_old)==before
ast.parse(after)
dest=ROOT/'test_outputs.py'
assert not dest.exists()
dest.write_text(after,encoding='utf-8')
diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='original/test_outputs.py',tofile='revision-v2/test_outputs.py'))
assert 'EXPECTED_FORMULAS = ' not in diff
(ROOT/'checker.diff').write_text(diff,encoding='utf-8')
from PIL import Image,ImageChops
white=Image.new('RGBA',(2,2),'white')
black=Image.new('RGBA',(2,2),'black')
assert ImageChops.difference(white,black).getbbox() is None
assert ImageChops.difference(white,black).convert('RGB').getbbox() is not None
receipt=json.loads((ROOT.parent/'verifier-revision-v1/preparation.json').read_text())
receipt.update(revision_checker_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
    rgba_alpha_false_positive_reproduced=True,rgb_comparison_corrected=True,
    color_negative_control_passed=True,version='v2',v1_not_admitted_to_gold=True)
(ROOT/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
for name in ('verify_revision.sh','regression_checks.py'):
    source=(ROOT.parent/'verifier-revision-v1'/name).read_text()
    (ROOT/name).write_text(source,encoding='utf-8')
print(json.dumps(receipt))
