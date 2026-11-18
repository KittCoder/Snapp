"""Ordinary household portions and intentional purchased foods stay priceable."""
import sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).parent)]
from ingredient_normalization import parse_ingredient
from basket_quantity import canonical_quantity,convert_quantity,parse_package_info,calculate_coverage,calculate_cost,parse_price_info
from product_ontology import describe,compatibility

OMITTED=['1/3 cup basil fresh chopped','4 slice provolone cheese','4 ciabatta rolls','1/8 cup prepared pesto','1/2 red onion sliced','4 leaves romaine lettuce']

class HouseholdPortionTests(unittest.TestCase):
    def test_portion_units_and_modifier_before_counted_noun_are_parsed(self):
        for text,amount,unit in [(OMITTED[1],4,'slice'),(OMITTED[2],4,'roll'),(OMITTED[4],.5,'onion'),(OMITTED[5],4,'leaf')]:
            parsed=parse_ingredient(text)
            self.assertEqual((parsed.quantity,parsed.unit),(amount,unit),text)
            self.assertEqual(canonical_quantity(parsed.quantity,parsed.unit,parsed.canonical_name).status,'known')
        self.assertEqual(describe(OMITTED[4]).variety,'red')

    def test_standard_portions_keep_food_and_preparation_identity(self):
        self.assertAlmostEqual(convert_quantity(canonical_quantity(4,'slice'),'gram','provolone cheese').base_quantity,112)
        self.assertAlmostEqual(convert_quantity(canonical_quantity(.5,'onion'),'gram','red onion sliced').base_quantity,55)
        self.assertAlmostEqual(convert_quantity(canonical_quantity(4,'leaf'),'gram','romaine lettuce').base_quantity,112)
        self.assertIsNone(convert_quantity(canonical_quantity(4,'slice'),'gram','chicken').base_quantity)
        self.assertIsNone(convert_quantity(canonical_quantity(4,'leaf'),'gram','unidentified herb').base_quantity)
        self.assertIsNone(convert_quantity(canonical_quantity(4,'roll'),'gram','ciabatta').base_quantity)
        self.assertIsNone(convert_quantity(canonical_quantity(4,'leaf'),'count','romaine lettuce').base_quantity)

    def test_package_count_uses_actual_slices_and_preserves_unknown_count_types(self):
        package=parse_package_info({'original_product_name':'Organic Provolone Cheese Slices','package_quantity':8,'package_unit':'count'})
        self.assertEqual((package.item_count,package.item_unit),(8,'slice'))
        coverage=calculate_coverage(canonical_quantity(4,'slice'),package,'provolone cheese')
        self.assertEqual(coverage.packages_required,1)
        self.assertEqual(calculate_cost(coverage,parse_price_info('$7.99')).checkout_cost,7.99)
        unknown=parse_package_info({'original_product_name':'Provolone Cheese','package_quantity':8,'package_unit':'count'})
        self.assertIsNone(calculate_coverage(canonical_quantity(4,'slice'),unknown,'provolone cheese').packages_required)

    def test_verified_roll_count_is_metadata_only_and_pinned_to_exact_package(self):
        feature={'product_id':'items_28952-48459848','original_product_name':'The Avocado Bread Company Seeds & Grains Ciabatta Sandwich Bun','package_quantity':14,'package_unit':'ounce','raw_unit_text':'14 oz'}
        package=parse_package_info(feature)
        self.assertEqual((package.item_count,package.item_unit),(4,'roll'))
        coverage=calculate_coverage(canonical_quantity(4,'roll'),package,'ciabatta rolls')
        self.assertEqual(coverage.packages_required,1)
        self.assertEqual(calculate_cost(coverage,parse_price_info('$7.99')).checkout_cost,7.99)
        self.assertEqual(calculate_cost(coverage,parse_price_info('$5.49')).checkout_cost,5.49)
        self.assertIsNone(parse_package_info(dict(feature,raw_unit_text='16 oz',package_quantity=16)).item_count)
        self.assertIsNone(parse_package_info(dict(feature,original_product_name='Unknown Ciabatta Bread')).item_count)

    def test_portion_counts_survive_pantry_transfer(self):
        from types import SimpleNamespace
        from store_comparison import pantry_transfer_payload
        package=parse_package_info({'original_product_name':'Provolone Cheese Slices','package_quantity':8,'package_unit':'count'})
        transfer=pantry_transfer_payload(['4 slice provolone cheese'],canonical_quantity(4,'slice'),SimpleNamespace(package=package,packages_needed=1),True)
        self.assertEqual(transfer['quantity'],'8 slice')
        from store_requirements import prepare_recipes
        prepared,_=prepare_recipes([{'ingredients':['4 slice provolone cheese']}],[transfer])
        self.assertEqual(prepared[0]['ingredients'],[])

class PurchasedFoodHeadTests(unittest.TestCase):
    def test_ciabbata_and_pesto_match_their_actual_foods(self):
        for query,product in [('ciabatta rolls','Ciabatta Sandwich Buns'),('prepared pesto','Basil Pesto Sauce'),('prepared pesto','Pesto Alla Genovese'),('sun dried tomato pesto','Sundried Tomato Pesto')]:
            self.assertTrue(compatibility(describe(query),describe(product,product=True)).allowed,(query,product))
        self.assertEqual(describe('ciabatta rolls').canonical,'bread:ciabatta')
        self.assertEqual(describe('prepared pesto').canonical,'sauce:pesto')

    def test_food_components_do_not_turn_meals_and_concentrates_into_pesto(self):
        for product in ['Rigatoni with Chicken & Pesto','Bowls Pesto Tortellini','Quinoa Meal Basil Pesto','Basil Pesto Soup','Pesto Sauce Mix','Pesto Paste','Sundried Tomato Pesto']:
            self.assertFalse(compatibility(describe('prepared pesto'),describe(product,product=True)).allowed,product)
        self.assertFalse(compatibility(describe('ciabatta rolls'),describe('Grilled Chicken with Pesto on Ciabatta Bread',product=True)).allowed)
        self.assertFalse(compatibility(describe('fresh basil'),describe('Basil Pesto',product=True)).allowed)

class RealTurkeyBurgerRegressionTests(unittest.TestCase):
    def test_all_six_screenshot_omissions_are_matched_and_costed_in_selected_catalog(self):
        from product_retrieval import DEFAULT_FEATURES_PATH
        if not DEFAULT_FEATURES_PATH.exists():self.skipTest('Optional Morton Williams snapshot unavailable')
        from store_comparison import BasketComparison
        from test_store_comparison import FixtureRegistry
        from store_catalogs import StoreCatalog,StoreMetadata,digest
        registry=FixtureRegistry();registry.stores={'morton-williams':StoreCatalog(StoreMetadata('morton-williams','morton_williams','morton-williams','Morton Williams',None,None,None,0,digest(DEFAULT_FEATURES_PATH),None))}
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown)
        for lines in [OMITTED,[{'name':line,'display':line} for line in OMITTED]]:
            result=engine.compare([{'id':'turkey','ingredients':lines}],['morton-williams'])['stores'][0]
            self.assertEqual(result['coverage_count'],6)
            self.assertTrue(result['complete'],result['unknown_cost_items'])
            self.assertEqual(result['unknown_cost_items'],[])
            self.assertEqual(len(result['product_selections']),6)
            self.assertTrue(all(p['checkout_cost'] is not None for p in result['product_selections']))
            self.assertEqual(result['basket_total'],result['checkout_total_known'])
