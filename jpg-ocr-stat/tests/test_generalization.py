"""Guards commit 2e1a410's 22-ticket contract when adding frozen 20-ticket tasks.

Only synthetic fixtures are executed; no old experiment or paid agent is run.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_score_accuracy import fixture_xlsx

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / 'evaluation'))
sys.path.insert(0, str(TASK / 'verifier'))
import score_results
from prepare_task import prepare
from score_accuracy import HEADER, read_oracle, score
from write_reward import validated_reward


class Generalization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jpg-generalization-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'task/evaluation'
        self.root.mkdir(parents=True)
        self.groups = {}
        self.rows = {}
        for g in score_results.GROUPS:
            names = [f'{g}_synthetic_{i:02d}.png' for i in range(20)]
            self.groups[g] = [{'filename': n, 'source_id': n} for n in names]
            self.rows[g] = [HEADER] + [[n, '2000-01-01', '10.00'] for n in names]
            folder = self.root / g
            (folder / 'images').mkdir(parents=True)
            for n in names:
                (folder / 'images' / n).write_bytes(b'synthetic-image-fixture')
            fixture_xlsx(folder / 'stat_oracle.xlsx', self.rows[g])
        self.save_manifest()
        self.predictions = self.base / 'predictions'
        self.predictions.mkdir()

    def save_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps({'groups': self.groups}))

    def spec(self, g='group_01'):
        return score_results.group_spec(self.groups[g])

    def actual(self, g, rows):
        folder = self.predictions / g
        folder.mkdir(exist_ok=True)
        fixture_xlsx(folder / 'stat_ocr.xlsx', rows)
        return folder / 'stat_ocr.xlsx'

    def test_twenty_fixed_fields_and_missing_delivery(self):
        g = 'group_01'
        oracle = self.root / g / 'stat_oracle.xlsx'
        actual = self.actual(g, self.rows[g])
        self.assertEqual(score(actual, oracle, self.spec())['reward'], 1)
        wrong = copy.deepcopy(self.rows[g]); wrong[1][2] = '11.00'
        self.actual(g, wrong)
        self.assertEqual(score(actual, oracle, self.spec())['reward'], 39/40)
        self.actual(g, self.rows[g][:-1])
        self.assertEqual(score(actual, oracle, self.spec())['reward'], 38/40)
        actual.unlink()
        report = score(actual, oracle, self.spec())
        self.assertEqual(report['reward'], 0)
        self.assertEqual(report['all_receipts']['fields'], 40)

    def test_twenty_oracle_requires_explicit_fixed_membership(self):
        oracle = self.root / 'group_01/stat_oracle.xlsx'
        with self.assertRaises(RuntimeError):
            read_oracle(oracle)  # Original 22-ticket contract remains strict.
        spec = self.spec(); spec['filenames'][0] = 'wrong_source.png'
        spec['filenames'].sort()
        with self.assertRaises(RuntimeError):
            read_oracle(oracle, spec)

    def test_three_groups_keep_120_fields_when_third_is_missing(self):
        for g in ('group_01', 'group_02'):
            self.actual(g, self.rows[g])
        report = score_results.evaluate(self.predictions, self.root)
        self.assertEqual(report['overall']['fields'], 120)
        self.assertEqual(report['overall']['field_correct'], 80)
        self.assertEqual(report['overall']['field_accuracy'], 2/3)
        self.assertEqual(report['groups']['group_03']['reward'], 0)
        self.assertNotIn('2000-01-01', json.dumps(report))
        self.assertEqual(report['model_calls'], 0)

    def test_manifest_rejects_duplicates_missing_members_and_paths(self):
        original = copy.deepcopy(self.groups)
        cases = []
        broken = copy.deepcopy(original); broken['group_01'].pop(); cases.append(broken)
        broken = copy.deepcopy(original); broken['group_02'][0]['source_id'] = broken['group_01'][0]['source_id']; cases.append(broken)
        broken = copy.deepcopy(original); broken['group_01'][0]['filename'] = '../escape.png'; cases.append(broken)
        for groups in cases:
            self.groups = groups; self.save_manifest()
            with self.assertRaises(ValueError):
                score_results.load_groups(self.root)

    def make_task(self):
        task = self.root.parent
        (task / 'task.md').write_text('original task fixture')
        environment = task / 'environment'; environment.mkdir()
        (environment / 'Dockerfile').write_text('FROM synthetic-offline-fixture')
        for i in range(5):
            folder = environment / 'skills' / f'skill_{i}'
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('original instruction')
            (folder / 'support.txt').write_text('fixed support and license fixture')
        shutil.copytree(TASK / 'verifier', task / 'verifier',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.xlsx'))
        return task

    def test_prepare_exports_only_twenty_images_and_verifier_side_answers(self):
        task = self.make_task(); output = self.base / 'exported'
        prepare('group_02', output, root=self.root)
        image_dir = output / 'environment/workspace/dataset/img'
        self.assertEqual(sorted(p.name for p in image_dir.iterdir()), self.spec('group_02')['filenames'])
        self.assertEqual((task/'task.md').read_bytes(), (output/'task.md').read_bytes())
        self.assertEqual((task/'environment/Dockerfile').read_bytes(), (output/'environment/Dockerfile').read_bytes())
        self.assertFalse(list((output/'environment/workspace').rglob('*.xlsx')))
        self.assertEqual(len(read_oracle(output/'verifier/stat_oracle.xlsx', self.spec('group_02'))), 20)
        self.assertEqual(json.loads((output/'verifier/receipt_spec.json').read_text()), self.spec('group_02'))
        self.assertFalse(json.loads((output/'preparation_receipt.json').read_text())['agent_started'])

    def test_prepare_rejects_nested_outputs_and_modified_support_before_writing(self):
        task = self.make_task()
        candidate = self.base / 'candidate'
        shutil.copytree(task/'environment/skills', candidate)
        for output in (task/'new', candidate/'new'):
            with self.assertRaises(ValueError):
                prepare('group_01', output, candidate, self.root)
            self.assertFalse(output.exists())
        (candidate/'skill_0/support.txt').write_text('not permitted')
        with self.assertRaises(ValueError):
            prepare('group_01', self.base/'bad-export', candidate, self.root)
        self.assertFalse((self.base/'bad-export').exists())

    def test_native_twenty_runs_forty_checks_and_rejects_incomplete_evidence(self):
        self.make_task(); output = self.base/'native'
        prepare('group_01', output, root=self.root)
        rows = copy.deepcopy(self.rows['group_01']); rows[1][2] = '11.00'
        actual = self.actual('group_01', rows)
        accuracy, ctrf, reward = [self.base/n for n in ('accuracy.json','ctrf.json','reward.txt')]
        env = dict(os.environ, JPG_OCR_ACTUAL_PATH=str(actual),
                   JPG_OCR_ORACLE_PATH=str(output/'verifier/stat_oracle.xlsx'),
                   JPG_OCR_REPORT_PATH=str(accuracy), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        result = subprocess.run([sys.executable,'-m','pytest','-p','ctrf.main','--ctrf',str(ctrf),
            str(output/'verifier/test_outputs.py'),'-q','--tb=no','--override-ini','addopts='],
            cwd=self.base,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
        self.assertTrue(ctrf.is_file(), result.stdout+result.stderr)
        write = subprocess.run([sys.executable,str(output/'verifier/write_reward.py'),
            '--ctrf',str(ctrf),'--accuracy',str(accuracy),'--reward',str(reward)],
            capture_output=True,text=True)
        self.assertEqual(write.returncode,0,write.stderr)
        self.assertEqual(float(reward.read_text()),39/40)
        evidence=json.loads(ctrf.read_text()); report=json.loads(accuracy.read_text())
        self.assertEqual(evidence['results']['summary']['tests'],40)
        evidence['results']['tests'].pop()
        with self.assertRaises(ValueError):
            validated_reward(evidence,report,self.spec())


if __name__ == '__main__':
    unittest.main()
