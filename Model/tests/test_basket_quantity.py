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


def ranked(product_id, name, confidence="high"):
    return RankedCandidate(
        product_id=product_id,
        product_name=name,
        normalized_name=name.casefold(),
        canonical_ingredient=None,
        record_status="valid_grocery_product",
        confidence=confidence,
        final_score=0.9,
        score_breakdown={},
        conflicts=[],
        warnings=[],
        reason_codes=["test"],
        exact_match=False,
        alias_match=False,
        lexical_similarity=1.0,
        semantic_similarity=1.0,
    )


def match_result(raw, candidate):
    return MatchResult(
        raw_ingredient=raw,
        parsed_ingredient={},
        normalized_ingredient_signature=raw,
        selected_match=candidate,
        compatible_alternatives=[],
        substitution_candidates=[],
        rejected_candidates=[],
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
        self.feature_by_id = {
            "milk": {
                "product_id": "milk",
                "original_product_name": "Bowl & Basket Milk 64 fl oz",
                "normalized_name": "bowl and basket milk 64 fl oz",
                "price": 4.0,
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
        }

    def match_recipe_ingredients(self, ingredients, limit=5):
        results = []
        for raw in ingredients:
            key = "milk"
            if "oil" in raw:
                key = "oil"
            elif "egg" in raw:
                key = "eggs"
            elif "beef" in raw:
                key = "beef"
            feature = self.feature_by_id[key]
            results.append(match_result(raw, ranked(key, feature["original_product_name"])))
        return results


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

    def test_merged_basket_same_product(self):
        basket = BasketBuilder(FakeMatchService()).build_recipe_basket(
            {"id": "r1", "ingredients": ["1 tbsp olive oil", "2 tbsp olive oil"]}
        )
        self.assertEqual(len(basket.shopping_basket), 1)
        item = basket.shopping_basket[0]
        self.assertEqual(item.product_id, "oil")
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
        self.assertEqual(round(basket.checkout_cost, 2), 15.0)


if __name__ == "__main__":
    unittest.main()
