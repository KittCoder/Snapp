"""Quantities must survive unit conversion, aggregation, scaling and pantry use."""
import math
import unittest
from basket_quantity import (BasketBuilder, canonical_quantity, convert_quantity,
    calculate_coverage, calculate_cost, parse_package_info, parse_price_info)
from recipe_ingredient_adapter import canonical_recipe_ingredients
from test_basket_quantity import FakeMatchService

class QuantityIntegrityTests(unittest.TestCase):
    def test_equivalent_volume_units_do_not_buy_an_extra_package(self):
        for unit,amount in [('tablespoon',16),('teaspoon',48),('fluid ounce',8),('pint',.5),('quart',.25),('gallon',.0625)]:
            with self.subTest(unit=unit):
                package=parse_package_info({'package_quantity':1,'package_unit':'cup'})
                coverage=calculate_coverage(canonical_quantity(amount,unit),package)
                self.assertEqual(coverage.packages_required,1)
        package=parse_package_info({'package_quantity':1,'package_unit':'cup'})
        self.assertEqual(calculate_coverage(canonical_quantity(1.001,'cup'),package).packages_required,2)

    def test_small_quantities_are_not_rounded_away(self):
        quantity=canonical_quantity(.00001,'teaspoon')
        self.assertGreater(quantity.base_quantity,0)
        package=parse_package_info({"package_quantity":1,"package_unit":"gram"})
        self.assertEqual(calculate_coverage(canonical_quantity(1e-8,"gram"),package).packages_required,1)
        self.assertAlmostEqual(convert_quantity(quantity,'teaspoon').quantity,.00001,places=8)
        for invalid in [-1,float('nan'),float('inf')]:
            self.assertIsNone(canonical_quantity(invalid,'gram').base_quantity)

    def test_mixed_units_merge_without_dropping_either_requirement(self):
        for lines in [['1 cup milk','100 gram milk'],['100 gram milk','1 cup milk']]:
            basket=BasketBuilder(FakeMatchService()).build_recipe_basket({'ingredients':lines},use_semantic=False)
            self.assertEqual(len(basket.shopping_basket),1)
            item=basket.shopping_basket[0]
            self.assertEqual(len(item.ingredients),2)
            expected=convert_quantity(canonical_quantity(1,'cup'),'gram','milk').base_quantity+100
            actual=convert_quantity(item.total_required,'gram','milk').base_quantity
            self.assertAlmostEqual(actual,expected,places=5)

    def test_unconvertible_amounts_remain_separate_not_silently_omitted(self):
        basket=BasketBuilder(FakeMatchService()).build_recipe_basket({'ingredients':['1 cup milk','2 can milk','3 can milk']},use_semantic=False)
        self.assertEqual(len(basket.shopping_basket),2)
        self.assertEqual(sum(len(item.ingredients) for item in basket.shopping_basket),3)
        counted=next(item for item in basket.shopping_basket if item.total_required.base_unit=='can')
        self.assertEqual(counted.total_required.base_quantity,5)
        self.assertIsNone(counted.checkout_cost)

    def test_household_conversions_are_reversible_for_pantry_and_packages(self):
        for name,unit,amount in [('provolone cheese','slice',4),('red onion','onion',.5),('romaine lettuce','leaf',4)]:
            mass=convert_quantity(canonical_quantity(amount,unit),'gram',name)
            self.assertAlmostEqual(convert_quantity(mass,unit,name).base_quantity,amount)
        package=parse_package_info({'original_product_name':'Provolone Cheese Slices','package_quantity':8,'package_unit':'count'})
        self.assertEqual(calculate_coverage(canonical_quantity(112,'gram'),package,'provolone cheese').packages_required,1)

    def test_fractional_and_mixed_container_counts_preserve_package_sizes(self):
        for line,ounces in [('1/2 can tomatoes 28 ounce',14),('1 1/2 can tomatoes 28 ounce',42),('1/2 28-ounce can tomatoes',14)]:
            with self.subTest(line=line):
                item=canonical_recipe_ingredients({'ingredients':[line]})[0]
                self.assertEqual(item.quantity*item.package_quantity,ounces)

    def test_mixed_pantry_units_survive_and_deplete_once(self):
        from model import pantry_quantity_buckets,pantry_adjusted_ingredient_text
        buckets=pantry_quantity_buckets([{'name':'milk','quantity':'1 cup'},{'name':'milk','quantity':'100 gram'}])
        self.assertIsNone(pantry_adjusted_ingredient_text({'name':'milk','display':'1 cup milk'},buckets,set()))
        self.assertIsNone(pantry_adjusted_ingredient_text({'name':'milk','display':'100 gram milk'},buckets,set()))
        self.assertIsNotNone(pantry_adjusted_ingredient_text({'name':'milk','display':'1 cup milk'},buckets,set()))
        buckets=pantry_quantity_buckets([{'name':'milk','quantity':'1 cup'},{'name':'milk','quantity':'2 can'}])
        self.assertIsNone(pantry_adjusted_ingredient_text({'name':'milk','display':'2 can milk'},buckets,set()))
        self.assertIsNone(pantry_adjusted_ingredient_text({'name':'milk','display':'1 cup milk'},buckets,set()))

    def test_serving_scaling_preserves_fractional_container_weight(self):
        from store_requirements import prepare_recipes
        from ingredient_normalization import parse_ingredient
        recipes,_=prepare_recipes([{'servings':4,'target_servings':2,'ingredients':['1/2 can tomatoes 28 ounce']}],[])
        parsed=parse_ingredient(recipes[0]['ingredients'][0])
        self.assertEqual((parsed.quantity,parsed.unit),(7,'ounce'))

    def test_failed_weight_conversion_does_not_claim_full_coverage(self):
        package=parse_package_info({'original_product_name':'Unknown food','raw_unit_text':'lb'})
        coverage=calculate_coverage(canonical_quantity(1,'cup'),package,'unidentified food')
        self.assertIsNone(coverage.packages_required)
        self.assertIsNone(coverage.coverage)
        self.assertIsNone(calculate_cost(coverage,parse_price_info('$4/lb')).checkout_cost)
