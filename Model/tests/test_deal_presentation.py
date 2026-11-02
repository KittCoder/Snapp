"""Actual shopping adapter/matcher/optimizer/API presentation integration."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import model
from basket_quantity import BasketBuilder
from product_compatibility import ProductMatchService
from test_product_compatibility import FakeRetriever, feature


def shopping_payload(query, names, prices, sizes=None):
    rows=[]
    for i,name in enumerate(names):
        f=feature(str(i),name)
        f.update(price=prices[i],raw_price=f'${prices[i]}',package_quantity=(sizes or [16]*len(names))[i],package_unit='ounce',lexical=1.,semantic=1.)
        rows.append(f)
    service=ProductMatchService(retriever=FakeRetriever(rows));builder=BasketBuilder(service)
    recipe={'id':'shopping-deal-test','title':'Shopping presentation','servings':2,'ingredients':[query],'instructions':[]}
    with patch('basket_quantity.get_basket_builder',return_value=builder),patch.object(model,'should_use_semantic_recipe_matching',return_value=False),patch.object(model,'basket_builder_match_service',return_value=service):
        matches=model.match_recipe_ingredients_to_morton_williams(recipe,pantry_items=[])
        dish=model.spoonacular_recipe_to_dish(recipe,matches,{},2)
    return dish


class ShoppingDealIntegrationTests(unittest.TestCase):
    def test_same_tier_sugar_deal(self):
        dish=shopping_payload('20 oz sugar',['Domino Premium Pure Cane Granulated Sugar','Domino Premium Pure Cane Granulated Sugar 2 lb. Carton'],[6.49,5.29],[24,32])
        item=dish['ingredients'][0];d=item['deal']
        self.assertEqual(item['product_id'],'1');self.assertTrue(d['best_deal'])
        self.assertEqual(d['savings_vs_closest_match'],1.2);self.assertEqual(d['effective_cost'],5.29)
    def test_single_candidate_no_badge(self):
        for query,name in [('1 lb ground beef','Fresh made lean ground beef round'),('1 oz cheddar cheese','Cheddar Cheese'),('1 tbsp olive oil','Filippo Berio Olive Oil, Extra Virgin'),('1 tbsp red wine vinegar','Colavita Red Wine Vinegar')]:
            with self.subTest(query=query):
                dish=shopping_payload(query,[name],[5]);d=dish['ingredients'][0]['deal']
                self.assertFalse(d['best_deal']);self.assertIsNone(d['savings_vs_closest_match'])
    def test_invalid_candidate_not_compared(self):
        dish=shopping_payload('1 oz sugar',['Domino Premium Pure Cane Granulated Sugar','Zero Sugar Cola'],[4,.01])
        d=dish['ingredients'][0]['deal'];self.assertFalse(d['best_deal']);self.assertEqual(d['comparable_candidate_count'],1)
    def test_two_packages_checkout_cost(self):
        d=shopping_payload('20 oz sugar',['Domino Premium Pure Cane Granulated Sugar'],[4],[16])['ingredients'][0]['deal']
        self.assertEqual(d['packages_needed'],2);self.assertEqual(d['effective_cost'],8)
    def test_missing_quantity(self):
        d=shopping_payload('sugar',['Domino Premium Pure Cane Granulated Sugar'],[4])['ingredients'][0]
        self.assertFalse((d.get('deal') or {}).get('best_deal'));self.assertIsNone((d.get('deal') or {}).get('savings_vs_closest_match'))

if __name__=='__main__': unittest.main()
