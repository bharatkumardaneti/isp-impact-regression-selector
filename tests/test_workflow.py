import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from isp_impact.bundles import tuning_diff
from isp_impact.cli import make_plan, read
from isp_impact.demo import generate
from isp_impact.runner import run, validate, seal


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='isp impact ')
        self.root = generate(Path(self.tmp.name) / 'data')
        self.before, self.after, self.rules, self.adapter = [read(self.root / x) for x in ('baseline.json','candidate.json','rules.json','adapter.json')]
        self.plan = make_plan(self.root / 'catalog.csv', self.before, self.after, self.rules, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self, adapter=None, mode='full', **kw):
        return run(self.plan, self.before, self.after, adapter or self.adapter, self.root / 'run', mode, **kw)

    def test_diff_region_and_structural_change(self):
        diff = tuning_diff(self.before, self.after)
        self.assertEqual(diff['changes'][0]['regions'], ['HIGH'])
        self.after['execution_contract']['pipeline'] = 'new'
        self.assertFalse(tuning_diff(self.before,self.after)['execution_contract_unchanged'])

    def test_unknown_bundle_field_rejected(self):
        self.after['untracked'] = 1
        with self.assertRaises(ValueError):
            tuning_diff(self.before,self.after)

    def test_no_change_rejected(self):
        with self.assertRaises(ValueError):
            make_plan(self.root/'catalog.csv', self.before,self.before,self.rules)

    def test_real_pixels_full_validation(self):
        report = self.execute()
        self.assertTrue(report['success'], report['errors'])
        validation = validate(self.plan,report)
        self.assertTrue(validation['passed'])
        self.assertEqual(validation['changed_frames'],20)
        self.assertLess(self.plan['summary']['selected'],48)

    def test_incorrect_support_detected_by_full_run(self):
        self.rules['modules']['DENOISE']['regions']['HIGH']['support'] = [{'gain':[10,14]}]
        self.plan = make_plan(self.root/'catalog.csv',self.before,self.after,self.rules,0)
        validation = validate(self.plan,self.execute())
        self.assertFalse(validation['passed'])
        self.assertGreater(len(validation['missed_changed']),0)

    def test_selected_run_rejected_for_shadow_validation(self):
        report = self.execute(mode='selected')
        with self.assertRaises(ValueError):
            validate(self.plan,report)

    def test_changed_input_rejected(self):
        Path(self.plan['decisions'][0]['path']).write_text('changed')
        with self.assertRaises(ValueError):
            self.execute()

    def test_tampered_plan_rejected(self):
        self.plan['decisions'][0]['selected'] = False
        with self.assertRaises(ValueError):
            self.execute()

    def test_wrong_tuning_rejected(self):
        self.after['modules']['DENOISE']['regions']['HIGH']['parameters']['strength'] = .9
        with self.assertRaises(ValueError):
            self.execute()

    def test_adapter_failure_is_not_unchanged(self):
        report = self.execute({'argv':[sys.executable,'-c','import sys; sys.exit(7)','{job}']})
        self.assertFalse(report['success'])
        self.assertEqual(report['observations'],[])
        with self.assertRaises(ValueError):
            validate(self.plan,report)

    def test_missing_artifact_rejected(self):
        script = "import json,sys; from pathlib import Path; j=json.loads(Path(sys.argv[1]).read_text()); Path(j['result_path']).write_text(json.dumps({'artifacts':{}}))"
        report = self.execute({'argv':[sys.executable,'-c',script,'{job}']})
        self.assertFalse(report['success'])

    def test_timeout_reported(self):
        self.plan['decisions'] = self.plan['decisions'][:1]
        seal(self.plan)
        report = self.execute({'argv':[sys.executable,'-c','import time; time.sleep(2)','{job}']},timeout=.01)
        self.assertFalse(report['success'])

    def test_existing_output_not_overwritten(self):
        (self.root/'run').mkdir()
        with self.assertRaises(FileExistsError):
            self.execute()
