import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility

class HerbProductHeadTests(unittest.TestCase):
    def test_flavor_tokens_do_not_establish_herb_identity(self):
        cases=[('fresh mint','Mentos Gum, Sugarfree, Fresh Mint'),('mint','Breath Mints'),('mint','Mint Candy'),('mint','Mint Tea'),('mint','Mint Chocolate'),('mint','Mint Toothpaste'),('mint','Mint Mouthwash'),('fresh basil','Basil-flavored Crackers'),('fresh rosemary','Rosemary Bread')]
        for q,p in cases:
            with self.subTest(query=q,product=p):self.assertFalse(compatibility(describe(q),describe(p,product=True)).allowed)
    def test_all_basic_herbs_reject_derived_flavors(self):
        for herb in ['mint','parsley','cilantro','basil','oregano','rosemary','thyme','sage','dill']:
            for outer in ['Gum','Candy','Tea','Drink','Dessert','Sauce','Dressing','Crackers','Toothpaste','Mouthwash']:
                with self.subTest(herb=herb,outer=outer):self.assertFalse(compatibility(describe(herb),describe(herb+' '+outer,product=True)).allowed)
    def test_explicit_derived_queries_remain_possible(self):
        for q,p in [('mint gum','Mentos Mint Gum'),('mint tea','Mint Tea'),('rosemary bread','Rosemary Bread'),('basil crackers','Basil Crackers')]:
            with self.subTest(query=q):self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed)
    def test_valid_herbs_and_seasonings_remain_possible(self):
        for q,p in [('fresh mint','Fresh Mint Leaves'),('fresh basil','Fresh Basil'),('fresh rosemary','Fresh Rosemary'),('oregano','Oregano Leaves'),('sage','Sage'),('dill','Dill Weed')]:
            with self.subTest(query=q):self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed)
    def test_fresh_herbs_require_fresh_evidence(self):
        for p in ['Dried Mint','Mint Extract','Mint Flavoring','Mint Leaves']:
            with self.subTest(product=p):self.assertFalse(compatibility(describe('fresh mint'),describe(p,product=True)).allowed)
        self.assertTrue(compatibility(describe('fresh mint'),describe('Mint Leaves',feature={'freshness':'fresh'},product=True)).allowed)
    def test_cheap_gum_never_enters_herb_optimizer(self):
        from test_product_compatibility import FakeRetriever,feature
        from product_compatibility import ProductMatchService
        from basket_quantity import BasketBuilder
        rows=[]
        for pid,name,price in [('herb','Fresh Mint Leaves',10),('gum','Mentos Gum Fresh Mint',.01)]:
            f=feature(pid,name);f.update(price=price,raw_price=f'${price}',package_quantity=1,package_unit='ounce',lexical=1,semantic=1);rows.append(f)
        b=BasketBuilder(ProductMatchService(retriever=FakeRetriever(rows))).build_recipe_basket({'ingredients':['1 oz fresh mint']},use_semantic=False)
        self.assertEqual(b.shopping_basket[0].product_id,'herb')
    def test_spice_aisle_minced_alliums_are_not_fresh_produce(self):
        for herb in ['Onions','Garlic']:
            f={'source_categories':['n-spices-seasoning-94997']};p=describe('Minced '+herb,feature=f,product=True)
            self.assertEqual(p.state,'dried')
            self.assertFalse(compatibility(describe(herb),p).allowed)
            self.assertTrue(compatibility(describe('dried minced '+herb),p).allowed)
    def test_minced_fresh_or_jarred_alliums_are_not_inferred_dried(self):
        for name,f in [('Fresh Minced Onions',{'source_categories':['spices-seasoning']}),('Minced Garlic',{'source_categories':['fresh-vegetables']}),('Minced Onions',{})]:
            self.assertNotEqual(describe(name,feature=f,product=True).state,'dried')
    def test_source_snack_aisle_cannot_establish_a_produce_head(self):
        p=describe('Unseen Brand Classic Onion',feature={'source_categories':['n-frozen-snacks-74004']},product=True)
        self.assertFalse(compatibility(describe('small onion'),p).allowed)
        self.assertTrue(compatibility(describe('onion'),describe('Onion',feature={'source_categories':['fresh-vegetables']},product=True)).allowed)
    def test_pickled_goods_source_evidence_rejects_raw_produce_request(self):
        p=describe('Unseen Brand Silverskin Onions',feature={'source_categories':['n-olives-pickled-goods-35476']},product=True)
        self.assertEqual(p.treatment,'preserved')
        self.assertFalse(compatibility(describe('small onion'),p).allowed)
