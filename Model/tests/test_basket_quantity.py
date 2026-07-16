import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basket_quantity import (  # noqa: E402
    UNKNOWN,
    BasketBuilder,
    calculate_cost,
    calculate_coverage,
    canonical_quantity,
    convert_quantity,
    parse_package_info,
    parse_price_info,
)
from product_compatibility import MatchResult, RankedCandidate  # noqa: E402


def ranked(product_id, name, confidence="high", score=0.9, conflicts=None):
    return RankedCandidate(
        product_id=product_id,
        product_name=name,
        normalized_name=name.casefold(),
        canonical_ingredient=None,
        record_status="valid_grocery_product",
        confidence=confidence,
        final_score=score,
        score_breakdown={},
        conflicts=conflicts or [],
        warnings=[],
        reason_codes=["test"],
        exact_match=False,
        alias_match=False,
        lexical_similarity=1.0,
        semantic_similarity=1.0,
    )


def match_result(raw, candidate, alternatives=None, rejected=None):
    return MatchResult(
        raw_ingredient=raw,
        parsed_ingredient={},
        normalized_ingredient_signature=raw,
        selected_match=candidate,
        compatible_alternatives=alternatives or [],
        substitution_candidates=[],
        rejected_candidates=rejected or [],
        confidence=candidate.confidence,
        final_score=candidate.final_score,
        warnings=[],
        reason_codes=[],
        cache_hit=False,
        retrieval_timing_ms=0,
        reranking_timing_ms=0,
        total_timing_ms=0,
        matcher_version="test",
        product_index_version="test",
        override_version="test",
    )


