import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ingredient_normalization import parse_package_size,extract_product_features
from product_ontology import describe,compatibility
from basket_quantity import parse_package_info

class RefreshPackageTests(unittest.TestCase):
    def test_explicit_sizes(self):
        for text,amount,unit in [('10 oz',10,'ounce'),('16.9 oz',16.9,'ounce'),('16.9 fl oz',16.9,'fluid ounce'),('32 oz',32,'ounce'),('1 lb',1,'pound'),('1 lb 4 oz',20,'ounce'),('2 x 8 oz',16,'ounce'),('2x8oz',16,'ounce'),('6 ct',6,'count'),('3/4 lb',.75,'pound'),('1 pint',1,'pint'),('1 quart',1,'quart'),('1 gallon',1,'gallon')]:
            with self.subTest(text=text):self.assertEqual(parse_package_size(text)[:2],(amount,unit))
    def test_ambiguous_ranges_and_numbers_abstain(self):
        for text in ['8-12 oz','22-30oz jar','6 ct 13 oz']:
            with self.subTest(text=text):
                self.assertEqual(parse_package_size(text),(None,None,None,None))
    def test_raw_source_preferred_over_name_and_legacy_unit(self):
        f=extract_product_features({'name':'Product 2026 containing 10 oz','price':'$2.99','unit':'1 oz','raw_size_text':'16.9 fl oz','source':'mortonwilliams-storefront'})
        self.assertEqual(f['package_quantity'],16.9);self.assertEqual(f['package_unit'],'fluid ounce');self.assertEqual(f['raw_size_text'],'16.9 fl oz')
    def test_average_pack_weight_is_not_exact_checkout_evidence(self):
        f=extract_product_features({'name':'Ground Beef Average Weight 1.25 lb Pack','price':'$7.28','unit':'1 lb','raw_size_text':'per lb','source':'mortonwilliams-storefront'})
        self.assertEqual(f['package_parse_confidence'],'low')
        self.assertFalse(parse_package_info(f).eligible_for_optimization)

    def test_ambiguous_source_size_cannot_be_replaced_by_name_numbers(self):
        f=extract_product_features({'name':'Example Rice 2026 10 oz','price':'$2.99','unit':'6 ct 13 oz','raw_size_text':'6 ct 13 oz','source':'mortonwilliams-storefront'})
        self.assertIsNone(f['package_quantity'])
        self.assertFalse(parse_package_info(f).eligible_for_optimization)

    def test_weight_price_is_not_a_fixed_each_price(self):
        from basket_quantity import parse_price_info
        f=extract_product_features({'name':'Garlic','price':'$0.85','unit':'1 lb','raw_size_text':'each','raw_pricing_unit_text':'$0.85 / lb','source':'mortonwilliams-storefront'})
        self.assertEqual(f['raw_price'],'$0.85 / lb')
        self.assertIsNone(parse_price_info(f['raw_price'],f).checkout_price)
        self.assertFalse(parse_package_info(f).eligible_for_optimization)

    def test_source_ids_preserve_same_named_variants(self):
        seen=set()
        for source_id in ['items_test-1','items_test-2']:
            f=extract_product_features({'name':'Example Rice','price':'$2.99','unit':'16 oz','source':'mortonwilliams-storefront','source_id':source_id},seen_fingerprints=seen)
            self.assertTrue(f['eligible_for_retrieval'])

    def test_unverified_pdf_size_cannot_optimize(self):
        f=extract_product_features({'name':'Olive Oil','price':'$7.99','unit':'7.3 oz','source':'mortonwilliams-pdf','size_evidence_source':'pdf_layout_unverified'})
        self.assertFalse(parse_package_info(f).eligible_for_optimization)

