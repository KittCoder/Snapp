import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basket_quantity import get_basket_builder  # noqa: E402
from model import should_buy_recipe_ingredient  # noqa: E402
from product_compatibility import get_product_match_service  # noqa: E402


FIXTURE = Path(__file__).resolve().parents[1] / "evaluation" / "real_recipe_match_regression_cases.jsonl"


def load_cases():
    with FIXTURE.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


class RealRecipeRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case["id"]: case for case in load_cases()}
        cls.service = get_product_match_service()
        cls.builder = get_basket_builder()
        cls.service.cache.clear()
        cls.builder.clear_caches()

    def assert_text_patterns(self, text, acceptable, unacceptable):
        lowered = text.casefold()
        if acceptable:
            self.assertTrue(any(pattern.casefold() in lowered for pattern in acceptable), lowered)
        for pattern in unacceptable:
            self.assertNotIn(pattern.casefold(), lowered)

    def test_beef_steak_pudding_matcher_cases(self):
        for case_id in (
            "beef-steak-pudding-beef",
            "beef-steak-pudding-suet",
            "beef-steak-pudding-flour",
            "beef-steak-pudding-baking-powder",
            "beef-tongue-smoked",
            "beef-steak-pie-steak",
            "beef-steak-pie-dripping",
            "corn-starch-identity",
            "corn-flour-identity",
            "lamb-in-pitas-minced-lamb",
            "lamb-in-pitas-fresh-mint",
            "lamb-in-pitas-pita-bread",
            "lamb-in-pitas-rocket",
            "lamb-in-pitas-sweet-chili-sauce",
        ):
            case = self.cases[case_id]
            with self.subTest(case_id=case_id):
                result = self.service.match_recipe_ingredient(case["raw_ingredient"], limit=5)
                if case.get("expect_no_safe_match"):
                    self.assertIsNone(result.selected_match)
                    continue
                self.assertIsNotNone(result.selected_match)
                selected_text = " ".join(
                    str(value or "")
                    for value in (
                        result.selected_match.product_name,
                        result.selected_match.normalized_name,
                        result.selected_match.canonical_ingredient,
                    )
                )
                self.assert_text_patterns(
                    selected_text,
                    case.get("acceptable_patterns") or [],
                    case.get("unacceptable_patterns") or [],
                )

    def test_beef_steak_pudding_water_is_not_purchased(self):
        case = self.cases["beef-steak-pudding-water"]
        self.assertFalse(
            should_buy_recipe_ingredient(
                {
                    "name": "water",
                    "measure": case["raw_ingredient"],
                    "display": case["raw_ingredient"],
                }
            )
        )

    def test_beef_steak_pudding_basket_does_not_buy_sauce_for_beef(self):
        basket = self.builder.build_recipe_basket(
            {
                "id": "beef-steak-pudding-regression",
                "ingredients": ["1 pound beef", "1 teaspoon baking powder"],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        self.assertIn("1 pound beef", by_raw)
        self.assertNotIn("sauce", by_raw["1 pound beef"].product_name.casefold())
        self.assertIn("beef", by_raw["1 pound beef"].product_name.casefold())
        self.assertIn("1 teaspoon baking powder", by_raw)
        self.assertNotEqual(by_raw["1 teaspoon baking powder"].package.package_quantity, 81.0)

    def test_lamb_in_pitas_core_ingredients_match_real_inventory(self):
        basket = self.builder.build_recipe_basket(
            {
                "id": "lamb-in-pitas-regression",
                "ingredients": [
                    "1 pound minced lamb",
                    "1 tablespoon fresh mint, chopped",
                    "1 small onion, finely chopped",
                    "1 garlic clove, crushed",
                    "1 tablespoon sweet chili sauce",
                    "1 tub hummus",
                    "4 whole meal pita breads",
                    "25 gram rockets",
                ],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        expected = {
            "1 pound minced lamb": "lamb",
            "1 tablespoon fresh mint, chopped": "mint",
            "1 tablespoon sweet chili sauce": "chili",
            "1 tub hummus": "hummus",
            "4 whole meal pita breads": "pita bread",
            "25 gram rockets": "arugula",
        }
        for raw, expected_text in expected.items():
            with self.subTest(raw=raw):
                self.assertIn(raw, by_raw)
                self.assertIn(expected_text, by_raw[raw].product_name.casefold())
        self.assertNotIn("dog food", by_raw["1 pound minced lamb"].product_name.casefold())
        self.assertNotIn("chips", by_raw["4 whole meal pita breads"].product_name.casefold())
