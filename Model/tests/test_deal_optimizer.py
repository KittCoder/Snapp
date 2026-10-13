import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from basket_quantity import BasketBuilder, canonical_quantity
from test_basket_quantity import ranked


class DealTests(unittest.TestCase):
    def choose(self, scores=(.99,.97), prices=(6.49,5.29), sizes=(16,16), need=16, conflicts=None, types=('exact','exact')):
        features={str(i): {'product_id':str(i), 'original_product_name':f'Sugar {size} oz', 'package_quantity':size,'package_unit':'ounce','price':prices[i]} for i,size in enumerate(sizes)}
        service=type('Service',(),{'feature_by_id':features,'match_mode':'exact'})()
        candidates=[ranked(str(i), features[str(i)]['original_product_name'],score=score,conflicts=conflicts if i==1 else None) for i,score in enumerate(scores)]
        for c,t in zip(candidates,types): c.match_type=t
        return BasketBuilder(service).optimize_ingredient_purchase(canonical_quantity(need,'ounce'),'sugar',candidates,top1_product_id='0')

    def test_same_tier_price(self): self.assertEqual(self.choose().selected.product_id,'1')
    def test_weak_cheap(self): self.assertEqual(self.choose(scores=(.99,.84),prices=(6.49,.01)).selected.product_id,'0')
    def test_package_cost(self):
        result=self.choose(prices=(4,5.5),sizes=(16,24),need=20)
        self.assertEqual(result.selected.product_id,'1')
        self.assertEqual(result.selected.effective_cost,5.5)
        self.assertEqual(result.alternatives[0].effective_cost,8)
    def test_waste_tie(self): self.assertEqual(self.choose(prices=(5,5.03),sizes=(24,20),need=20).selected.product_id,'1')
    def test_hard_reject(self): self.assertEqual(self.choose(prices=(6,.01),conflicts=[{'classification':'hard_reject'}]).selected.product_id,'0')
    def test_no_lower_tier(self): self.assertEqual(self.choose(scores=(.97,.96),prices=(6,.01)).selected.product_id,'0')
    def test_no_substitute(self): self.assertEqual(self.choose(types=('exact','substitute'),prices=(6,.01)).selected.product_id,'0')
    def test_unknown_cost_keeps_identity(self):
        result=self.choose(sizes=(None,None))
        self.assertEqual(result.selected.product_id,'0')
        self.assertIsNone(result.selected.effective_cost)
        self.assertEqual(result.selected.deal_confidence,'low')
    def test_sale(self):
        from basket_quantity import parse_price_info
        self.assertEqual(parse_price_info(6,{'sale_price':4}).checkout_price,4)
        self.assertEqual(parse_price_info(6,{'sale_price':'unknown'}).checkout_price,6)

if __name__=='__main__': unittest.main()

class CheapWrongIdentityTests(unittest.TestCase):
    def test_guardrail_classes_with_price_pressure(self):
        from product_compatibility import ProductMatchService
        from test_product_compatibility import FakeRetriever, feature
        cases=[('1 oz sugar','Granulated Sugar','Zero Sugar Cola'),
               ('1 tbsp red wine vinegar','Red Wine Vinegar','White Vinegar'),
               ('1 lb skirt steak','Skirt Steak','Hanger Steak'),
               ('1 tbsp extra virgin olive oil','Extra Virgin Olive Oil','Canola Oil'),
               ('1 lb salmon','Atlantic Salmon','Tilapia'),
               ('1 oz black beans','Black Beans','Chickpeas'),
               ('1 oz cheddar cheese','Cheddar Cheese','Mozzarella Cheese'),
               ('1 tsp minced garlic','Minced Garlic','Garlic Aioli'),
               ('1 oz fresh spinach','Fresh Spinach','Frozen Spinach'),
               ('1 oz sugar','Granulated Sugar','Sugar Free Candy')]
        for query,right,wrong in cases:
            with self.subTest(query=query):
                rows=[]
                for pid,name,price in [('right',right,10),('wrong',wrong,.01)]:
                    f=feature(pid,name);f.update(price=price,raw_price=f'${price}',package_quantity=16,package_unit='ounce',lexical=1.0,semantic=1.0);rows.append(f)
                service=ProductMatchService(retriever=FakeRetriever(rows))
                basket=BasketBuilder(service).build_recipe_basket({'ingredients':[query]},use_semantic=False)
                self.assertTrue(basket.shopping_basket)
                self.assertEqual(basket.shopping_basket[0].product_id,'right')
