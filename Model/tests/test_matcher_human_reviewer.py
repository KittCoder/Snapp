"""Review tooling persistence and metrics, without any matcher execution."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from matcher_review_store import ReviewStore, FIELDS
from review_matcher_human import create_app
from analyze_matcher_human_review import analyze, accepted_summary, rejected_summary


class HumanReviewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        columns = ['case_id', 'sample_group', 'ingredient_query', 'current_matcher_decision', 'confidence'] + FIELDS
        self.rows = []
        for key, decision, group in [('a', 'accepted', 'Exact/High'), ('b', 'rejected', 'Rejected')]:
            self.rows.append(dict(case_id=key, sample_group=group, ingredient_query=key, current_matcher_decision=decision, confidence='high', **{f:'' for f in FIELDS}))
        with (self.directory/'review.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader(); writer.writerows(self.rows)
        self.original = (self.directory/'review.csv').read_bytes()

    def test_manual_save_resume_and_original_preserved(self):
        store = ReviewStore(self.directory)
        self.assertTrue(all(not r['review_label'] for r in store.snapshot()['cases']))
        store.save('a', {'review_label':'CORRECT', 'review_notes':'manual'}, 0)
        resumed = ReviewStore(self.directory)
        self.assertEqual(resumed.snapshot()['cases'][0]['review_label'], 'CORRECT')
        self.assertEqual(self.original, (self.directory/'review.csv').read_bytes())
        self.assertEqual(json.loads((self.directory/'review_labels.json').read_text())['revision'], 1)

    def test_interrupted_csv_write_recovers_from_sidecar(self):
        store = ReviewStore(self.directory)
        with mock.patch.object(store, 'write_csv', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): store.save('a', {'review_label':'WRONG'}, 0)
        recovered = ReviewStore(self.directory)
        self.assertEqual(recovered.snapshot()['cases'][0]['review_label'], 'WRONG')
        with (self.directory/'review_labeled.csv').open() as handle:
            self.assertEqual(next(csv.DictReader(handle))['review_label'], 'WRONG')

    def test_two_process_stores_cannot_overwrite_stale_revision(self):
        first = ReviewStore(self.directory); second = ReviewStore(self.directory)
        first.save('a', {'review_label':'CORRECT'}, 0)
        with self.assertRaises(RuntimeError): second.save('b', {'review_label':'AMBIGUOUS'}, 0)
        self.assertEqual(second.snapshot()['cases'][0]['review_label'], 'CORRECT')

    def test_sidecar_write_failure_does_not_change_memory_or_original(self):
        store = ReviewStore(self.directory)
        with mock.patch('matcher_review_store.atomic_write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): store.save('a', {'review_label':'WRONG'}, 0)
        self.assertEqual(store.snapshot()['revision'], 0)
        self.assertEqual(store.snapshot()['cases'][0]['review_label'], '')
        self.assertEqual(self.original, (self.directory/'review.csv').read_bytes())

    def test_api_allows_all_context_labels_and_rejects_unknown_or_cross_origin(self):
        client = create_app(self.directory).test_client()
        for revision, label in enumerate(['CORRECT','ACCEPTABLE_SUBSTITUTE','WRONG','SHOULD_HAVE_MATCHED','AMBIGUOUS']):
            response = client.post('/api/label', json={'case_id':'b','values':{'review_label':label},'revision':revision})
            self.assertEqual(response.status_code, 200)
        bad = client.post('/api/label', json={'case_id':'b','values':{'review_label':'proxy'},'revision':5})
        self.assertEqual(bad.status_code, 400)
        cross = client.post('/api/label', headers={'Origin':'https://example.org'}, json={})
        self.assertEqual(cross.status_code, 403)
        for path in ['/', '/review.js']:
            with client.get(path) as response:
                self.assertEqual(response.status_code, 200)

    def test_final_analysis_refuses_incomplete_review(self):
        with self.assertRaisesRegex(ValueError, 'Refusing final analysis'):
            analyze(self.rows, {}, partial=False)

    def test_ambiguity_stays_in_precision_denominator(self):
        rows = [{'review_label':x} for x in ['CORRECT','ACCEPTABLE_SUBSTITUTE','WRONG','AMBIGUOUS']]
        result = accepted_summary(rows)
        self.assertEqual(result['precision'], .5)
        self.assertEqual(result['false_positive_rate'], .25)
        self.assertEqual(rejected_summary([{'review_label':'CORRECT'}, {'review_label':'SHOULD_HAVE_MATCHED'}, {'review_label':'AMBIGUOUS'}])['false_negative_rate'], 1/3)

    def test_changed_original_is_refused(self):
        store = ReviewStore(self.directory)
        store.save('a', {'review_label':'CORRECT'}, 0)
        (self.directory/'review.csv').write_text('changed')
        with self.assertRaises(ValueError): store.snapshot()
