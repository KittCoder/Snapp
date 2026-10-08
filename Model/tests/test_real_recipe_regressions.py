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
            "beef-stew-meat-cut",
            "beef-steak-pudding-suet",
            "beef-steak-pudding-flour",
            "beef-steak-pudding-baking-powder",
            "beef-tongue-smoked",
            "beef-steak-pie-steak",
            "beef-steak-pie-dripping",
            "corn-starch-identity",
            "corn-flour-identity",
            "chicken-hawaii-corn-flour",
            "lamb-in-pitas-minced-lamb",
            "lamb-in-pitas-fresh-mint",
            "lamb-in-pitas-pita-bread",
            "lamb-in-pitas-rocket",
            "lamb-in-pitas-sweet-chili-sauce",
        ):
            case = self.cases[case_id]
            with self.subTest(case_id=case_id):
                result = self.service.match_recipe_ingredient(case["raw_ingredient"], limit=5)
                if case.get("expect_no_safe_match") or case_id in {"beef-stew-meat-cut", "beef-steak-pudding-beef"}:
                    # A species-free or cut-free request cannot silently choose a meat cut.
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
                "ingredients": ["1 pound beef shank", "1 teaspoon baking powder"],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        self.assertIn("1 pound beef shank", by_raw)
        self.assertNotIn("sauce", by_raw["1 pound beef shank"].product_name.casefold())
        self.assertTrue(
            any(term in by_raw["1 pound beef shank"].product_name.casefold() for term in ("beef", "steak"))
        )
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

    def test_chicken_hawaii_corn_flour_uses_maseca_not_corn_starch(self):
        result = self.service.match_recipe_ingredient("corn flour", limit=10, candidate_limit=80)
        self.assertIsNotNone(result.selected_match)
        selected = result.selected_match.product_name.casefold()
        self.assertIn("maseca", selected)
        self.assertIn("masa flour", selected)
        self.assertNotIn("starch", selected)

    def test_dishes_api_path_keeps_beef_purchase_rows(self):
        import model

        recipe = {
            "id": "beef-steak-pudding-regression",
            "title": "Beef Steak Pudding",
            "extendedIngredients": [
                {"name": "beef shank", "original": "1 pound beef shank"},
                {"name": "flour", "original": "3/4 pound flour"},
                {"name": "water", "original": "3/4 cup water"},
                {"name": "baking powder", "original": "1 teaspoon baking powder"},
            ],
        }
        matches = model.match_recipe_ingredients_to_morton_williams(recipe, pantry_items=[], servings=4)
        product_names = [product["product_name"].casefold() for _ingredient, product in matches]
        self.assertTrue(any("beef" in name or "steak" in name for name in product_names), product_names)
        self.assertFalse(any("water" in name for name in product_names), product_names)

    def test_dishes_api_path_abstains_for_species_free_stew_meat(self):
        import model

        recipe = {
            "id": "slow-cooker-beef-stew-regression",
            "title": "Slow Cooker Beef Stew",
            "extendedIngredients": [
                {"name": "stew meat", "original": "2 pounds stew meat, cut into 1-inch cubes"},
                {"name": "carrots", "original": "3 medium carrots, sliced"},
                {"name": "water", "original": "2 cups water"},
            ],
        }
        matches = model.match_recipe_ingredients_to_morton_williams(recipe, pantry_items=[], servings=4)
        product_names = [product["product_name"].casefold() for _ingredient, product in matches]
        self.assertFalse(
            any("beef" in name or "lamb" in name or "pork" in name for name in product_names),
            product_names,
        )
        self.assertFalse(any("soup" in name or "burrito" in name for name in product_names), product_names)

    def test_beef_shank_soup_keeps_raw_beef_and_carrots_distinct_from_juice(self):
        basket = self.builder.build_recipe_basket(
            {
                "id": "beef-shank-barley-soup-regression",
                "ingredients": [
                    "2 pound beef, shank",
                    "1/3 cup julienne carrots",
                    "2 cup water",
                    "1/3 cup onions, chopped",
                ],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        self.assertIn("2 pound beef, shank", by_raw)
        beef_name = by_raw["2 pound beef, shank"].product_name.casefold()
        self.assertIn("beef", beef_name)
        self.assertNotIn("frank", beef_name)
        self.assertNotIn("roast beef", beef_name)
        self.assertIn("1/3 cup julienne carrots", by_raw)
        carrot_name = by_raw["1/3 cup julienne carrots"].product_name.casefold()
        self.assertIn("carrot", carrot_name)
        self.assertNotIn("juice", carrot_name)

    def test_beef_pot_roast_keeps_raw_beef_roast_requirement(self):
        basket = self.builder.build_recipe_basket(
            {
                "id": "beef-pot-roast-regression",
                "ingredients": [
                    "1/16 cup orange juice",
                    "1/2 cup onion, chopped",
                    "2 1/2 pounds boneless lean beef chuck roast",
                ],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        self.assertIn("1/16 cup orange juice", by_raw)
        self.assertIn("juice", by_raw["1/16 cup orange juice"].product_name.casefold())
        self.assertIn("2 1/2 pounds boneless lean beef chuck roast", by_raw)
        beef_name = by_raw["2 1/2 pounds boneless lean beef chuck roast"].product_name.casefold()
        self.assertIn("beef", beef_name)
        self.assertNotIn("roast beef", beef_name)
        self.assertNotIn("frank", beef_name)

    def test_beef_and_broccoli_buys_raw_cut_beef_not_prepared_entree(self):
        basket = self.builder.build_recipe_basket(
            {
                "id": "beef-and-broccoli-regression",
                "ingredients": [
                    "1/2 lb Beef sirloin, cut into strips",
                    "1 cup Broccoli Pieces",
                    "1 Tbsp Corn starch",
                ],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        self.assertIn("1/2 lb Beef sirloin, cut into strips", by_raw)
        beef_item = by_raw["1/2 lb Beef sirloin, cut into strips"]
        beef_name = beef_item.product_name.casefold()
        self.assertTrue(any(term in beef_name for term in ("beef", "steak")))
        self.assertNotIn("broccoli frozen", beef_name)
        self.assertNotIn("entree", beef_name)
        self.assertNotIn("entrée", beef_name)
        self.assertEqual(round(beef_item.total_required.base_quantity, 1), 226.8)
        self.assertGreater(beef_item.checkout_cost or 0, 0)

    def test_beef_shank_recipe_buys_two_pounds_of_shank(self):
        basket = self.builder.build_recipe_basket(
            {
                "id": "crosscut-beef-shank-stew-regression",
                "ingredients": [
                    "2 pound beef shank, (cut in 2-inch pieces)",
                    "1 cup cooked tomatoes",
                    "1 onion",
                ],
            },
            optimization_mode="balanced",
        )
        by_raw = {
            raw: item
            for item in basket.shopping_basket
            for raw in item.ingredients
        }
        self.assertIn("2 pound beef shank, (cut in 2-inch pieces)", by_raw)
        item = by_raw["2 pound beef shank, (cut in 2-inch pieces)"]
        self.assertIn("shank", item.product_name.casefold())
        self.assertEqual(round(item.total_required.base_quantity, 1), 907.2)
        self.assertEqual(item.packages_required, 2)
