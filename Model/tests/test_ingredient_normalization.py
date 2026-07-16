import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingredient_normalization import (  # noqa: E402
    PROBABLE_PRODUCT,
    SCRAPER_NOISE,
    VALID_PRODUCT,
    apply_alias,
    classify_product_record,
    extract_product_features,
    normalize_text,
    parse_ingredient,
    parse_package_size,
    validate_package_parse,
)


class IngredientParserTests(unittest.TestCase):
    def test_quantity_unicode_fraction_and_unit(self):
        parsed = parse_ingredient("1 \u00bd lbs. potatoes")
        self.assertEqual(parsed.quantity, 1.5)
        self.assertEqual(parsed.unit, "pound")
        self.assertEqual(parsed.canonical_name, "potatoes")

    def test_quantity_range(self):
        parsed = parse_ingredient("1-2 cups milk")
        self.assertEqual(parsed.quantity_min, 1)
        self.assertEqual(parsed.quantity_max, 2)
        self.assertEqual(parsed.unit, "cup")

    def test_aliases(self):
        self.assertEqual(apply_alias("AP flour"), "all-purpose flour")
        self.assertEqual(apply_alias("plain flour"), "all-purpose flour")
        self.assertEqual(apply_alias("confectioners sugar"), "powdered sugar")
        self.assertEqual(apply_alias("scallions"), "green onions")

    def test_preparation_terms_are_separated(self):
        parsed = parse_ingredient("2 cups reduced-fat shredded mozzarella cheese, divided")
        self.assertEqual(parsed.quantity, 2)
        self.assertEqual(parsed.unit, "cup")
        self.assertEqual(parsed.canonical_name, "mozzarella cheese")
        self.assertEqual(parsed.form, "shredded")
        self.assertEqual(parsed.fat_level, "reduced-fat")
        self.assertEqual(parsed.preparation, ["divided"])

    def test_meaningful_modifiers(self):
        cases = {
            "low-fat milk": ("milk", "low-fat", None, None, None),
            "whole milk": ("milk", "whole", None, None, None),
            "unsalted butter": ("butter", None, "unsalted", None, None),
            "salted butter": ("butter", None, "salted", None, None),
            "fresh parsley": ("parsley", None, None, "fresh", None),
            "dried parsley": ("parsley", None, None, "dried", None),
            "2% milk": ("milk", "2 percent", None, None, None),
            "heavy cream": ("cream", "heavy", None, None, None),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                parsed = parse_ingredient(raw)
                self.assertEqual(
                    (
                        parsed.canonical_name,
                        parsed.fat_level,
                        parsed.salted_status,
                        parsed.freshness,
                        parsed.form,
                    ),
                    expected,
                )

    def test_identity_phrases_survive(self):
        for raw in ["ground beef", "all-purpose flour", "tomato paste", "baking powder"]:
            with self.subTest(raw=raw):
                self.assertEqual(parse_ingredient(raw).canonical_name, raw)

    def test_branded_optional_alternative(self):
        parsed = parse_ingredient("1 cup King Arthur brand AP flour, optional or plain flour")
        self.assertEqual(parsed.brand, "King Arthur")
        self.assertEqual(parsed.canonical_name, "all-purpose flour")
        self.assertTrue(parsed.optional)
        self.assertEqual(parsed.alternatives, ["plain flour"])


class ProductFeatureTests(unittest.TestCase):
    def test_product_name_normalization(self):
        self.assertEqual(normalize_text("Seagram\u2019s 2% Milk"), "seagrams 2 percent milk")

    def test_package_size_extraction(self):
        self.assertEqual(parse_package_size("1 lb"), (1.0, "pound", 453.592, "gram"))
        self.assertEqual(parse_package_size("12 fl oz"), (12.0, "fluid ounce", 354.882, "milliliter"))
        self.assertEqual(parse_package_size("12.98 oz"), (12.98, "ounce", 367.977, "gram"))
        self.assertEqual(parse_package_size("25.3oz bottle"), (25.3, "ounce", 717.242, "gram"))
        confidence, source, warnings = validate_package_parse(253.0, "ounce", "253 oz", "Extra Virgin Olive Oil")
        self.assertEqual(confidence, "low")
        self.assertIn("large ounce package should be verified before optimization", warnings)

    def test_attribute_extraction(self):
        product = {
            "name": "Organic Low-Fat Milk",
            "price": "$4.99",
            "unit": "32 fl oz",
            "source": "mortonwilliams-page",
        }
        features = extract_product_features(product, 1)
        self.assertEqual(features["normalized_name"], "organic low-fat milk")
        self.assertEqual(features["canonical_name"], "milk")
        self.assertEqual(features["category"], "dairy")
        self.assertEqual(features["fat_level"], "low-fat")
        self.assertEqual(features["dietary_attributes"], ["organic"])
        self.assertEqual(features["package_unit"], "fluid ounce")
        self.assertEqual(features["base_unit"], "milliliter")

    def test_product_regressions(self):
        cases = {
            "Unsalted Butter 8 oz": ("butter", "unsalted", None),
            "Salted Butter 8 oz": ("butter", "salted", None),
            "Ground Beef 1 lb": ("ground beef", None, "ground"),
            "Tomato Paste 6 oz": ("tomato paste", None, "paste"),
            "Baking Powder 8 oz": ("baking powder", None, None),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                features = extract_product_features({"name": name, "unit": ""}, 1)
                self.assertEqual(
                    (features["canonical_name"], features["salted_status"], features["form"]),
                    expected,
                )

    def test_scraper_noise_rejected(self):
        product = {
            "name": "The cost is",
            "price": "$5.00",
            "unit": "",
            "source": "mortonwilliams-page",
        }
        features = extract_product_features(product, 0)
        self.assertEqual(features["record_status"], SCRAPER_NOISE)
        self.assertFalse(features["eligible_for_retrieval"])
        self.assertIn("scraper/navigation/description noise", features["exclusion_reasons"])

    def test_real_product_remains_valid(self):
        features = extract_product_features(
            {
                "name": "Chicken Breast",
                "price": "$3.99",
                "unit": "lb",
                "source": "mortonwilliams-pdf",
            },
            1,
        )
        self.assertEqual(features["record_status"], PROBABLE_PRODUCT)
        self.assertTrue(features["eligible_for_retrieval"])
        self.assertEqual(features["canonical_name"], "chicken breast")

    def test_branded_product_without_canonical_is_eligible(self):
        features = extract_product_features(
            {
                "name": "Bowl & Basket Specialty Crackers",
                "price": "$3.99",
                "unit": "7 oz",
                "source": "mortonwilliams-storefront",
            },
            2,
        )
        self.assertEqual(features["record_status"], VALID_PRODUCT)
        self.assertTrue(features["eligible_for_retrieval"])
        self.assertIsNone(features["canonical_name"])
        self.assertEqual(features["brand"], "Bowl And Basket")

    def test_uncertain_canonical_does_not_make_invalid(self):
        features = extract_product_features(
            {
                "name": "Sparkling Water",
                "price": "$4.99",
                "unit": "8 pack",
                "source": "mortonwilliams-pdf",
            },
            3,
        )
        self.assertEqual(features["record_status"], PROBABLE_PRODUCT)
        self.assertTrue(features["eligible_for_retrieval"])
        self.assertIsNone(features["canonical_name"])
        self.assertIn("canonical ingredient not assigned", features["uncertainty_reasons"])


if __name__ == "__main__":
    unittest.main()
