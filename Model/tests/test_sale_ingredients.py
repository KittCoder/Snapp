import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import model  # noqa: E402


def product(name, price="$4.99", original="$7.99", sale=True, unit="1 lb"):
    return {
        "name": name,
        "price": price,
        "original_price": original,
        "sale_price": price,
        "unit": unit,
        "is_on_sale": sale,
        "source": "mortonwilliams-storefront",
        "notes": "fixture",
    }


def recipe(recipe_id, name, ingredients):
    return {
        "id": recipe_id,
        "name": name,
        "ingredients": [
            {"name": ingredient, "raw": f"1 cup {ingredient}"}
            for ingredient in ingredients
        ],
    }


class SaleIngredientTests(unittest.TestCase):
    def setUp(self):
        model.sale_ingredient_pool_cache = None
        model.sale_candidate_artifact_cache = None
        model.sale_recipe_index_cache = None

    def tearDown(self):
        model.sale_ingredient_pool_cache = None
        model.sale_candidate_artifact_cache = None
        model.sale_recipe_index_cache = None

    def patch_recipes(self, recipes):
        return mock.patch.object(model, "load_all_recipes_db", return_value=recipes)

    def test_discount_calculation_rejects_bad_prices(self):
        discount = model.trusted_discount("$10.00", "$6.00")
        self.assertEqual(discount["discount_percent"], 0.4)
        self.assertEqual(discount["absolute_savings"], 4.0)
        self.assertIsNone(model.trusted_discount("", "$6.00"))
        self.assertIsNone(model.trusted_discount("$10.00", ""))
        self.assertIsNone(model.trusted_discount("$10.00", "$10.00"))
        self.assertIsNone(model.trusted_discount("$10.00", "$12.00"))
        self.assertIsNone(model.trusted_discount("$100.00", "$1.00"))

    def test_duplicate_ingredient_types_keep_best_offer(self):
        recipes = [recipe(str(index), f"Chicken Recipe {index}", ["chicken breast"]) for index in range(4)]
        grocery_db = {
            "products": [
                product("Chicken Breast Family Pack", "$7.99", "$9.99"),
                product("Chicken Breast Value Pack", "$4.99", "$9.99"),
            ]
        }
        with self.patch_recipes(recipes):
            candidates = model.build_sale_ingredient_pool(grocery_db)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["product_name"], "Chicken Breast Value Pack")

    def test_excludes_non_ingredient_products_and_recipe_poor_items(self):
        recipes = [recipe(str(index), f"Tomato Recipe {index}", ["tomatoes"]) for index in range(3)]
        grocery_db = {
            "products": [
                product("Laundry Detergent Fresh Lavender", "$5.99", "$10.49"),
                product("Tomatoes", "$3.50", "$5.49"),
                product("Dragon Fruit", "$2.99", "$4.99"),
            ]
        }
        with self.patch_recipes(recipes):
            audit = model.build_sale_ingredient_pool(grocery_db, include_diagnostics=True)
        names = [candidate["ingredient_id"] for candidate in audit["candidates"]]
        self.assertIn("tomatoes", names)
        excluded_names = " ".join(item["product_name"] for item in audit["exclusions"])
        self.assertIn("Laundry Detergent", excluded_names)
        self.assertIn("Dragon Fruit", excluded_names)

    def test_recipe_count_eligibility_requires_three(self):
        recipes = [recipe("1", "Pepper One", ["peppers"]), recipe("2", "Pepper Two", ["peppers"])]
        grocery_db = {"products": [product("Orange Peppers", "$2.99", "$4.99")]}
        with self.patch_recipes(recipes):
            candidates = model.build_sale_ingredient_pool(grocery_db)
        self.assertEqual(candidates, [])

    def test_weighted_sampling_uses_distinct_top_ten_only(self):
        candidates = [
            {"ingredient_id": f"ingredient-{index}", "score": 100 - index}
            for index in range(12)
        ]
        selected = model.weighted_sale_sample(candidates, sample_size=3, rng=mock.Mock(choices=lambda pool, weights, k: [pool[-1]]))
        self.assertEqual(len(selected), 3)
        self.assertEqual(len({item["ingredient_id"] for item in selected}), 3)
        self.assertTrue(all(int(item["ingredient_id"].split("-")[-1]) < 10 for item in selected))

    def test_recipe_use_check_is_ingredient_based(self):
        database_recipe = recipe("chicken-1", "Chicken Dinner", ["chicken breast", "rice"])
        spoonacular_recipe = model.all_recipe_to_spoonacular_recipe(database_recipe)
        self.assertTrue(model.recipe_uses_sale_ingredient(spoonacular_recipe, "chicken breast"))
        self.assertFalse(model.recipe_uses_sale_ingredient(spoonacular_recipe, "beef"))

    def test_frontend_transfers_sale_ingredient_id(self):
        app_js = Path(__file__).resolve().parents[2] / "Web" / "app.js"
        source = app_js.read_text(encoding="utf-8")
        self.assertIn("sale_ingredient_id: options.saleIngredientId", source)
        self.assertIn("params.set(\"sale_ingredient\", ingredientId)", source)

    def test_sale_endpoint_uses_artifact_and_hides_recipe_ids(self):
        artifact = {
            "candidates": [
                {
                    "ingredient_id": "tomatoes",
                    "ingredient_name": "tomatoes",
                    "product_name": "Tomatoes",
                    "sale_price": 2.99,
                    "score": 50,
                    "recipe_count": 3,
                    "recipe_ids": ["r1", "r2", "r3"],
                }
            ]
        }
        with mock.patch.object(model, "load_sale_candidate_artifact", return_value=artifact):
            with model.app.test_client() as client:
                response = client.get("/sale-ingredients")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["candidate_pool_size"], 1)
        self.assertEqual(data["sale_ingredients"][0]["ingredient_id"], "tomatoes")
        self.assertNotIn("recipe_ids", data["sale_ingredients"][0])
        self.assertEqual(model.matcher_warmup.get_warmup_status().status, "not_started")

    def test_sale_recipe_ids_can_come_from_artifact(self):
        artifact = {"candidates": [{"ingredient_id": "pork", "recipe_ids": ["p1", "p2", "p3"]}]}
        with mock.patch.object(model, "load_sale_candidate_artifact", return_value=artifact):
            with mock.patch.object(model, "sale_recipe_index", side_effect=AssertionError("slow index should not build")):
                self.assertEqual(model.recipe_ids_for_sale_ingredient("pork"), ["p1", "p2", "p3"])

    def test_fallback_when_fewer_than_three_eligible_sale_types(self):
        recipes = [recipe(str(index), f"Egg Recipe {index}", ["eggs"]) for index in range(4)]
        grocery_db = {"products": [product("Large Eggs", "$2.99", "$4.99", unit="12 ct")]}
        with self.patch_recipes(recipes):
            candidates = model.build_sale_ingredient_pool(grocery_db)
        self.assertEqual(len(candidates), 1)
        selected = model.weighted_sale_sample(candidates, sample_size=3)
        self.assertEqual(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
