import copy
import json
import unittest
from fixture import fixture
from isp_impact.selection import plan, validate_shadow


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.change, self.rules = fixture()

    def run_plan(self):
        return plan(self.rows, self.change, self.rules, 0)

    def selected(self):
        return {r['id'] for r in self.run_plan()['decisions'] if r['selected']}

    def single(self, **kw):
        row = dict(self.rows[1], id='test', sensor='SENSOR_A', gain='7', cct='5000', **kw)
        self.rows = [row]

    def test_interpolation_halo_and_closed_boundaries(self):
        self.single()
        for gain in ('6', '7', '8', '16', '19', '20'):
            self.rows[0]['gain'] = gain
            self.assertEqual(self.selected(), {'test'})
        for gain in ('5.99', '20.01'):
            self.rows[0]['gain'] = gain
            self.assertFalse(self.selected())

    def test_missing_nan_and_bad_trigger_retained(self):
        self.single()
        for gain in ('', 'NaN', 'inf', 'bad'):
            self.rows[0]['gain'] = gain
            self.assertEqual(self.selected(), {'test'})

    def test_multi_axis_known_exclusion(self):
        self.single()
        self.rows[0].update(gain='', cct='9000')
        self.assertFalse(self.selected())

    def test_missing_scope_retained(self):
        self.single()
        self.rows[0].update(sensor='', gain='1')
        self.assertEqual(self.selected(), {'test'})

    def test_known_scope_mismatch(self):
        self.single()
        self.rows[0]['sensor'] = 'SENSOR_B'
        self.assertFalse(self.selected())

    def test_sequence_closure(self):
        ids = self.selected()
        self.assertTrue(all(f'seq_0_{i:02}' in ids for i in range(10)))
        self.assertFalse(any(i.startswith('seq_3_') for i in ids))

    def test_global_fallbacks(self):
        for key in ('diff_complete', 'scope_resolved', 'execution_contract_unchanged'):
            change = copy.deepcopy(self.change)
            change[key] = False
            self.assertEqual(plan(self.rows, change, self.rules, 0)['summary']['selected'], len(self.rows))
        self.change['changes'][0]['kind'] = 'trigger_layout'
        self.assertEqual(len(self.selected()), len(self.rows))

    def test_unknown_module(self):
        self.change['changes'][0]['module'] = 'UNKNOWN'
        self.assertEqual(len(self.selected()), len(self.rows))

    def test_unknown_region_and_support_and_locality(self):
        self.single()
        self.rows[0]['gain'] = '1'
        original = copy.deepcopy(self.rules)
        for key in ('locality_verified', 'support_verified'):
            self.rules = copy.deepcopy(original)
            self.rules['modules']['ANR'][key] = False
            self.assertEqual(self.selected(), {'test'})
        self.rules = original
        self.change['changes'][0]['regions'] = ['UNKNOWN']
        self.assertEqual(self.selected(), {'test'})

    def test_trace_overrides_support_only_with_matching_context(self):
        self.single()
        self.rows[0].update(trace_context='synthetic-baseline-v1', trace_json=json.dumps({'ANR': {'complete': True, 'active_regions': []}}))
        self.assertFalse(self.selected())
        self.rows[0]['trace_context'] = 'stale'
        self.assertEqual(self.selected(), {'test'})

    def test_incomplete_trace_falls_back_to_support(self):
        self.single()
        self.rows[0].update(trace_context='synthetic-baseline-v1', trace_json=json.dumps({'ANR': {'complete': False, 'active_regions': []}}))
        self.assertEqual(self.selected(), {'test'})

    def test_multiple_changes_union(self):
        self.single()
        self.rows[0]['sensor'] = 'SENSOR_B'
        another = copy.deepcopy(self.change['changes'][0])
        another['scope']['sensor'] = ['SENSOR_B']
        self.change['changes'].append(another)
        self.assertEqual(self.selected(), {'test'})

    def test_canaries_deterministic_and_add_only(self):
        a = plan(self.rows, self.change, self.rules, .05)
        b = plan(list(reversed(self.rows)), self.change, self.rules, .05)
        get = lambda result: {r['id'] for r in result['decisions'] if r['selected']}
        self.assertEqual(get(a), get(b))
        self.assertTrue(self.selected() <= get(a))
        self.assertGreater(len(get(a)), len(self.selected()))

    def test_shadow_detects_miss_and_requires_full_observations(self):
        result = self.run_plan()
        excluded = next(r['id'] for r in result['decisions'] if not r['selected'])
        obs = [{'id': r['id'], 'changed': '1' if r['id'] == excluded else '0'} for r in self.rows]
        report = validate_shadow(result, obs)
        self.assertFalse(report['passed'])
        self.assertEqual(report['missed_changed'], [excluded])
        with self.assertRaises(ValueError):
            validate_shadow(result, obs[:-1])

    def test_zero_change_not_recall_evidence(self):
        obs = [{'id': r['id'], 'changed': '0'} for r in self.rows]
        self.assertIsNone(validate_shadow(self.run_plan(), obs)['observed_recall'])


if __name__ == '__main__':
    unittest.main()
