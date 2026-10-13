"""Exercise adapter, real matching/ranking, cost optimizer and final API rows."""
import itertools
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model
from basket_quantity import BasketBuilder, ingredient_aggregation_signature
from product_compatibility import ProductMatchService
from product_ontology import describe, compatibility
from recipe_ingredient_adapter import canonical_recipe_ingredients, canonical_ingredient_from_spoonacular
from test_product_compatibility import FakeRetriever, feature


def inventory(names):
    rows = []
    for index, name in enumerate(names):
        row = feature(str(index), name)
        row.update(raw_price='$2.99', package_size='16 oz', lexical=1.0, semantic=1.0)
        rows.append(row)
    return rows


class ShoppingPathStructuralTests(unittest.TestCase):
    diagnostics = []

    def run_path(self, query, names, expected=None, schema='extendedIngredients', pantry_items=None, servings=None):
        service = ProductMatchService(retriever=FakeRetriever(inventory(names)))
        builder = BasketBuilder(service)
        if schema == 'extendedIngredients':
            recipe = {'id': 'integration', schema: [{'nameClean': 'garlic' if 'garlic' in query else 'oil' if 'oil' in query else 'steak' if 'steak' in query else 'vinegar', 'original': query}]}
        elif schema == 'structured':
            recipe = {'id': 'integration', 'ingredients': [{'name': 'oil' if 'oil' in query else 'vinegar', 'raw': query, 'quantity': 1, 'unit': 'tablespoon'}]}
        else:
            recipe = {'id': 'integration', 'ingredients': [query]}
        canonical = canonical_recipe_ingredients(recipe)
        result = service.match_recipe_ingredient(canonical[0].matcher_text) if canonical else None
        basket = builder.build_recipe_basket(recipe, use_semantic=False)
        with patch('basket_quantity.get_basket_builder', return_value=builder), patch.object(model, 'should_use_semantic_recipe_matching', return_value=False):
            purchases = model.match_recipe_ingredients_to_morton_williams(recipe, pantry_items=pantry_items or [], servings=servings)
        qi = describe(canonical[0].matcher_text) if canonical else None
        self.diagnostics.append({'input': query, 'normalized_query': qi.normalized_text if qi else None,
            'query_identity': qi.to_dict() if qi else None, 'matcher_result': result.to_dict() if result else None,
            'candidates': [{'product': n, 'identity': describe(n, product=True).to_dict(),
                'hard_compatibility': compatibility(qi, describe(n, product=True)).__dict__ if qi else None} for n in names],
            'basket_rows': [r.product_name for r in basket.shopping_basket],
            'final_purchase_rows': [p['product_name'] for _, p in purchases]})
        if expected is None:
            self.assertFalse(basket.shopping_basket)
            self.assertFalse(purchases)
        else:
            self.assertEqual([r.product_name for r in basket.shopping_basket], [expected])
            self.assertEqual([p['product_name'] for _, p in purchases], [expected])

    def test_headings_excluded_before_matcher_and_purchase(self):
        headings = ['For the steak:', 'For the marinade:', 'For assembly:', 'Cake layers:', 'For the drizzle']
        for heading in headings:
            for schema in ('ingredients', 'extendedIngredients'):
                with self.subTest(heading=heading, schema=schema):
                    self.run_path(heading, ['Hatfield Ham Steak'], schema=schema)
        for item in ({'type': 'heading', 'name': 'Assembly'}, {'original': 'For the sauce:', 'amount': 0}):
            self.assertFalse(canonical_recipe_ingredients({'extendedIngredients': [item]}))
        service = ProductMatchService(retriever=FakeRetriever(inventory(['Ham Steak'])))
        with patch.object(service, 'match_recipe_ingredients', wraps=service.match_recipe_ingredients) as call:
            BasketBuilder(service).build_recipe_basket({'ingredients': headings})
            self.assertEqual(call.call_args.args[0], [])
        self.assertTrue(canonical_recipe_ingredients({'ingredients': ['1 tablespoon sauce:']}))

    def test_vinegar_subtype_cross_product_matrix(self):
        names = ['Balsamic Vinegar', 'Red Wine Vinegar', 'White Wine Vinegar', 'Rice Vinegar', 'Apple Cider Vinegar', 'Distilled White Vinegar', 'Sherry Vinegar']
        for wanted, wrong in itertools.permutations(names, 2):
            with self.subTest(wanted=wanted, wrong=wrong):
                self.run_path('1 tablespoon ' + wanted, [wrong])
        for wanted in names:
            self.run_path('1 tablespoon ' + wanted, [wanted], wanted)

    def test_negative_alternative_is_not_positive_permission(self):
        for note in ['or any non-balsamic vinegar', 'or anything but balsamic vinegar', 'or not balsamic vinegar', 'or other than balsamic vinegar']:
            self.run_path('2 tablespoon rice vinegar (' + note + ')', ['Balsamic Vinegar'])
            self.run_path('2 tablespoon rice vinegar (' + note + ')', ['Rice Vinegar'], 'Rice Vinegar')

    def test_oil_grade_and_direction(self):
        for wrong in ['Olive Oil', 'Refined Olive Oil', 'Light Olive Oil', 'Canola Oil', 'Vegetable Oil', 'Sesame Oil']:
            self.run_path('1 tablespoon extra virgin olive oil', [wrong])
        self.run_path('1 tablespoon extra virgin olive oil', ['Extra Virgin Olive Oil'], 'Extra Virgin Olive Oil')
        self.run_path('1 tablespoon olive oil', ['Extra Virgin Olive Oil'], 'Extra Virgin Olive Oil')
        for wrong in ['Olive Oil', 'Extra Virgin Olive Oil']:
            self.run_path('1 tablespoon light olive oil', [wrong])

    def test_garlic_prepared_head_negatives(self):
        for query in ['1 teaspoon minced garlic', '2 garlic cloves', '1 tablespoon garlic']:
            for wrong in ['Garlic Aioli', 'Garlic Sauce', 'Garlic Bread', 'Garlic Dressing', 'Garlic Flavored Pasta Meal']:
                self.run_path(query, [wrong])
        self.run_path('0.5 teaspoon minced garlic', ['Minced Garlic'], 'Minced Garlic')
        item = canonical_ingredient_from_spoonacular({'name': 'minced garlic', 'original': '1/2 teaspoon minced garlic'})
        self.assertEqual(item.matcher_text.lower().count('minced'), 1)
        self.assertEqual(item.note, 'minced')

    def test_steak_cuts_exact_matrix(self):
        names = ['Beef Skirt Steak', 'Beef Hanger Steak', 'Beef Flank Steak', 'Beef Sirloin Steak', 'Beef Ribeye Steak']
        for wanted, wrong in itertools.permutations(names, 2):
            self.run_path('8 ounce ' + wanted, [wrong])
        for wanted in names:
            self.run_path('8 ounce ' + wanted, [wanted], wanted)
        self.run_path('8 ounce skirt steak', ['Ham Steak'])

    def test_cost_aggregation_preserves_structural_requirements(self):
        for a, b in [('red wine vinegar', 'white wine vinegar'), ('balsamic vinegar', 'vinegar'), ('extra virgin olive oil', 'olive oil'), ('skirt steak', 'hanger steak')]:
            self.assertNotEqual(ingredient_aggregation_signature('1 tablespoon ' + a)[0], ingredient_aggregation_signature('1 tablespoon ' + b)[0])
        service = ProductMatchService(retriever=FakeRetriever(inventory(['Olive Oil', 'Extra Virgin Olive Oil'])))
        service.feature_by_id['0']['raw_price'] = '$0.50'
        basket = BasketBuilder(service).build_recipe_basket({'ingredients': ['1 tablespoon extra virgin olive oil', '1 tablespoon olive oil']}, optimization_mode='lowest_checkout_cost', use_semantic=False)
        evoo = next(r for r in basket.shopping_basket if '1 tablespoon extra virgin olive oil' in r.ingredients)
        self.assertEqual(evoo.product_name, 'Extra Virgin Olive Oil')

    def test_quantity_adjustments_preserve_identity(self):
        for name in ['red wine vinegar', 'balsamic vinegar', 'extra virgin olive oil', 'minced garlic', 'skirt steak']:
            ingredient = {'display': '2 tablespoon ' + name, 'name': name}
            buckets = model.pantry_quantity_buckets([{'name': name, 'quantity': '1 tablespoon'}])
            adjusted = model.pantry_adjusted_ingredient_text(ingredient, buckets, set())
            self.assertIn(name, adjusted)
            per_person = model.pantry_adjusted_ingredient_text({'display': '1 tablespoon ' + name + ' per person', 'name': name}, {}, set(), servings=4)
            self.assertIn(name, per_person)
            self.assertTrue(per_person.startswith('4 tablespoon'))

    def test_wrong_pantry_identity_cannot_cover_request(self):
        for query, pantry in [('red wine vinegar', 'white vinegar'), ('balsamic vinegar', 'red wine vinegar'), ('extra virgin olive oil', 'olive oil'), ('skirt steak', 'hanger steak')]:
            text = '1 tablespoon ' + query
            buckets = model.pantry_quantity_buckets([{'name': pantry, 'quantity': '10 tablespoon'}])
            self.assertEqual(model.pantry_adjusted_ingredient_text({'display': text}, buckets, set()), text)

    def test_structured_labels_cannot_broaden_identity(self):
        for query, wrong in [('red wine vinegar', 'White Vinegar'), ('balsamic vinegar', 'White Wine Vinegar'), ('extra virgin olive oil', 'Olive Oil')]:
            self.run_path('1 tablespoon ' + query, [wrong], schema='structured')

    def test_pantry_and_serving_changes_through_final_rows(self):
        for query, product in [('red wine vinegar', 'Red Wine Vinegar'), ('balsamic vinegar', 'Balsamic Vinegar'), ('extra virgin olive oil', 'Extra Virgin Olive Oil'), ('minced garlic', 'Minced Garlic'), ('skirt steak', 'Beef Skirt Steak')]:
            self.run_path('2 tablespoon ' + query, [product], product,
                          pantry_items=[{'name': query, 'quantity': '1 tablespoon'}])
            self.run_path('1 tablespoon ' + query + ' per person', [product], product, servings=4)

    @classmethod
    def tearDownClass(cls):
        out = Path(__file__).resolve().parents[2] / 'data/matcher_shopping_path_audit'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'integration_diagnostics.json').write_text(json.dumps(cls.diagnostics, indent=2, default=str) + '\n')