class CommodityHeadTests(unittest.TestCase):
    def test_sugar_component_is_not_sugar(self):
        for query in ['sugar','white sugar','1 teaspoon white sugar']:
            for name in ['Blue Sugar Sprinkles',"Stewart's Key Lime Made with Sugar",'Candy with Sugar','Sugar Cookies','Sugar Dessert','Sugar Beverage','Sugar Sauce','Sugar Dressing','Key Lime Made with Cane Sugar','Key Lime Containing Sugar','Ocean Spray 50% Less Sugar Dried Cranberries, Dried Fruit','Brown Sugar English Muffins','Sugar Pancakes']:
                with self.subTest(query=query,name=name):self.assertFalse(compatibility(describe(query),describe(name,product=True)).allowed)
    def test_rice_components_are_not_grain(self):
        for name in ['Rice Cakes','Haddar Cakes, Multigrain Rice, Unsalted','Rice Crackers','Rice Cereal','Rice Pudding','Rice Drink','Rice Sauce','Rice Candy']:
            with self.subTest(name=name):self.assertFalse(compatibility(describe('rice'),describe(name,product=True)).allowed)
    def test_prepared_noodle_head_precedes_garlic_component(self):
        self.assertFalse(compatibility(describe('garlic'),describe('Example Garlic Pepper Ramen',product=True)).allowed)
        self.assertFalse(compatibility(describe('rice'),describe('Example Yellow Rice, Saffron',product=True)).allowed)

    def test_bread_head_precedes_olive_oil_component(self):
        self.assertFalse(compatibility(describe('olive oil'),describe('Example Focaccia, Olive Oil & Sea Salt',product=True)).allowed)
        self.assertTrue(compatibility(describe('focaccia'),describe('Example Focaccia, Olive Oil & Sea Salt',product=True)).allowed)

    def test_rye_bread_requires_rye_grain(self):
        self.assertFalse(compatibility(describe('rye bread'),describe('Garlic Bread',product=True)).allowed)
        self.assertTrue(compatibility(describe('rye bread'),describe('Seeded Jewish Rye Bread',product=True)).allowed)

    def test_directional_specific_queries(self):
        for query,name in [('rice cakes','Rice Cakes'),('sugar sprinkles','Blue Sugar Sprinkles'),('white sugar','Domino Granulated Sugar'),('rice','Long Grain White Rice')]:
            with self.subTest(query=query):self.assertTrue(compatibility(describe(query),describe(name,product=True)).allowed)
    def test_reliable_source_categories_support_head(self):
        self.assertFalse(compatibility(describe('sugar'),describe('Key Lime Sugar',feature={'source_categories':['soft drinks']},product=True)).allowed)
        self.assertFalse(compatibility(describe('rice'),describe('Rice Cakes',feature={'category':'grains'},product=True)).allowed)
        self.assertTrue(compatibility(describe('white sugar'),describe('Granulated Sugar',feature={'source_categories':['soft drinks']},product=True)).allowed)

class CommodityDealSafetyTests(unittest.TestCase):
    def test_cheapest_derivatives_never_enter_safe_purchase_set(self):
        from test_product_compatibility import FakeRetriever, feature
        from product_compatibility import ProductMatchService
        from basket_quantity import BasketBuilder
        cases=[('1 oz olive oil','Olive Oil',['Focaccia, Olive Oil & Sea Salt']),('1 oz white sugar','Granulated Sugar',['Blue Sugar Sprinkles','Key Lime Made with Sugar','50% Less Sugar Dried Cranberries, Dried Fruit']),('1 oz rice','Long Grain White Rice',['Rice Cakes','Rice Cereal','Yellow Rice, Saffron']),('1 oz garlic','Garlic',['Garlic Pepper Ramen','Garlic Aioli']),('1 oz rye bread','Seeded Rye Bread',['Garlic Bread'])]
        for query,right,wrong in cases:
            rows=[]
            for i,name in enumerate([right]+wrong):
                row=feature(str(i),name);price=10 if i==0 else .01
                row.update(price=price,raw_price=f'${price}',package_quantity=16,package_unit='ounce',lexical=1.,semantic=1.)
                rows.append(row)
            service=ProductMatchService(retriever=FakeRetriever(rows));basket=BasketBuilder(service).build_recipe_basket({'ingredients':[query]},use_semantic=False)
            with self.subTest(query=query):
                self.assertTrue(basket.shopping_basket)
                self.assertEqual(basket.shopping_basket[0].product_id,'0')
