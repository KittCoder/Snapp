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

    def test_sale_metadata_only_labels_verified_offers(self):
        matches = [
            ({"measure": "2 eggs", "display": "2 eggs"},
             {"product_name": "Eggs", "is_on_sale": True, "sale_offer": "2 for $5"}),
            ({"measure": "rice"}, {"product_name": "Rice", "is_on_sale": False}),
        ]
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', return_value=matches):
            result = self.request(include_sale_matches=True).get_json()['dish']
        self.assertEqual(len(result['sale_ingredients']), 1)
        self.assertEqual(result['sale_ingredients'][0]['recipe_display'], '2 eggs')
        self.assertEqual(result['sale_ingredients'][0]['sale_offer'], '2 for $5')
        self.assertNotIn('ingredients_to_buy', result)

    def test_sale_failure_does_not_block_recipe(self):
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', side_effect=RuntimeError('private')):
            response = self.request(include_sale_matches=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['dish']['sale_metadata_unavailable'])
        self.assertNotIn('private', response.get_data(as_text=True))

    def test_failure_is_concise(self):
        self.lookup.side_effect = RuntimeError('private backend exception')
        result = self.request()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('private backend exception', result.get_data(as_text=True))

    def test_price_preview_is_available_before_scheduling(self):
        matches = [({'measure': '2 eggs', 'name': 'egg'},
                    {'estimated_price_total': 4.5, 'source_ingredients': ['2 eggs']})]
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', return_value=matches), \
             patch.object(model, 'spoonacular_recipe_to_dish') as schedule_adapter:
            response = self.request(include_price_estimate=True)
        self.assertEqual(response.status_code, 200)
        dish = response.get_json()['dish']
        self.assertEqual(dish['grocery_estimate']['total'], 4.5)
        self.assertEqual(dish['grocery_estimate']['status'], 'complete')
        self.assertEqual(dish['recipe']['ingredients'][0]['display'], '2 eggs')
        schedule_adapter.assert_not_called()

    def test_unpriced_ingredients_produce_partial_subtotal(self):
        self.indexed['ingredient_names'] = ['egg', 'rice']
        self.indexed['ingredients_text'] = ['2 eggs', '1 cup rice']
        matches = [({'measure': '2 eggs'}, {'estimated_price_total': 4.5})]
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', return_value=matches):
            estimate = self.request(include_price_estimate=True).get_json()['dish']['grocery_estimate']
        self.assertEqual(estimate['status'], 'partial')
        self.assertEqual(estimate['total'], 4.5)
        self.assertEqual(estimate['unpriced_ingredients'], 1)

    def test_price_failure_keeps_recipe_available_and_never_invents_zero(self):
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', side_effect=RuntimeError('private')):
            response = self.request(include_price_estimate=True)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()['dish']['grocery_estimate']['total'])
        self.assertEqual(response.get_json()['dish']['grocery_estimate']['status'], 'unavailable')

    def test_all_required_ingredients_are_included_in_estimate(self):
        matches = [({'name': 'egg', 'measure': f'{index} eggs'},
                    {'estimated_price_total': 1, 'price': 1, 'package_grams': 100})
                   for index in range(1, 13)]
        dish = model.spoonacular_recipe_to_dish(
            {'id': 'full-recipe', 'title': 'Egg dinner', 'extendedIngredients': []}, matches, {}, 2)
        self.assertEqual(dish['estimated_price_total'], 12)
        self.assertEqual(len(dish['ingredients_to_buy']), 12)

    def test_scheduling_calculates_usda_nutrition_for_original_ingredients(self):
        self.indexed.update(ingredients_text=['2 large eggs'], servings=2)
        with patch.object(model, 'match_recipe_ingredients_to_morton_williams', return_value=[]), \
             patch.object(model, 'morton_williams_store_lookup', return_value={}):
            dish = self.request(for_schedule=True, pantry_items=[{'name': 'eggs', 'quantity': '2'}]).get_json()['dish']
        self.assertEqual(dish['nutrition_source'], 'USDA FoodData Central')
        self.assertEqual(dish['nutrition_status'], 'complete')
        self.assertGreater(dish['nutrition_per_person']['protein_g'], 0)
        self.assertEqual(dish['nutrition_ingredients'][0]['grams'], 100)
        self.assertAlmostEqual(dish['nutrition_per_person']['protein_g'], dish['nutrition_total']['protein_g']/2)
        self.assertEqual(dish['ingredients_to_buy'], [])

    def test_saved_recipe_nutrition_endpoint_uses_canonical_recipe_quantities(self):
        response = self.client.post('/api/recipes/nutrition', json={
            'recipe': {'servings': 2, 'ingredients': [{'display': '2 large eggs'}]}, 'household_size': 4})
        self.assertEqual(response.status_code, 200)
        nutrition = response.get_json()
        self.assertEqual(nutrition['nutrition_servings'], 2)
        self.assertEqual(nutrition['nutrition_source'], 'USDA FoodData Central')
        self.assertEqual(nutrition['nutrition_ingredients'][0]['grams'], 100)
        self.assertEqual(self.client.post('/api/recipes/nutrition', json={'recipe': {}}).status_code, 400)

    def test_dishes_localizes_recipe_without_changing_canonical_facts(self):
        dish = {'recipe_id': 'dishes-recipe', 'name': 'Egg dinner', 'ingredients': [],
                'recipe': {'ingredients': [{'display': '2 eggs'}], 'instructions': ['Beat eggs.']}}
        class Translator:
            def translate(self, text, source, target):
                return {'Egg dinner': 'Cena de huevos', '2 eggs': '2 huevos',
                        'Beat eggs.': 'Bate los huevos.'}[text]
        with patch.object(model, 'build_real_recipe_results', return_value=([dish], False)), \
             patch.object(model, 'morton_williams_store_lookup', return_value={}), \
             patch('recipe_chat_presentation.translation_provider', return_value=Translator()), \
             patch('recipe_chat_presentation._save_lines'):
            response = self.client.post('/dishes', json={'meal_prompt': 'eggs', 'locale': 'es'})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()['dishes'][0]
        self.assertEqual(result['recipe']['ingredients'][0]['display'], '2 eggs')
        self.assertEqual(result['localized_recipe']['name'], 'Cena de huevos')
        self.assertEqual(result['localized_recipe']['ingredients'][0]['display'], '2 huevos')
        self.assertEqual(result['localized_recipe']['instructions'], ['Bate los huevos.'])

if __name__ == '__main__':
    unittest.main()
