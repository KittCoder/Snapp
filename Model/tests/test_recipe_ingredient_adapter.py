import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recipe_ingredient_adapter import canonical_ingredient_from_structured, canonical_ingredient_from_text  # noqa: E402


class RecipeIngredientAdapterTests(unittest.TestCase):
    def test_structured_quantity_and_unit_are_trusted(self):
        ingredient = canonical_ingredient_from_structured(
            {
                "quantity": "1 1/2",
                "unit": "cups",
                "name": "cooked, shredded chicken",
                "note": "divided",
                "raw": "1 1/2 cups cooked, shredded chicken, divided",
            }
        )
        self.assertEqual(ingredient.quantity, 1.5)
        self.assertEqual(ingredient.unit, "cup")
        self.assertEqual(ingredient.ingredient_name, "cooked, shredded chicken")
        self.assertEqual(ingredient.parser_provenance["quantity"], "source.quantity")

    def test_package_descriptor_is_separated_from_identity(self):
        ingredient = canonical_ingredient_from_text("one 14.5-ounce can diced tomatoes, drained")
        self.assertEqual(ingredient.quantity, 1)
        self.assertEqual(ingredient.unit, "can")
        self.assertEqual(ingredient.package_quantity, 14.5)
        self.assertEqual(ingredient.package_unit, "ounce")
        self.assertIn("tomatoes diced", ingredient.matcher_text)

    def test_structured_package_note_does_not_pollute_matcher_text(self):
        ingredient = canonical_ingredient_from_structured(
            {
                "quantity": "1",
                "unit": "can",
                "name": "whole corn",
                "note": "15.2 ounce, or any low-sodium canned vegetable, drained",
                "raw": "1 can whole corn 15.2 ounce, or any low-sodium canned vegetable, drained",
            }
        )
        self.assertEqual(ingredient.quantity, 1)
        self.assertEqual(ingredient.unit, "can")
        self.assertEqual(ingredient.ingredient_name, "whole corn")
        self.assertNotIn("15.2", ingredient.matcher_text)
        self.assertNotIn("low-sodium canned vegetable", ingredient.matcher_text)


if __name__ == "__main__":
    unittest.main()
