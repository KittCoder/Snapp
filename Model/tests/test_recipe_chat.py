"""Multi-turn orchestration tests through the real frozen search with a fake wire transport."""
import copy
import io
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recipe_chat as chat
import recipe_search_typesense as search


def recipe(i, title, names, minutes, categories, **extra):
    return dict(id=i, title=title, ingredient_names=names, total_time_minutes=minutes,
                categories=categories, **extra)


DOCUMENTS = [
    recipe('c1', 'Chicken Rice', ['chicken', 'rice', 'salt'], 30, ['lunch_dinner']),
    recipe('c2', 'Chicken Cheese', ['chicken', 'cheese'], 20, ['lunch_dinner']),
    recipe('b1', 'Beef Rice', ['beef', 'rice', 'salt'], 40, ['lunch_dinner']),
    recipe('b2', 'Beef Broth', ['beef', 'broth'], 20, ['lunch_dinner']),
    recipe('e1', 'Milk Eggs', ['eggs', 'milk'], 10, ['breakfast']),
    recipe('e2', 'Water Eggs', ['eggs', 'water', 'salt'], 15, ['breakfast']),
    recipe('p1', 'Tomato Pasta', ['pasta', 'tomato'], 20, ['lunch_dinner']),
    recipe('p2', 'Cream Pasta', ['pasta', 'cream'], 25, ['lunch_dinner', 'vegetarian']),
    recipe('r1', 'Spicy Rice', ['rice', 'beans', 'chili'], 15, ['lunch_dinner', 'vegetarian']),
]


