"""Negative claims are attributes, never positive ingredient-head evidence."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1])]
from absence_claims import separate_absence_claims
from product_ontology import describe, compatibility
from product_compatibility import ProductMatchService
from basket_quantity import BasketBuilder
from test_product_compatibility import FakeRetriever, feature
import model


class AbsenceClaimIdentityTests(unittest.TestCase):
    def test_claim_forms_remove_only_claim_not_head(self):
        for claim in ['zero sugar', 'sugar-free', 'free of sugar', 'no sugar', 'without sugar']:
            text = claim.replace('-', ' ')
            for name in [text + ' beverage', 'beverage ' + text]:
                self.assertEqual(separate_absence_claims(name), ('beverage', ('sugar',)))
        for claim in ['no added sugar', 'no sugar added', 'without added sugar']:
            self.assertEqual(separate_absence_claims(claim + ' beverage'), ('beverage', ('added_sugar',)))

    def test_negated_tokens_cannot_establish_basic_identity(self):
        for q,p in [('sugar','Zero-Sugar Cola'),('sugar','Sugar-Free Drink'),('sugar','No-Sugar-Added Beverage'),('salt','No-Salt-Added Tomatoes'),('fat','Fat-Free Yogurt'),('honey','Drink Without Honey'),('garlic','Sauce Free of Garlic')]:
            with self.subTest(query=q, product=p):
                self.assertFalse(compatibility(describe(q), describe(p,product=True)).allowed)
        cola = describe('Unseen Brand Zero-Sugar Cola', product=True)
        self.assertEqual((cola.family, cola.subfamily, cola.semantic_head), ('beverage','cola','beverage'))
        self.assertEqual(describe('sugar').family,'sugar')

    def test_explicit_absence_requests_require_verified_attributes(self):
        for q,p in [('sugar-free drink','zero sugar cola'),('fat-free yogurt','Fat-Free Yogurt'),('no-salt-added tomatoes','Tomatoes Without Salt'),('low-sodium broth chicken','Chicken Broth Low Sodium')]:
            self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed,(q,p))
        for q,p in [('sugar-free drink','Cola'),('sugar-free drink','No Added Sugar Drink'),('fat-free yogurt','Whole Milk Yogurt'),('no-salt-added tomatoes','Tomatoes'),('low-sodium chicken broth','Chicken Broth')]:
            self.assertFalse(compatibility(describe(q),describe(p,product=True)).allowed,(q,p))

    def test_product_metadata_can_verify_existing_absence_attributes(self):
        self.assertTrue(compatibility(describe('fat-free yogurt'),describe('Yogurt',feature={'fat_level':'nonfat'},product=True)).allowed)
        self.assertTrue(compatibility(describe('no salt added tomatoes'),describe('Tomatoes',feature={'salted_status':'unsalted'},product=True)).allowed)

    def test_high_similarity_cannot_bypass_head_gate(self):
        for query,name in [('sugar','Zero Sugar Cola'),('sugar','Sugar Free Soda'),('salt','No Salt Added Tomatoes'),('fat','Fat Free Yogurt')]:
            f=feature('adversarial',name);f.update(lexical=1.0,semantic=1.0,exact=True)
            result=ProductMatchService(retriever=FakeRetriever([f])).match_recipe_ingredient(query)
            self.assertIsNone(result.selected_match)

    def test_shopping_path_rejects_absent_component_purchase(self):
        for query,name in [('1 tablespoon sugar','Zero Sugar Cola'),('1 teaspoon salt','No Salt Added Tomatoes'),('1 tablespoon fat','Fat Free Yogurt')]:
            f=feature('adversarial',name);f.update(raw_price='$1.00',package_size='16 oz',lexical=1.0,semantic=1.0)
            service=ProductMatchService(retriever=FakeRetriever([f]));builder=BasketBuilder(service)
            recipe={'extendedIngredients':[{'name':query.split()[-1],'original':query}]}
            self.assertFalse(builder.build_recipe_basket(recipe,use_semantic=False).shopping_basket)
            with patch('basket_quantity.get_basket_builder',return_value=builder),patch.object(model,'should_use_semantic_recipe_matching',return_value=False):
                self.assertFalse(model.match_recipe_ingredients_to_morton_williams(recipe,pantry_items=[]))

    def test_real_inventory_sugar_is_not_zero_sugar_cola(self):
        service=ProductMatchService()
        for name in ['sugar','1 teaspoon sugar, for the top','2 tablespoons sugar']:
            result=service.match_recipe_ingredient(name,use_semantic=False)
            if result.selected_match:
                self.assertEqual(result.selected_match.ontology['family'],'sugar')
                self.assertNotIn('sugar', result.selected_match.ontology.get('absence_claims',()))

    def test_recipe_comments_and_kitchen_removal_do_not_create_heads(self):
        self.assertNotEqual(describe('1 bottle red wine (you want to drink it)').family, 'beverage')
        for q,p in [('parsley chopped without the stalks','Parsley'),('lemons without seeds, juiced','Lemon'),('onion without skin','Onion')]:
            self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed,(q,p))
        self.assertTrue(compatibility(describe('fat-free or low-fat milk'),describe('Milk 2% Reduced Fat',product=True)).allowed)

    def test_absence_class_regression_corpus(self):
        import json
        fixture=Path(__file__).resolve().parents[1]/'evaluation/absence_claim_regressions.jsonl'
        for line in fixture.read_text().splitlines():
            row=json.loads(line)
            with self.subTest(case=row['case_id']):
                self.assertEqual(compatibility(describe(row['ingredient']),describe(row['product_name'],product=True)).allowed,row['expected_allowed'])
