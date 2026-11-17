"""Regressions for the production nugget recipe's matched-but-unpriced items."""
import sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).parent)]
from basket_quantity import canonical_quantity,convert_quantity,parse_package_info,density_for_ingredient
from ingredient_normalization import parse_package_size

NUGGETS={'id':'nuggets-kitchen-regression','ingredients':[
 '1 cup buttermilk','2 pound chicken tenderloins, cut into nugget size','1 cup flour',
 '3 tablespoon parmesan cheese grated','1 tablespoon paprika','1 tablespoon parsley flakes',
 '1 teaspoon salt','1 teaspoon black pepper ground','2 large eggs','2 cup panko bread crumbs','cooking spray']}

class KitchenQuantityTests(unittest.TestCase):
    def test_quart_and_pint_abbreviations_have_known_package_volumes(self):
        for text,unit,ml in [('1 qt','quart',946.353),('1 pt','pint',473.176)]:
            q,u,base,base_unit=parse_package_size(text)
            self.assertEqual((q,u,base_unit),(1,unit,'milliliter'))
            self.assertAlmostEqual(base,ml,places=2)

    def test_only_the_old_package_parser_failure_is_repaired(self):
        feature={'original_product_name':'Buttermilk','raw_unit_text':'1 qt','package_parse_confidence':'low',
                 'package_parse_warnings':['package size unavailable','unrecognized or ambiguous source package size; not optimized']}
        parsed=parse_package_info(feature)
        self.assertTrue(parsed.eligible_for_optimization)
        self.assertEqual(parsed.package_unit,'quart')
        for warning in ['source explicitly marks checkout price as estimated','source purchase minimum/increment not supported by staging cost adapter','variable weight package']:
            unsafe=dict(feature,package_parse_warnings=feature['package_parse_warnings']+[warning])
            self.assertFalse(parse_package_info(unsafe).eligible_for_optimization)
        self.assertEqual(feature['package_parse_confidence'],'low')

    def test_egg_count_inference_never_invents_an_amount_or_counts_other_foods(self):
        quantity=canonical_quantity(2,None,'eggs')
        self.assertEqual((quantity.base_quantity,quantity.base_unit),(2,'egg'))
        self.assertIsNone(canonical_quantity(None,None,'eggs').base_quantity)
        self.assertIsNone(canonical_quantity(2,None,'flour').base_quantity)

    def test_supported_kitchen_measures_use_identity_and_preparation(self):
        for key,amount,unit,grams in [('flour',1,'cup',120),('panko bread crumbs',2,'cup',100),
                ('parmesan cheese grated',3,'tablespoon',18.75),('paprika',1,'teaspoon',2.3),
                ('parsley flakes',1,'teaspoon',.5),('salt',1,'teaspoon',6),('ground black pepper',1,'teaspoon',2.3)]:
            with self.subTest(key=key):
                converted=convert_quantity(canonical_quantity(amount,unit),'gram',key)
                self.assertAlmostEqual(converted.base_quantity,grams,places=1)
        for key in ['fresh parsley','whole parmesan cheese','whole black peppercorns','kosher salt','almond flour','flour tortillas','unidentified ingredient']:
            with self.subTest(unsafe=key):self.assertIsNone(density_for_ingredient(key))

    def test_parsley_flakes_require_dried_herbs(self):
        from product_ontology import describe,compatibility
        query=describe('1 tablespoon parsley flakes')
        self.assertEqual(query.state,'dried')
        self.assertFalse(compatibility(query,describe('Fresh Parsley',product=True)).allowed)
        self.assertTrue(compatibility(query,describe('Parsley Flakes',product=True)).allowed)

    def test_unpriced_reasons_cover_matches_without_purchase_quantities(self):
        from test_store_comparison import FixtureRegistry,catalog
        from store_comparison import BasketComparison
        registry=FixtureRegistry();registry.stores={'a':catalog('a',4,('Rice',))}
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown)
        missing=engine.compare([{'ingredients':['rice']}],['a'])['stores'][0]
        self.assertEqual(missing['unknown_cost_items'][0]['detail'],'MISSING_RECIPE_QUANTITY')
        conversion=engine.compare([{'ingredients':['1 cup rice']}],['a'])['stores'][0]
        self.assertEqual(conversion['unknown_cost_items'][0]['detail'],'QUANTITY_CONVERSION_UNAVAILABLE')

class RealNuggetPricingTests(unittest.TestCase):
    def test_actual_morton_catalog_prices_every_supported_item_without_inventing_the_rest(self):
        from product_retrieval import DEFAULT_FEATURES_PATH
        if not DEFAULT_FEATURES_PATH.exists():self.skipTest('Optional Morton Williams catalog unavailable')
        from store_comparison import BasketComparison
        from test_store_comparison import FixtureRegistry
        from store_catalogs import StoreCatalog,StoreMetadata,digest
        registry=FixtureRegistry()
        registry.stores={'morton-williams':StoreCatalog(StoreMetadata('morton-williams','morton_williams','morton-williams','Morton Williams',None,None,None,0,digest(DEFAULT_FEATURES_PATH),None))}
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown)
        result=engine.compare([NUGGETS],['morton-williams'])['stores'][0]
        self.assertEqual(len(result['product_selections']),9)
        self.assertTrue(all(p['checkout_cost'] is not None for p in result['product_selections']))
        self.assertGreater(result['checkout_total_known'],0)
        self.assertFalse(result['complete']);self.assertIsNone(result['basket_total'])
        self.assertEqual({i['ingredients'][0] for i in result['unknown_cost_items']},{NUGGETS['ingredients'][1],'cooking spray'})
        parsley=next(p for p in result['product_selections'] if 'parsley' in p['ingredients'][0])
        self.assertIn('dried',parsley['product_name'].lower())
