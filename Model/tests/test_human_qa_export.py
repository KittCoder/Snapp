"""Review tooling must not turn proxy or missing labels into human evidence."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('human_qa', Path(__file__).resolve().parents[2] / 'scripts/human_qa_ingredient_matcher.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def case(key, accepted=True, confidence='high', family='cheese'):
    return {'case_id': key, 'selected_match': {'product_name': 'fixture'} if accepted else None,
            'confidence': confidence, 'ontology': {'family': family, 'subfamily': 'cheddar'},
            'compatible_alternatives': [], 'rejected_candidates': []}


def review(key, label):
    return {'case_id': key, 'review_label': label, 'wrong_family': 'no',
            'prepared_food_false_positive': 'no', 'structurally_correct': 'yes'}


class HumanQAExportTests(unittest.TestCase):
    def test_unreviewed_metrics_are_pending(self):
        result = qa.metrics({'a': case('a')}, [review('a', '')])
        self.assertIsNone(result['Exact/High_manual_precision'])
        self.assertIsNone(result['wrong_family_count'])
        self.assertEqual(result['freeze_recommendation'], 'DO_NOT_FREEZE_MATCHER')

    def test_ambiguous_is_in_denominator_and_not_correct(self):
        result = qa.metrics({key: case(key) for key in ('a', 'b', 'c')},
                            [review('a', 'CORRECT'), review('b', 'ACCEPTABLE_SUBSTITUTE'), review('c', 'AMBIGUOUS')])
        self.assertAlmostEqual(result['Exact/High_manual_precision'], 2 / 3)

    def test_rejection_miss_rate_is_not_population_false_negative_rate(self):
        result = qa.metrics({key: case(key, False) for key in ('a', 'b')},
                            [review('a', 'CORRECT'), review('b', 'SHOULD_HAVE_MATCHED')])
        self.assertEqual(result['rejected_SHOULD_HAVE_MATCHED_rate'], .5)
        self.assertIsNone(result['false_negative_rate'])

    def test_sampling_is_repeatable_disjoint_and_reports_shortages(self):
        rows = [case(str(i)) for i in range(500)] + [case('reject'+str(i), False, family='other') for i in range(300)]
        first, counts = qa.sample_population(rows, 123)
        self.assertEqual((first, counts), qa.sample_population(rows, 123))
        self.assertEqual(len(first), len({r['case_id'] for r in first}))
        self.assertEqual(counts['Medium']['sampled'], 0)
        self.assertEqual(counts['Medium']['requested'], 250)
        self.assertTrue(all('review_label' not in r for r in first))

    def test_wrong_accepted_count_and_family_flag_remain_errors(self):
        r = review('a', 'WRONG'); r['wrong_family'] = 'yes'
        result = qa.metrics({'a': case('a')}, [r])
        self.assertEqual(result['false_positive_rate'], 1)
        self.assertEqual(result['wrong_family_count'], 1)
        self.assertEqual(len(result['material_errors']), 1)