class FakeMatchService:
    def __init__(self):
        self.calls = 0
        self.overrides = type("Overrides", (), {"version": "test-overrides"})()
        self.feature_by_id = {
            "milk": {
                "product_id": "milk",
                "original_product_name": "Bowl & Basket Milk 64 fl oz",
                "normalized_name": "bowl and basket milk 64 fl oz",
                "price": 4.0,
                "package_quantity": 64.0,
                "package_unit": "fluid ounce",
            },
            "whole_milk": {
                "product_id": "whole_milk",
                "original_product_name": "Whole Milk 64 fl oz",
                "normalized_name": "whole milk 64 fl oz",
                "price": 1.0,
                "package_quantity": 64.0,
                "package_unit": "fluid ounce",
            },
            "oil": {
                "product_id": "oil",
                "original_product_name": "Extra Virgin Olive Oil 16 fl oz",
                "normalized_name": "extra virgin olive oil 16 fl oz",
                "price": 8.0,
                "package_quantity": 16.0,
                "package_unit": "fluid ounce",
            },
            "oil_large": {
                "product_id": "oil_large",
                "original_product_name": "Extra Virgin Olive Oil 32 fl oz",
                "normalized_name": "extra virgin olive oil 32 fl oz",
                "price": 10.0,
                "package_quantity": 32.0,
                "package_unit": "fluid ounce",
            },
            "oil_tiny": {
                "product_id": "oil_tiny",
                "original_product_name": "Extra Virgin Olive Oil 2 fl oz",
                "normalized_name": "extra virgin olive oil 2 fl oz",
                "price": 2.0,
                "package_quantity": 2.0,
                "package_unit": "fluid ounce",
            },
            "oil_bad": {
                "product_id": "oil_bad",
                "original_product_name": "Extra Virgin Olive Oil 253 oz",
                "normalized_name": "extra virgin olive oil 253 oz",
                "price": 1.0,
                "package_quantity": 253.0,
                "package_unit": "ounce",
                "package_quantity_base": 7172.423,
                "base_unit": "gram",
                "package_parse_confidence": "low",
                "package_parse_warnings": ["large ounce package should be verified before optimization"],
            },
            "dressing": {
                "product_id": "dressing",
                "original_product_name": "Cheap Salad Dressing 64 fl oz",
                "normalized_name": "cheap salad dressing 64 fl oz",
                "price": 1.0,
                "package_quantity": 64.0,
                "package_unit": "fluid ounce",
            },
            "eggs": {
                "product_id": "eggs",
                "original_product_name": "Large Eggs 1 dozen",
                "normalized_name": "large eggs 1 dozen",
                "price": 3.0,
            },
            "beef": {
                "product_id": "beef",
                "original_product_name": "Ground Beef $8.99/lb variable weight",
                "normalized_name": "ground beef variable weight",
                "raw_price": "$8.99/lb",
            },
            "dry_milk": {
                "product_id": "dry_milk",
                "original_product_name": "Swiss Miss Nonfat Dry Milk 12.98 oz",
                "normalized_name": "swiss miss nonfat dry milk 12.98 oz",
                "price": 7.89,
                "package_quantity": 12.98,
                "package_unit": "ounce",
                "package_parse_confidence": "high",
            },
            "steak": {
                "product_id": "steak",
                "original_product_name": "Skirt Steak 1 lb",
                "normalized_name": "skirt steak 1 lb",
                "price": 12.0,
                "package_quantity": 1.0,
                "package_unit": "pound",
            },
            "shaved": {
                "product_id": "shaved",
                "original_product_name": "Shaved Steak Beef 1 lb",
                "normalized_name": "shaved steak beef 1 lb",
                "price": 1.0,
                "package_quantity": 1.0,
                "package_unit": "pound",
            },
            "unsalted": {
                "product_id": "unsalted",
                "original_product_name": "Unsalted Butter 16 oz",
                "normalized_name": "unsalted butter 16 oz",
                "price": 8.0,
                "package_quantity": 16.0,
                "package_unit": "ounce",
            },
            "salted": {
                "product_id": "salted",
                "original_product_name": "Salted Butter 16 oz",
                "normalized_name": "salted butter 16 oz",
                "price": 7.0,
                "package_quantity": 16.0,
                "package_unit": "ounce",
            },
            "fresh_parsley": {
                "product_id": "fresh_parsley",
                "original_product_name": "Fresh Parsley bunch",
                "normalized_name": "fresh parsley bunch",
                "price": 2.0,
                "package_quantity": 1.0,
                "package_unit": "bunch",
            },
            "dried_parsley": {
                "product_id": "dried_parsley",
                "original_product_name": "Parsley Flakes 1 oz",
                "normalized_name": "parsley flakes 1 oz",
                "price": 3.0,
                "package_quantity": 1.0,
                "package_unit": "ounce",
            },
        }

    def match_recipe_ingredients(self, ingredients, limit=5):
        self.calls += 1
        results = []
        for raw in ingredients:
            key = "milk"
            if "oil" in raw:
                key = "oil"
            elif "egg" in raw:
                key = "eggs"
            elif "beef" in raw:
                key = "beef"
            elif "dry milk" in raw:
                key = "dry_milk"
            elif "skirt steak" in raw:
                key = "steak"
            elif "unsalted butter" in raw:
                key = "unsalted"
            elif "salted butter" in raw:
                key = "salted"
            elif "fresh parsley" in raw:
                key = "fresh_parsley"
            elif "dried parsley" in raw:
                key = "dried_parsley"
            feature = self.feature_by_id[key]
            alternatives = []
            rejected = []
            if key == "oil":
                alternatives = [
                    ranked("oil_large", self.feature_by_id["oil_large"]["original_product_name"], score=0.88),
                    ranked("oil_tiny", self.feature_by_id["oil_tiny"]["original_product_name"], score=0.87),
                    ranked("oil_bad", self.feature_by_id["oil_bad"]["original_product_name"], score=0.86),
                ]
                rejected = [ranked("dressing", self.feature_by_id["dressing"]["original_product_name"], conflicts=[{"rule": "oil_identity", "classification": "hard_reject", "message": "dressing is not oil"}])]
            if key == "milk":
                rejected = [ranked("whole_milk", self.feature_by_id["whole_milk"]["original_product_name"], conflicts=[{"rule": "milk_fat_level", "classification": "hard_reject", "message": "whole does not satisfy fat-free"}])]
            if key == "steak":
                rejected = [ranked("shaved", self.feature_by_id["shaved"]["original_product_name"], conflicts=[{"rule": "meat_cut", "classification": "hard_reject", "message": "meat cut differs"}])]
            results.append(match_result(raw, ranked(key, feature["original_product_name"]), alternatives, rejected))
        return results

    def product_index_version(self):
        return "test-index"