class Wire:
    """Small fixture-only filter evaluator, not a replacement retrieval engine."""
    def __init__(self):
        self.documents = copy.deepcopy(DOCUMENTS)
        self.calls = []
        self.returned = set()
        self.embedding_error = False

    def __call__(self, config, method, path, body=None, query=None):
        self.calls.append((method, path, copy.deepcopy(body), query))
        if method == 'GET':
            rid = unquote(path.rsplit('/', 1)[-1])
            found = next((d for d in self.documents if d['id'] == rid), None)
            if found is None:
                raise HTTPError('http://fixture', 404, 'missing', {}, io.BytesIO())
            return copy.deepcopy(found)
        params = body['searches'][0]
        if self.embedding_error and 'vector_query' in params:
            return {'results': [{'error': 'embedding unavailable'}]}
        def matches(doc):
            for part in params.get('filter_by', '').split(' && '):
                if not part:
                    continue
                field, operation = part.split(':', 1)
                if field == 'total_time_minutes':
                    val = doc.get(field)
                    if val is None:
                        return False
                    if operation.startswith('<=') and val > int(operation[2:]): return False
                    if operation.startswith('>=') and val < int(operation[2:]): return False
                elif field == 'has_named_dairy':
                    if set(doc['ingredient_names']) & set(search.dairy_ingredient_names()): return False
                else:
                    terms = re.findall(r'`([^`]+)`', operation)
                    values = search.ingredient_filter_tokens(doc['ingredient_names']) if field == 'ingredient_filter_tokens' else doc.get(field, [])
                    match = bool(set(terms) & set(values))
                    if operation.startswith('!=') and match or not operation.startswith('!=') and not match:
                        return False
            return True
        docs = [copy.deepcopy(d) for d in self.documents if matches(d)]
        self.returned.update(d['id'] for d in docs)
        return {'results': [{'hits': [{'document': d} for d in docs], 'found': len(docs), 'search_time_ms': 2}]}


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.wire = Wire()
        self.patch = patch.object(search, 'typesense_request', side_effect=self.wire)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.service = chat.RecipeChatService()
        self.state = None
        self.turns = []

    def turn(self, message):
        old = copy.deepcopy(self.state)
        result = self.service.handle_message(message, self.state)
        self.assertEqual(self.state, old, 'caller state mutated')
        self.assertTrue({r['id'] for r in result['results']} <= self.wire.returned)
        if result['selected_recipe']:
            self.assertIn(result['selected_recipe']['id'], result['state']['last_result_ids'])
            self.assertIn(result['selected_recipe']['id'], self.wire.returned)
        json.dumps(result, allow_nan=False)
        self.state = json.loads(json.dumps(result['state']))
        self.turns.append(result)
        return result

    def test_a_chicken_time_exclusion_replace(self):
        self.turn('I want chicken for dinner')
        self.turn('under 30 minutes')
        self.turn('no cheese')
        r = self.turn('actually beef instead')
        self.assertEqual(r['intent'], 'REFINE_SEARCH')
        self.assertEqual(self.state['include_ingredients'], ['beef'])
        self.assertEqual(self.state['exclude_ingredients'], ['cheese'])
        self.assertEqual(self.state['max_time'], 30)
        self.assertEqual(self.state['categories'], ['lunch_dinner'])
        self.assertEqual([x['id'] for x in r['results']], ['b2'])

    def test_b_winter_beef_quicker(self):
        self.turn('I want a warm winter meal')
        self.turn('with beef')
        r = self.turn('something quicker')
        self.assertEqual(self.state['semantic_query'], 'warm winter meal')
        self.assertEqual(self.state['max_time'], 15)
        self.assertIn('15 minutes', r['message'])

    def test_c_breakfast_second_milk(self):
        self.turn('breakfast with eggs')
        self.turn('show me the second one')
        r = self.turn('does it use milk?')
        self.assertEqual(self.state['selected_recipe_id'], 'e2')
        self.assertIn('does not name milk', r['message'])
        self.assertEqual(self.state['include_ingredients'], ['eggs'])

    def test_d_pasta_exclude_tomato_creamy(self):
        self.turn('I want pasta')
        self.turn('no tomato')
        r = self.turn('something creamy')
        self.assertEqual(self.state['semantic_query'], 'creamy')
        self.assertEqual(self.state['exclude_ingredients'], ['tomato'])
        self.assertEqual([x['id'] for x in r['results']], ['p2'])

    def test_e_spicy_rice_vegetarian(self):
        self.turn('something spicy with rice')
        r = self.turn('make it vegetarian')
        self.assertEqual(self.state['dietary'], ['vegetarian'])
        self.assertEqual(self.state['semantic_query'], 'spicy')
        self.assertIn('not dietary guarantees', r['message'])
        self.assertTrue(all('vegetarian' in x['categories'] for x in r['results']))

    def test_f_beef_clear_time(self):
        self.turn('beef dinner')
        r = self.turn('forget the time limit')
        self.assertEqual(r['intent'], 'CLEAR_CONSTRAINT')
        self.assertEqual(self.state['include_ingredients'], ['beef'])
        self.assertIsNone(self.state['max_time'])

    def test_g_number_three_no_results_then_search(self):
        r = self.turn('show me number 3')
        self.assertIsNone(r['selected_recipe'])
        self.assertIn('not in the last result list', r['message'])
        self.turn('dinner')
        r = self.turn('show me number 3')
        self.assertEqual(r['selected_recipe']['id'], self.state['last_result_ids'][2])

    def test_clear_both_time_bounds(self):
        self.turn('beef over 10 minutes')
        self.turn('under 30 minutes')
        self.turn('forget the time limit')
        self.assertIsNone(self.state['min_time'])
        self.assertIsNone(self.state['max_time'])
        self.assertEqual(self.state['include_ingredients'], ['beef'])

    def test_first_and_last_resolve_order(self):
        r = self.turn('dinner')
        ids = r['state']['last_result_ids'][:]
        self.assertEqual(self.turn('the first one')['selected_recipe']['id'], ids[0])
        self.assertEqual(self.turn('the last one')['selected_recipe']['id'], ids[-1])

    def test_out_of_range_preserves_selection(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        r = self.turn('number 99')
        self.assertIsNone(r['selected_recipe'])
        self.assertEqual(self.state['selected_recipe_id'], 'e1')

    def test_zero_ordinal_does_not_select_last(self):
        self.turn('dinner')
        self.assertIsNone(self.turn('number 0')['selected_recipe'])
        self.assertIsNone(self.state['selected_recipe_id'])

    def test_selected_positive_milk_is_stored_fact(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        r = self.turn('Does that have milk?')
        self.assertIn('stored ingredient list names: milk', r['message'])
        self.assertIn('not establish allergen safety', r['message'])
        self.assertEqual(r['intent'], 'QUESTION_ABOUT_SELECTED_RECIPE')

    def test_time_and_ingredients_no_search(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        count = sum(c[0] == 'POST' for c in self.wire.calls)
        self.assertIn('10 minutes total', self.turn('How long does it take?')['message'])
        self.assertIn('eggs; milk', self.turn('What ingredients are in it?')['message'])
        self.assertEqual(sum(c[0] == 'POST' for c in self.wire.calls), count)

    def test_instructions_missing_then_stored(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        self.assertIn('does not contain cooking instructions', self.turn('How do I make it?')['message'])
        self.wire.documents[4]['instructions'] = ['Beat eggs.', 'Cook in a pan.']
        self.assertIn('1. Beat eggs.', self.turn('How do I make it?')['message'])

    def test_missing_servings_not_invented(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        self.assertIn('not recorded', self.turn('How many servings?')['message'])

    def test_question_requires_explicit_selection(self):
        self.turn('breakfast with eggs')
        r = self.turn('Does that have milk?')
        self.assertIn('Select a recipe first', r['message'])
        self.assertIsNone(self.state['selected_recipe_id'])

    def test_question_can_reference_ordinal(self):
        self.turn('breakfast with eggs')
        r = self.turn('Does the first one have milk?')
        self.assertEqual(r['selected_recipe']['id'], 'e1')
        self.assertIn('names: milk', r['message'])

    def test_refine_clears_selection_and_replaces_result_ids(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        r = self.turn('no milk')
        self.assertIsNone(self.state['selected_recipe_id'])
        self.assertEqual(self.state['last_result_ids'], ['e2'])
        self.assertEqual([x['id'] for x in r['results']], ['e2'])

    def test_compare_fastest(self):
        self.turn('breakfast with eggs')
        r = self.turn('Which is fastest?')
        self.assertEqual(r['intent'], 'COMPARE_RESULTS')
        self.assertIn('Milk Eggs — 10 minutes', r['message'])

    def test_compare_ingredient_counts(self):
        self.turn('breakfast with eggs')
        self.assertIn('Milk Eggs — 2 ingredients', self.turn('Which one has fewer ingredients?')['message'])

    def test_compare_first_two(self):
        self.turn('dinner')
        text = self.turn('Compare the first two.')['message']
        self.assertIn('Chicken Rice', text)
        self.assertIn('Chicken Cheese', text)
        self.assertNotIn('Beef Rice', text)

    def test_compare_explicit_and_bad_ordinals(self):
        self.turn('dinner')
        text = self.turn('Compare the first and third')['message']
        self.assertIn('Beef Rice', text)
        self.assertNotIn('Chicken Cheese', text)
        self.assertIn('not in the last result list', self.turn('Compare number 8 and number 1')['message'])

    def test_compare_missing_data_and_unsupported_claim(self):
        self.turn('breakfast with eggs')
        self.wire.documents[4].pop('total_time_minutes')
        self.assertIn('lack the stored data', self.turn('Which is fastest?')['message'])
        self.assertIn('cannot reliably rank', self.turn('Which is healthiest?')['message'])

    def test_replace_protein_preserves_rice_and_exclusions(self):
        self.turn('chicken with rice')
        self.turn('no cheese')
        self.turn('actually beef instead')
        self.assertEqual(set(self.state['include_ingredients']), {'rice', 'beef'})
        self.assertEqual(self.state['exclude_ingredients'], ['cheese'])

    def test_explicit_replace_nonprotein(self):
        self.turn('chicken with rice')
        self.turn('replace rice with pasta')
        self.assertEqual(set(self.state['include_ingredients']), {'chicken', 'pasta'})

    def test_instead_of_replaces_named_ingredient(self):
        self.turn('chicken with rice')
        self.turn('beef instead of chicken')
        self.assertEqual(set(self.state['include_ingredients']), {'beef', 'rice'})

    def test_remove_inclusion_and_exclusion_explicitly(self):
        self.turn('chicken dinner without cheese')
        self.turn('remove chicken')
        self.assertEqual(self.state['include_ingredients'], [])
        self.assertEqual(self.state['exclude_ingredients'], ['cheese'])
        self.turn('remove no cheese')
        self.assertEqual(self.state['exclude_ingredients'], [])

    def test_category_replace_then_clear(self):
        self.turn('chicken dinner')
        self.turn('breakfast instead')
        self.assertEqual(self.state['categories'], ['breakfast'])
        self.turn('remove category')
        self.assertEqual(self.state['categories'], [])
        self.assertNotIn('breakfast', self.state['semantic_query'])

    def test_remove_dietary_preserves_ingredient(self):
        self.turn('vegetarian with rice')
        self.turn('remove dietary restrictions')
        self.assertEqual(self.state['dietary'], [])
        self.assertEqual(self.state['include_ingredients'], ['rice'])

    def test_conflict_does_not_drop_exclusions(self):
        self.turn('pasta without tomato')
        old = copy.deepcopy(self.state)
        r = self.turn('with tomato')
        self.assertIn('conflicts with an active ingredient exclusion', r['message'])
        self.assertEqual(self.state, old)

    def test_time_conflict_does_not_commit_invalid_state(self):
        self.turn('chicken over 20 minutes')
        old = copy.deepcopy(self.state)
        r = self.turn('under 10 minutes')
        self.assertIn('conflicts', r['message'])
        self.assertEqual(self.state, old)

    def test_quicker_without_time_data_asks_limit(self):
        for doc in self.wire.documents: doc.pop('total_time_minutes')
        self.turn('chicken')
        self.assertIn('maximum total time', self.turn('something quicker')['message'])
        self.assertIsNone(self.state['max_time'])

    def test_quicker_uses_existing_cap(self):
        self.turn('chicken under 40 minutes')
        self.turn('something quicker')
        self.assertEqual(self.state['max_time'], 30)
        self.turn('something quicker')
        self.assertEqual(self.state['max_time'], 22)

    def test_new_search_resets_constraints(self):
        self.turn('chicken without cheese under 30 minutes')
        self.turn('new search for breakfast with eggs')
        self.assertEqual(self.state['include_ingredients'], ['eggs'])
        self.assertEqual(self.state['exclude_ingredients'], [])
        self.assertIsNone(self.state['max_time'])

    def test_reset_and_general_followup(self):
        self.turn('chicken')
        old = copy.deepcopy(self.state)
        self.assertEqual(self.turn('thanks')['intent'], 'GENERAL_FOLLOWUP')
        self.assertEqual(self.state, old)
        self.turn('start over')
        self.assertEqual(self.state, chat.RecipeChatState().to_dict())

    def test_no_results_clears_old_ordinals(self):
        self.turn('chicken')
        self.turn('with beef')
        self.assertEqual(self.state['last_result_ids'], [])
        self.assertIsNone(self.turn('the first one')['selected_recipe'])

    def test_deleted_selected_document(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        self.wire.documents = [d for d in self.wire.documents if d['id'] != 'e1']
        self.assertIn('no longer available', self.turn('How long does it take?')['message'])
        self.assertIsNone(self.state['selected_recipe_id'])

    def test_stored_fact_changes_are_refetched(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        self.wire.documents[4]['total_time_minutes'] = 17
        self.assertIn('17 minutes', self.turn('How long does it take?')['message'])

    def test_alpha_and_keyword_fallback_preserve_exclusions(self):
        self.turn('warm winter dinner with beef')
        self.wire.embedding_error = True
        r = self.turn('no cheese')
        self.assertTrue(r['search_metadata']['fallback'])
        self.assertEqual(r['search_metadata']['mode'], 'keyword')
        params = [c[2]['searches'][0] for c in self.wire.calls if c[0] == 'POST']
        self.assertTrue(all('alpha:0.7' in p['vector_query'] for p in params if 'vector_query' in p))
        self.assertEqual(params[-1]['filter_by'], params[-2]['filter_by'])
        self.assertIn('ingredient_filter_tokens:!=`cheese`', params[-1]['filter_by'])

    def test_cost_health_and_household_not_guaranteed(self):
        self.turn('cheapest dinner')
        self.assertIn('cannot be guaranteed', self.turns[-1]['message'])
        self.assertIn('cannot be guaranteed', self.turn('best for four people')['message'])

    def test_model_cannot_invent_recipes_or_facts(self):
        class Malicious:
            def interpret(self, *args): return {'semantic_query': 'cheese', 'exclude_ingredients': []}
            def compose(self, context):
                context['recipes'][0]['title'] = 'Invented'
                return {'ordered_recipe_ids': ['fake'], 'message': 'Invented recipe, 999 servings'}
        self.service.model = Malicious()
        r = self.turn('warm dinner with beef')
        self.turn('no cheese')
        self.turn('thanks')
        self.assertNotIn('Invented', json.dumps(self.turns))
        self.assertNotIn('fake', self.state['last_result_ids'])
        self.assertEqual(self.state['exclude_ingredients'], ['cheese'])
        self.assertTrue(r['results'])

    def test_valid_model_order_controls_ordinals_and_context_is_small(self):
        captured = []
        class Ordering:
            def interpret(self, *args): return {}
            def compose(self, context):
                captured.append(context)
                return {'ordered_recipe_ids': [r['id'] for r in reversed(context['recipes'])]}
        self.service.model = Ordering()
        r = self.turn('dinner')
        self.assertLessEqual(len(captured[0]['recipes']), 5)
        self.assertNotIn('instructions', json.dumps(captured))
        self.assertNotIn('embedding', json.dumps(captured))
        self.assertEqual(self.turn('the second one')['selected_recipe']['id'], r['results'][1]['id'])

    def test_model_failure_is_deterministic_and_hides_secrets(self):
        class Broken:
            def interpret(self, *args): raise RuntimeError('secret-key')
            def compose(self, *args): raise RuntimeError('secret-key')
        self.service.model = Broken()
        self.turn('chicken')
        self.turn('thanks')
        self.assertNotIn('secret-key', json.dumps(self.turns))

    def test_model_soft_interpretation_cannot_clear_constraints(self):
        class Soft:
            def interpret(self, *args): return {'semantic_query': 'cozy'}
            def compose(self, *args): return {}
        self.turn('beef without cheese')
        self.service.model = Soft()
        self.turn('more')
        self.assertEqual(self.state['exclude_ingredients'], ['cheese'])
        # MORE is now deterministic: a configured model cannot add preferences.
        self.assertEqual(self.state['semantic_query'], '')

    def test_unknown_id_never_becomes_recipe(self):
        self.turn('chicken')
        self.state['last_result_ids'] = ['unknown']
        self.state['selected_recipe_id'] = None
        self.assertIsNone(self.turn('the first one')['selected_recipe'])

    def test_cook_time_is_not_claimed_as_total_time(self):
        self.turn('breakfast with eggs')
        self.turn('the first one')
        self.wire.documents[4].pop('total_time_minutes')
        self.wire.documents[4]['cook_time_minutes'] = 8
        text = self.turn('How long does it take?')['message']
        self.assertIn('8 minutes cooking; total time not recorded', text)

    def test_lookup_response_cannot_substitute_another_id(self):
        self.turn('breakfast with eggs')
        original_wire = self.wire.__call__
        def substituted(config, method, path, **kwargs):
            if method == 'GET':
                return {'id': 'invented', 'title': 'Invented Recipe'}
            return original_wire(config, method, path, **kwargs)
        with patch.object(search, 'typesense_request', side_effect=substituted):
            result = self.turn('the first one')
        self.assertIsNone(result['selected_recipe'])
        self.assertNotIn('Invented', result['message'])

    def test_model_cannot_add_hard_constraints_via_semantic_query(self):
        class UnsafeInterpretation:
            def interpret(self, *args): return {'semantic_query': 'with cheese under 5 minutes'}
            def compose(self, *args): return {}
        self.turn('beef without cheese under 30 minutes')
        self.service.model = UnsafeInterpretation()
        before = copy.deepcopy(self.state)
        self.turn('more')
        self.assertEqual(self.state, before)


class ValidationTests(unittest.TestCase):
    def test_invalid_inputs(self):
        service = chat.RecipeChatService()
        for msg in [None, {}, [], '', ' ' * 4, 'x' * 301]:
            with self.subTest(message=msg), self.assertRaises(ValueError): service.handle_message(msg)
        for state in [[], {'unknown': 1}, {'max_time': True}, {'min_time': -1}, {'last_result_ids': ['x'] * 6},
                      {'selected_recipe_id': 'invented'}, {'include_ingredients': 'beef'}, {'semantic_query': []}]:
            with self.subTest(state=state), self.assertRaises(ValueError): service.handle_message('chicken', state)

    def test_unconfigured_and_broken_model_factory(self):
        self.assertIsNone(chat.load_model(''))
        self.assertIsNone(chat.load_model('missing.module:factory'))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import model
        cls.backend = model

    def setUp(self):
        self.client = self.backend.app.test_client()
        self.wire = Wire()
        self.patch = patch.object(search, 'typesense_request', side_effect=self.wire)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_multiturn_api_and_no_matcher_warmup(self):
        with patch.object(self.backend.matcher_warmup, 'start_background_warmup') as warm:
            first = self.client.post('/api/recipes/chat', json={'message': 'breakfast with eggs'})
            second = self.client.post('/api/recipes/chat', json={'message': 'the second one', 'state': first.json['state']})
            third = self.client.post('/api/recipes/chat', json={'message': 'does it use milk?', 'state': second.json['state']})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(third.status_code, 200)
        self.assertEqual(third.json['selected_recipe']['id'], 'e2')
        self.assertIn('latency_ms', third.json['search_metadata'])
        warm.assert_not_called()

    def test_bad_json_and_state(self):
        for payload in [[], {}, {'message': []}, {'message': 'hi', 'state': {'selected_recipe_id': 'fake'}}]:
            self.assertEqual(self.client.post('/api/recipes/chat', json=payload).status_code, 400)
        self.assertEqual(self.client.post('/api/recipes/chat', data='{').status_code, 400)

    def test_unavailable_hides_secrets(self):
        with patch.object(search, 'typesense_request', side_effect=search.TypesenseUnavailable('secret-key')):
            response = self.client.post('/api/recipes/chat', json={'message': 'chicken'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret-key', response.get_data(as_text=True))

    def test_options_and_search_independence(self):
        self.assertEqual(self.client.options('/api/recipes/chat').status_code, 204)
        response = self.client.post('/api/recipes/search', json={'query': 'chicken'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('intent', response.json)


if __name__ == '__main__':
    unittest.main()
