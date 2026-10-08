import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model
import recipe_chat
import recipe_search_typesense as search


class DetailTests(unittest.TestCase):
    def setUp(self):
        self.indexed = dict(id='exact-id', title='Egg dinner', ingredient_names=['egg'],
                            ingredients_text=['2 eggs'], equipment=['pan'])
        self.service = patch.object(recipe_chat, 'configured_service').start()
        self.lookup = patch.object(search, 'get_recipe_by_id', return_value=self.indexed).start()
        self.records = patch.object(model, 'load_all_recipes_by_id', return_value={}).start()
        self.addCleanup(patch.stopall)
        self.client = model.app.test_client()

    def request(self, **extra):
        return self.client.post('/api/recipes/detail', json={'recipe_id': 'exact-id', **extra})

    def test_full_index_record_without_optional_facts(self):
        result = self.request().get_json()['dish']
        self.assertEqual(result['recipe_id'], 'exact-id')
        self.assertEqual(result['name'], 'Egg dinner')
        self.assertEqual(result['recipe']['ingredients'][0]['display'], '2 eggs')
        self.assertFalse(result['recipe']['instructions'])
        self.assertIsNone(result['recipe']['servings'])
        self.assertNotIn('estimated_price_total', result)
        self.assertEqual(result['recipe']['equipment'], ['pan'])

    def test_exact_typesense_record_supplies_ordered_instructions(self):
        self.indexed.update(instructions=['  Beat eggs.  ', 'Cook.', 'Serve.'], servings=2,
                            source_id='exact-id', ingredients=[{'name': 'egg', 'quantity': 2}])
        self.records.return_value = {'exact-id': {'name': 'Different Dishes recipe'}}
        result = self.request().get_json()['dish']
        self.assertEqual(result['name'], 'Egg dinner')
        self.assertEqual(result['recipe']['instructions'], ['  Beat eggs.  ', 'Cook.', 'Serve.'])
        self.assertEqual(result['recipe']['servings'], 2)
        self.assertEqual(result['recipe']['stored_ingredients'], self.indexed['ingredients'])
        self.records.assert_not_called()
        self.lookup.assert_called_once_with('exact-id', self.service.return_value.config)

    def test_string_instruction_text_is_unchanged(self):
        self.indexed['instructions'] = '  First step.\nThen serve.  '
        result = self.request().get_json()['dish']
        self.assertEqual(result['recipe']['instructions'], self.indexed['instructions'])

    def test_missing_and_invalid_ids(self):
        self.lookup.return_value = None
        self.assertEqual(self.request().status_code, 404)
        self.assertEqual(self.client.post('/api/recipes/detail', json={}).status_code, 400)

    def test_schedule_uses_existing_matcher_and_dishes_adapter(self):
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', return_value=[]) as matcher, \
             patch.object(model, 'morton_williams_store_lookup', return_value={}):
            result = self.request(for_schedule=True, pantry_items=[]).get_json()['dish']
        matcher.assert_called_once()
        self.assertEqual(result['recipe_id'], 'exact-id')
        self.assertEqual(result['name'], 'Egg dinner')
        self.assertEqual(result['recipe']['ingredients'][0]['display'], '2 eggs')
        self.assertEqual(result['ingredients_to_buy'], [])
        self.assertNotIn('servings', result)

    def test_failure_is_concise(self):
        self.lookup.side_effect = RuntimeError('private backend exception')
        result = self.request()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('private backend exception', result.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main()
