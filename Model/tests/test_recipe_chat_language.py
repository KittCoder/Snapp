"""Natural-language cases run through the real service with fixture transport."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_recipe_chat import Wire
import recipe_chat as chat
import recipe_search_typesense as search
from recipe_chat_language_cases import language_cases

CASES = language_cases()


class NaturalLanguageTests(unittest.TestCase):
    def test_benchmark_has_at_least_100_cases(self):
        self.assertGreaterEqual(len(CASES), 100)
        self.assertGreaterEqual(sum(len(c['turns']) > 1 for c in CASES), 40)


def case_test(case):
    def test(self):
        wire = Wire()
        state = None
        with patch.object(search, 'typesense_request', side_effect=wire):
            service = chat.RecipeChatService()
            for spec in case['turns']:
                before = copy.deepcopy(state)
                result = service.handle_message(spec['message'], state)
                self.assertEqual(state, before, 'mutated caller state')
                state = result['state']
                for key, expected in spec['expect'].items():
                    with self.subTest(message=spec['message'], field=key):
                        if key == 'intent':
                            self.assertEqual(result[key], expected)
                        elif key == 'response_contains':
                            self.assertIn(expected, result['message'])
                        elif key == 'alternatives':
                            self.assertFalse(set(before['last_result_ids']) & {r['id'] for r in result['results']})
                        else:
                            self.assertEqual(state[key], expected)
                self.assertTrue({r['id'] for r in result['results']} <= wire.returned)
                for recipe in result['results']:
                    original = next(d for d in wire.documents if d['id'] == recipe['id'])
                    self.assertEqual(recipe['title'], original['title'])
                query = result['search_metadata']['typesense_query']
                if query:
                    self.assertIn(query['alpha'], (0.7, None))
    return test


for index, case in enumerate(CASES):
    setattr(NaturalLanguageTests, f'test_{index:03d}_{case["name"]}', case_test(case))

if __name__ == '__main__':
    unittest.main()

class ConversationSafetyTests(unittest.TestCase):
    def test_alternatives_need_existing_context(self):
        service = chat.RecipeChatService()
        with patch.object(service, 'search') as search_call:
            result = service.handle_message('not that one')
        self.assertEqual(result['intent'], 'GENERAL_FOLLOWUP')
        self.assertIn('Search for an ingredient or meal first', result['message'])
        search_call.assert_not_called()

    def test_resolved_turns_do_not_call_model_interpretation(self):
        from unittest.mock import Mock
        model = Mock()
        model.compose.return_value = {}
        service = chat.RecipeChatService(model=model)
        with patch.object(search, 'typesense_request', side_effect=Wire()):
            initial = service.handle_message('warm dinner with chicken')
            service.handle_message("I don't mind chicken", initial['state'])
            service.handle_message('thanks', initial['state'])
            service.handle_message('give me more', initial['state'])
        model.interpret.assert_not_called()

    def test_alternatives_keep_all_filters_and_skip_shown_ids(self):
        service = chat.RecipeChatService()
        with patch.object(search, 'typesense_request', side_effect=Wire()):
            initial = service.handle_message('dinner without cheese under 40 minutes')
            result = service.handle_message('show me another', initial['state'])
        self.assertEqual(result['state']['max_time'], 40)
        self.assertEqual(result['state']['exclude_ingredients'], ['cheese'])
        self.assertEqual(result['state']['categories'], ['lunch_dinner'])
        self.assertFalse(set(initial['state']['last_result_ids']) & {r['id'] for r in result['results']})
        filters = result['search_metadata']['typesense_query']['filter_by']
        self.assertIn('total_time_minutes:<=40', filters)
        self.assertIn('ingredient_filter_tokens:!=`cheese`', filters)

    def test_unreviewed_traces_are_not_scored_as_good(self):
        import importlib.util
        import tempfile
        path = Path(__file__).resolve().parents[2] / 'scripts/review_recipe_chat.py'
        spec = importlib.util.spec_from_file_location('review_recipe_chat', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        trace = {'user_message': 'new phrasing'}
        report = {'conversations': [{'name': 'new', 'turns': [trace]}]}
        with tempfile.TemporaryDirectory() as directory:
            module.apply_manual_ratings(report, Path(directory) / 'absent.json')
        self.assertEqual(report['manual_quality_review']['counts']['UNREVIEWED'], 1)
        self.assertFalse(report['manual_quality_review']['target_met'])