class QuantityEngineTests(unittest.TestCase):
    def test_unit_conversions(self):
        self.assertEqual(canonical_quantity(1, "kg").base_quantity, 1000)
        self.assertAlmostEqual(canonical_quantity(2, "cup").base_quantity, 473.176, places=3)
        self.assertEqual(canonical_quantity(3, "egg").base_unit, "egg")

    def test_unknown_volume_to_mass_without_density(self):
        converted = convert_quantity(canonical_quantity(1, "cup"), "gram", "flour")
        self.assertEqual(converted.status, UNKNOWN)
        self.assertEqual(converted.reason, "unsafe conversion")

    def test_density_conversion_when_explicit(self):
        converted = convert_quantity(canonical_quantity(1, "cup"), "gram", "milk")
        self.assertAlmostEqual(converted.quantity, 243.7, places=1)

    def test_package_parsing(self):
        package = parse_package_info({"original_product_name": "Soda 12 x 12 oz cans"})
        self.assertEqual(package.package_count, 12)
        self.assertEqual(package.package_quantity, 12)
        self.assertEqual(package.package_unit, "ounce")
        self.assertAlmostEqual(package.base_quantity, 4082.328, places=3)
        self.assertEqual(parse_package_info({"original_product_name": "Large Eggs 1 dozen"}).base_quantity, 12)
        self.assertEqual(parse_package_info({"original_product_name": "Avocados 4 ct"}).base_quantity, 4)
        self.assertEqual(parse_package_info({"original_product_name": "Broth 2 pack"}).base_quantity, 2)
        self.assertTrue(parse_package_info({"original_product_name": "Family Pack Chicken variable weight"}).variable_weight)

    def test_low_confidence_package_metadata_excluded(self):
        package = parse_package_info(
            {
                "original_product_name": "Extra Virgin Olive Oil",
                "raw_unit_text": "253 oz",
                "package_quantity": 253.0,
                "package_unit": "ounce",
                "package_quantity_base": 7172.423,
                "base_unit": "gram",
                "package_parse_confidence": "low",
                "package_parse_warnings": ["large ounce package should be verified before optimization"],
            }
        )
        self.assertFalse(package.eligible_for_optimization)
        coverage = calculate_coverage(canonical_quantity(2, "tablespoon", "olive oil"), package, "olive oil")
        self.assertIsNone(coverage.packages_required)
        self.assertIn("package metadata excluded from optimization", coverage.warnings)

    def test_coverage_leftovers(self):
        required = canonical_quantity(2, "cup", "milk")
        package = parse_package_info({"package_quantity": 64, "package_unit": "fluid ounce"})
        coverage = calculate_coverage(required, package, "milk")
        self.assertEqual(coverage.packages_required, 1)
        self.assertAlmostEqual(coverage.used.quantity, 16.0, places=1)
        self.assertAlmostEqual(coverage.leftover.quantity, 48.0, places=1)
        self.assertEqual(coverage.coverage, 1.0)

    def test_sale_pricing_and_effective_cost(self):
        price = parse_price_info("2 for $5")
        coverage = calculate_coverage(canonical_quantity(20, "fluid ounce"), parse_package_info({"package_quantity": 16, "package_unit": "fluid ounce"}))
        cost = calculate_cost(coverage, price)
        self.assertEqual(coverage.packages_required, 2)
        self.assertEqual(cost.checkout_cost, 5.0)
        self.assertAlmostEqual(cost.effective_ingredient_cost, 3.13, places=2)
        bogo = parse_price_info("Buy One Get One $4.00")
        self.assertTrue(bogo.bogo)
        self.assertEqual(bogo.unit_price, 2.0)

    def test_weight_pricing(self):
        package = parse_package_info({"original_product_name": "Ground Beef $8.99/lb variable weight"})
        price = parse_price_info("$8.99/lb")
        coverage = calculate_coverage(canonical_quantity(1.5, "pound"), package)
        cost = calculate_cost(coverage, price)
        self.assertEqual(cost.checkout_cost, 13.49)
        self.assertEqual(parse_price_info("$1.29 per lb").price_unit, "pound")

    def test_variable_weight_volume_requirement_does_not_become_package_count(self):
        package = parse_package_info({"original_product_name": "Green Onions Package per lb"})
        price = parse_price_info("$1.29 per lb")
        coverage = calculate_coverage(canonical_quantity(1, "cup"), package, "green onion")
        cost = calculate_cost(coverage, price)
        self.assertIsNone(cost.checkout_cost)
        self.assertIn("unknown conversions", cost.warnings)

    def test_merged_basket_same_product(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"id": "r1", "ingredients": ["1 tbsp olive oil", "2 tbsp olive oil"]}
        )
        self.assertEqual(len(basket.shopping_basket), 1)
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "oil_tiny")
        self.assertEqual(item.packages_required, 1)
        self.assertEqual(len(item.ingredients), 2)

    def test_multi_recipe_basket(self):
        basket = BasketBuilder(FakeMatchService()).build_multi_recipe_basket(
            [
                {"id": "a", "ingredients": ["1 cup milk", "2 eggs"]},
                {"id": "b", "ingredients": ["1 cup milk", "1 tbsp olive oil"]},
            ]
        )
        items = {item.product_id: item for item in basket.shopping_basket}
        self.assertEqual(items["milk"].packages_required, 1)
        self.assertEqual(items["eggs"].packages_required, 1)
        self.assertEqual(round(basket.checkout_cost, 2), 9.0)

    def test_identical_basket_request_uses_complete_cache(self):
        fake = FakeMatchService()
        builder = BasketBuilder(fake)
        recipe = {"id": "a", "ingredients": ["1 cup milk", "2 eggs"]}
        first = builder.build_recipe_basket(recipe)
        second = builder.build_recipe_basket(recipe)
        self.assertEqual(first.checkout_cost, second.checkout_cost)
        self.assertEqual(fake.calls, 1)

    def test_cheaper_incompatible_product_never_wins(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket({"ingredients": ["1 tbsp olive oil"]})
        self.assertNotEqual(basket.shopping_basket[0].product_id, "dressing")
        rejected_ids = {item.product_id for item in basket.shopping_basket[0].optimized_purchase.rejected}
        self.assertIn("dressing", rejected_ids)

    def test_larger_package_can_beat_multiple_small_packages(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"ingredients": ["20 fl oz olive oil"]},
            optimization_mode="lowest_checkout_cost",
        )
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "oil_large")
        self.assertEqual(item.packages_required, 1)
        self.assertTrue(item.optimized_purchase.changed_from_matcher_top1)

    def test_smaller_package_can_win_when_cheaper_and_less_waste(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"ingredients": ["1 tbsp olive oil"]},
            optimization_mode="balanced",
        )
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "oil_tiny")
        self.assertLess(item.checkout_cost, 8.0)

    def test_aggregation_changes_package_choice(self):
        basket = BasketBuilder(FakeMatchService()).build_multi_recipe_basket(
            [{"ingredients": ["10 fl oz olive oil"]}, {"ingredients": ["10 fl oz olive oil"]}],
            optimization_mode="lowest_checkout_cost",
        )
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "oil_large")
        self.assertEqual(len(item.ingredients), 2)

    def test_low_confidence_package_does_not_win(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"ingredients": ["1 tbsp olive oil"]},
            optimization_mode="lowest_checkout_cost",
        )
        item = basket.shopping_basket[0]
        self.assertNotEqual(item.product_id, "oil_bad")
        rejected_ids = {candidate.product_id for candidate in item.optimized_purchase.rejected}
        self.assertIn("oil_bad", rejected_ids)

    def test_corrected_dry_milk_metadata_usable(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket({"ingredients": ["1 oz dry milk"]})
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "dry_milk")
        self.assertEqual(item.package.confidence, "high")
        self.assertEqual(item.packages_required, 1)

    def test_nonfat_milk_does_not_optimize_to_whole_milk(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket({"ingredients": ["1 cup non-fat milk"]})
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "milk")
        self.assertIn("whole_milk", {candidate.product_id for candidate in item.optimized_purchase.rejected})

    def test_skirt_steak_does_not_optimize_to_shaved_steak(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket({"ingredients": ["1 lb skirt steak"]})
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "steak")
        self.assertIn("shaved", {candidate.product_id for candidate in item.optimized_purchase.rejected})

    def test_materially_different_ingredients_are_not_aggregated(self):
        basket = BasketBuilder(FakeMatchService()).build_multi_recipe_basket(
            [{"ingredients": ["1 tbsp unsalted butter", "1 tbsp salted butter", "1 bunch fresh parsley", "1 oz dried parsley"]}]
        )
        ids = {item.product_id for item in basket.shopping_basket}
        self.assertTrue({"unsalted", "salted", "fresh_parsley", "dried_parsley"} <= ids)
        self.assertEqual(len(basket.shopping_basket), 4)

    def test_variable_weight_products_return_estimated_costs(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket({"ingredients": ["1.5 lb ground beef"]})
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "beef")
        self.assertEqual(item.checkout_cost, 13.49)
        self.assertTrue(item.package.variable_weight)

    def test_matcher_top1_retained_without_material_improvement(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"ingredients": ["15 fl oz olive oil"]},
            optimization_mode="balanced",
        )
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "oil")
        self.assertFalse(item.optimized_purchase.changed_from_matcher_top1)

    def test_optimization_explains_changed_product(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"ingredients": ["20 fl oz olive oil"]},
            optimization_mode="lowest_checkout_cost",
        )
        item = basket.shopping_basket[0]
        self.assertIn("lowers checkout", item.optimized_purchase.explanation)


if __name__ == "__main__":
    unittest.main()
