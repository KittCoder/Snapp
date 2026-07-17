import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from product_compatibility import (  # noqa: E402
    EXACT,
    HARD_REJECT,
    NO_SAFE_MATCH,
    OverrideStore,
    ProductMatchService,
    compatibility_signals,
    profile_from_feature,
    profile_from_query,
)
from product_retrieval import Candidate, CandidateRetrievalResult  # noqa: E402


def feature(product_id, name, canonical=None, category=None, **kwargs):
    return {
        "product_id": product_id,
        "original_product_name": name,
        "normalized_name": name.casefold().replace("&", "and"),
        "canonical_name": canonical,
        "category": category,
        "record_status": kwargs.get("record_status", "valid_grocery_product"),
        "eligible_for_retrieval": kwargs.get("eligible", True),
        "source_quality_score": kwargs.get("source_quality_score", 95),
        "brand": kwargs.get("brand"),
        "fat_level": kwargs.get("fat_level"),
        "salted_status": kwargs.get("salted_status"),
        "freshness": kwargs.get("freshness"),
        "form": kwargs.get("form"),
        "dietary_attributes": kwargs.get("dietary_attributes", []),
    }


class FakeRetriever:
    def __init__(self, features):
        self.features = features
        self._index_metadata = {"index_version": "fake-index-v1"}
        self.index_dir = Path("/tmp/missing-index")
        self.calls = 0

    def retrieve_product_candidates(self, ingredient_text, limit=50):
        self.calls += 1
        candidates = [
            Candidate(
                product_id=item["product_id"],
                original_product_name=item["original_product_name"],
                normalized_name=item["normalized_name"],
                record_status=item["record_status"],
                canonical_ingredient=item.get("canonical_name"),
                lexical_similarity=item.get("lexical", 0.7),
                semantic_similarity=item.get("semantic", 0.7),
                exact_match=item.get("exact", False),
                category_match_signal="match",
                retrieval_reason_codes=["test"],
            )
            for item in self.features
        ]
        return CandidateRetrievalResult(
            ingredient_text=ingredient_text,
            parsed_query={},
            normalized_semantic_query=ingredient_text,
            candidates=candidates[:limit],
            retrieval_latency_ms=1.0,
            lexical_latency_ms=0.1,
            semantic_latency_ms=0.1,
            query_embedding_latency_ms=0.1,
            embedding_index_available=True,
            embedding_model_version="fake",
            index_version="fake-index-v1",
            degraded_mode=False,
            errors=[],
        )


def service(features, override_data=None):
    if override_data is None:
        overrides = OverrideStore(Path("/tmp/definitely-missing-overrides.json"))
    else:
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        json.dump(override_data, temp)
        temp.close()
        overrides = OverrideStore(Path(temp.name))
    return ProductMatchService(retriever=FakeRetriever(features), overrides=overrides)


class CompatibilityRuleTests(unittest.TestCase):
    def test_low_fat_milk_rejects_unsafe_milks(self):
        svc = service(
            [
                feature("oat", "Oatmilk", "milk", "dairy"),
                feature("coconut", "Coconut Milk", "milk", "dairy"),
                feature("evap", "Evaporated Milk", "milk", "dairy"),
                feature("fatfree", "Lactaid Fat Free Milk", "milk", "dairy"),
                feature("lowfat", "Lactaid One Percent Lowfat Milk", "milk", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("low-fat milk")
        self.assertEqual(result.selected_match.product_id, "lowfat")
        rejected_ids = {item.product_id for item in result.rejected_candidates}
        self.assertTrue({"oat", "coconut", "evap", "fatfree"} <= rejected_ids)

    def test_unsalted_butter_prefers_unsalted_over_spread(self):
        svc = service(
            [
                feature("spread", "Spreadable Butter", "butter", "dairy"),
                feature("salted", "Kerrygold Salted Butter", "butter", "dairy", salted_status="salted"),
                feature("unsalted", "Breakstone's Unsalted Butter", "butter", "dairy", salted_status="unsalted"),
            ]
        )
        self.assertEqual(svc.match_recipe_ingredient("unsalted butter").selected_match.product_id, "unsalted")

    def test_chicken_broth_rejects_breast_and_soup(self):
        svc = service(
            [
                feature("breast", "Chicken Breast", "chicken breast", "meat"),
                feature("soup", "Cream of Chicken Soup", "soup", "pantry"),
                feature("broth", "Campbell's Chicken Broth", "broth", "pantry"),
            ]
        )
        result = svc.match_recipe_ingredient("chicken broth")
        self.assertEqual(result.selected_match.product_id, "broth")
        self.assertTrue({"breast", "soup"} <= {item.product_id for item in result.rejected_candidates})

    def test_fresh_parsley_does_not_silently_select_dried(self):
        svc = service(
            [
                feature("flakes", "Parsley Flakes", "parsley", "produce"),
                feature("fresh", "Plain Parsley", "parsley", "produce", freshness="fresh"),
            ]
        )
        result = svc.match_recipe_ingredient("fresh parsley")
        self.assertEqual(result.selected_match.product_id, "fresh")
        self.assertIn("flakes", {item.product_id for item in result.substitution_candidates})

    def test_required_regressions(self):
        cases = [
            ("ground beef", "ground", ["steak"], [feature("steak", "Ribeye Steak", "beef", "meat"), feature("ground", "Ground Beef Chuck", "ground beef", "meat")]),
            ("baking powder", "powder", ["soda"], [feature("soda", "Baking Soda", "baking soda", "pantry"), feature("powder", "Baking Powder", "baking powder", "pantry")]),
            ("tomato paste", "paste", ["sauce"], [feature("sauce", "Tomato Sauce", "tomato sauce", "pantry"), feature("paste", "Cento Tomato Paste", "tomato paste", "pantry")]),
            ("heavy cream", "heavy", ["half"], [feature("half", "Half And Half", None, "dairy"), feature("heavy", "Bowl & Basket Heavy Cream", "heavy cream", "dairy")]),
            ("pancake mix", "pancake", ["potato"], [feature("potato", "Streit's Potato Pancake Mix", None, "produce"), feature("pancake", "Pancake Mix", None, None)]),
            ("all-purpose flour", "ap", ["bread", "cake"], [feature("bread", "Bread Flour", "bread flour", "pantry"), feature("cake", "Cake Flour", "cake flour", "pantry"), feature("ap", "Gold Medal All Purpose Flour", "all-purpose flour", "pantry")]),
            ("active dry yeast", "active", ["nutritional"], [feature("nutritional", "Nutritional Yeast", "yeast", "pantry"), feature("active", "Active Dry Yeast", "yeast", "pantry")]),
            ("olive oil", "oil", ["dressing"], [feature("dressing", "Olive Oil Dressing", None, "pantry"), feature("oil", "Extra Virgin Olive Oil", "olive oil", "pantry")]),
            ("soy sauce", "soy", ["soybean"], [feature("soybean", "Soy Beans", None, "pantry"), feature("soy", "Kikkoman Soy Sauce", "soy sauce", "pantry")]),
            ("plain milk", "plain", ["chocolate"], [feature("chocolate", "Chocolate Milk", "milk", "dairy"), feature("plain", "Whole Milk", "milk", "dairy")]),
            ("oat milk", "oat", ["dairy"], [feature("dairy", "Whole Milk", "milk", "dairy"), feature("oat", "Elmhurst Unsweetened Oat Milk", "milk", "dairy")]),
            ("powdered milk", "dry", ["plain"], [feature("plain", "Bowl & Basket Milk", "milk", "dairy"), feature("dry", "Bowl & Basket Dry Milk", "milk", "dairy")]),
            ("beef stock", "beef", ["seafood"], [feature("seafood", "Kitchen Basics Seafood Stock", "stock", "pantry"), feature("beef", "Kitchen Basics Beef Stock", "stock", "pantry")]),
            ("cream of chicken soup", "chicken", ["tomato"], [feature("tomato", "Campbell's Creamy Tomato Soup", "soup", "pantry"), feature("chicken", "Campbell's Cream of Chicken Soup", "soup", "pantry")]),
            ("diced tomatoes", "diced", ["whole"], [feature("whole", "San Merican Whole Peeled Tomatoes", "tomatoes", "pantry"), feature("diced", "Bowl & Basket Tomatoes Diced", "tomatoes", "pantry")]),
        ]
        for query, expected, rejected, features in cases:
            with self.subTest(query=query):
                result = service(features).match_recipe_ingredient(query)
                self.assertEqual(result.selected_match.product_id, expected)
                self.assertTrue(set(rejected) <= {item.product_id for item in result.rejected_candidates})

    def test_compatibility_signal_classification(self):
        query, _ = profile_from_query("gluten-free flour")
        product = profile_from_feature(feature("ap", "Gold Medal All Purpose Flour", "all-purpose flour", "pantry"))
        signals = compatibility_signals(query, product)
        self.assertTrue(any(signal.classification == HARD_REJECT for signal in signals))

    def test_milk_fat_and_kind_regressions(self):
        svc = service(
            [
                feature("whole", "a2 Milk Whole Milk", "milk", "dairy"),
                feature("fatfree", "Bowl & Basket Fat Free Milk", "milk", "dairy"),
                feature("reduced", "Bowl & Basket 2% Reduced Fat Milk", "milk", "dairy"),
                feature("oat", "Elmhurst Unsweetened Oat Milk", "milk", "dairy"),
                feature("evap", "Carnation Evaporated Milk", "milk", "dairy"),
                feature("evap_fatfree", "Carnation Evaporated Fat-Free Milk", "milk", "dairy"),
                feature("kefir", "Lifeway Kefir Cultured Lowfat Milk", "milk", "dairy"),
            ]
        )
        nonfat = svc.match_recipe_ingredient("non-fat milk")
        self.assertEqual(nonfat.selected_match.product_id, "fatfree")
        self.assertIn("whole", {item.product_id for item in nonfat.rejected_candidates})
        self.assertIn("evap_fatfree", {item.product_id for item in nonfat.rejected_candidates})
        self.assertIn("kefir", {item.product_id for item in nonfat.rejected_candidates})
        plant = svc.match_recipe_ingredient("oat milk")
        self.assertEqual(plant.selected_match.product_id, "oat")
        self.assertIn("whole", {item.product_id for item in plant.rejected_candidates})
        ordinary = svc.match_recipe_ingredient("plain milk")
        self.assertIn("evap", {item.product_id for item in ordinary.rejected_candidates})
        fatfree = svc.match_recipe_ingredient("fat-free milk")
        self.assertEqual(fatfree.selected_match.product_id, "fatfree")
        self.assertIn("reduced", {item.product_id for item in fatfree.rejected_candidates})

    def test_beef_cut_regressions(self):
        svc = service(
            [
                feature("shaved", "Demakes Bros. Shaved Steak Beef", "beef", "meat"),
                feature("skirt", "Skirt Steak", "beef", "meat"),
                feature("ground", "Ground Beef Chuck", "ground beef", "meat"),
            ]
        )
        steak = svc.match_recipe_ingredient("skirt steak")
        self.assertEqual(steak.selected_match.product_id, "skirt")
        self.assertIn("shaved", {item.product_id for item in steak.rejected_candidates})
        ground = svc.match_recipe_ingredient("ground beef")
        self.assertEqual(ground.selected_match.product_id, "ground")
        self.assertTrue({"shaved", "skirt"} <= {item.product_id for item in ground.rejected_candidates})

    def test_demo_identity_regressions(self):
        cases = [
            ("apples", "apple", ["juice"], [feature("juice", "Snapple Juice Drink, Apple", None, "beverage"), feature("apple", "Bowl & Basket Macintosh Apples", "apple", "produce")]),
            ("almond butter", "almond", ["butter"], [feature("butter", "Bowl & Basket Butter", "butter", "dairy"), feature("almond", "Justin's Classic Almond Butter", None, "pantry")]),
            ("cayenne pepper", "cayenne", ["sweet"], [feature("sweet", "B&G Sweet Peppers", None, "pantry"), feature("cayenne", "Red Cayenne Pepper", None, "pantry")]),
            ("green onions", "scallion", ["onion"], [feature("onion", "Yellow Onions", "onion", "produce"), feature("scallion", "Green Onions (Scallions)", None, "produce")]),
            ("low-fat yogurt", "yogurt", ["drink"], [feature("drink", "Activia Mango Lowfat Yogurt Drink", "yogurt", "dairy"), feature("yogurt", "Chobani Low-Fat Greek Yogurt", "yogurt", "dairy")]),
            ("lemon pepper seasoning", "seasoning", ["marinade"], [feature("marinade", "Lawry's Lemon Pepper Marinade", None, "pantry"), feature("seasoning", "Dash Lemon Pepper Seasoning Blend", None, "pantry")]),
            ("1/2 can low-sodium tomatoes", "canned", ["fresh"], [feature("fresh", "Bowl & Basket Grape Tomatoes", "tomatoes", "produce"), feature("canned", "San Merican Whole Peeled Tomatoes", "tomatoes", "pantry")]),
            ("beef stew meat", "stew", ["mac"], [feature("mac", "Stouffer's Macaroni & Beef", "beef", "prepared"), feature("stew", "Beef For Stew", "beef", "meat")]),
            ("2 pounds stew meat, cut into 1-inch cubes", "stew", ["canned"], [feature("canned", "Dinty Moore Beef Stew With Potatoes And Carrots", "beef stew meat", "pantry"), feature("stew", "Beef For Stew", "beef stew meat", "meat")]),
            ("2 large carrots", "carrots", ["cake"], [feature("cake", "Carlo's Carrot Cake", "carrots", "bakery"), feature("carrots", "Wholesome Pantry Whole Carrots", "carrots", "produce")]),
            ("2 medium onions", "onions", ["rolls"], [feature("rolls", "Miami Onion Roll Company Challah Rolls", "onions", "bakery"), feature("onions", "Bowl & Basket Yellow Onions", "onions", "produce")]),
            ("chicken", "breast", ["broth", "parm"], [feature("broth", "Campbell's Chicken Broth", "broth", "pantry"), feature("parm", "Pasquale Chicken Parmesan", "chicken", "prepared"), feature("breast", "Boneless Chicken Breast", "chicken breast", "meat")]),
            ("1/2 pepper, per person", "bell", ["black"], [feature("black", "ShopRite Black Pepper", "peppers", "pantry"), feature("bell", "Red Bell Pepper", "peppers", "produce")]),
            ("3 slices tinned pineapple, per person", "pineapple", ["cake"], [feature("cake", "Pineapple Cheesecake Slice", "pineapple", "bakery"), feature("pineapple", "Dole Pineapple Slices", "pineapple", "pantry")]),
            ("curry powder", "curry", ["garlic"], [feature("garlic", "McCormick Garlic Powder", None, "pantry"), feature("curry", "McCormick Curry Powder", "curry powder", "pantry")]),
            ("cornflour", "cornstarch", ["chips"], [feature("chips", "Fritos Corn Chips", None, "snacks"), feature("cornstarch", "Argo Corn Starch", "corn starch", "pantry")]),
            ("pepper", "black", ["jalapeno", "jack"], [feature("jalapeno", "Jalapeno Pepper Bag", "peppers", "produce"), feature("jack", "Sargento Pepper Jack Slices", "peppers", "produce"), feature("black", "ShopRite Black Pepper", "peppers", "pantry")]),
            ("1 onion, minced", "white", ["dip", "rings"], [feature("dip", "Utz Creamy Onion Dip", "onions", "produce"), feature("rings", "Funyuns Onion Flavored Rings", "onions", "produce"), feature("white", "White Onion", "onions", "produce")]),
            ("celery", "celery", ["pasta", "salt"], [feature("pasta", "Colavita Cut Ziti Pasta", "pasta", "pantry"), feature("salt", "McCormick Celery Salt", "celery", "produce"), feature("celery", "Celery Package", None, None)]),
            ("garlic", "garlic", ["powder", "salt"], [feature("powder", "McCormick Garlic Powder", "garlic", "produce"), feature("salt", "McCormick Garlic Salt", "garlic", "produce"), feature("garlic", "Garlic", None, None)]),
            ("spinach", "spinach", ["dip", "ravioli", "pizza", "pouch"], [feature("dip", "Tostitos Creamy Spinach Dip", "spinach", "produce"), feature("ravioli", "Rana Spinach and Ricotta Ravioli", "spinach", "pantry"), feature("pizza", "Amy's Kitchen Spinach Pizza", "spinach", "frozen"), feature("pouch", "Beech-Nut Apple Blueberry and Spinach Pouch", "spinach", "baby"), feature("spinach", "Bowl & Basket Baby Spinach", None, None)]),
            ("arugula", "arugula", ["wrap"], [feature("wrap", "Spinach and Arugula Tortilla Wraps", "arugula", "pantry"), feature("arugula", "Bowl & Basket Arugula", None, None)]),
        ]
        for query, expected, rejected, features in cases:
            with self.subTest(query=query):
                result = service(features).match_recipe_ingredient(query)
                self.assertEqual(result.selected_match.product_id, expected)
                self.assertTrue(set(rejected) <= {item.product_id for item in result.rejected_candidates})

    def test_vegan_butter_alias_retrieves_plant_butter(self):
        overrides = {
            "version": "test-v1",
            "forbidden_products": [],
            "forced_matches": [],
            "approved_matches": [],
            "canonical_overrides": [],
            "aliases": [{"alias": "vegan butter", "canonical": "plant butter"}],
            "substitutions": [],
            "incompatible_families": [],
        }
        svc = service(
            [
                feature("dairy", "Wholesome Pantry Organic Butter", "butter", "dairy"),
                feature("plant", "Earth Balance Plant Butter Original Plant Based Oil Spread", "butter", "dairy"),
            ],
            overrides,
        )
        self.assertEqual(svc.match_recipe_ingredient("vegan butter").selected_match.product_id, "plant")


class OverrideCacheBatchEndpointTests(unittest.TestCase):
    def test_override_precedence_forbidden_beats_forced(self):
        overrides = {
            "version": "test-v1",
            "forbidden_products": [{"query": "milk", "product_id": "bad"}],
            "forced_matches": [{"query": "milk", "product_id": "bad"}, {"query": "milk", "product_id": "good"}],
            "approved_matches": [],
            "canonical_overrides": [],
            "aliases": [],
            "substitutions": [],
            "incompatible_families": [],
        }
        svc = service([feature("bad", "Oatmilk", "milk", "dairy"), feature("good", "Whole Milk", "milk", "dairy")], overrides)
        result = svc.match_recipe_ingredient("milk")
        self.assertEqual(result.selected_match.product_id, "good")
        self.assertIn("manual_forced", result.reason_codes)

    def test_cache_and_batch_matching(self):
        svc = service([feature("butter", "Unsalted Butter", "butter", "dairy", salted_status="unsalted")])
        first = svc.match_recipe_ingredient("unsalted butter")
        second = svc.match_recipe_ingredient("unsalted butter")
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(len(svc.match_recipe_ingredients(["unsalted butter", {"raw": "unsalted butter"}])), 2)

    def test_no_safe_match(self):
        result = service([feature("oat", "Oatmilk", "milk", "dairy")]).match_recipe_ingredient("low-fat milk")
        self.assertEqual(result.confidence, "no_safe_match")
        self.assertIsNone(result.selected_match)

    def test_development_endpoint(self):
        import model

        app = model.app
        app.config["TESTING"] = True
        fake_result = service([feature("butter", "Unsalted Butter", "butter", "dairy", salted_status="unsalted")]).match_recipe_ingredient("unsalted butter")
        with patch("product_compatibility.match_recipe_ingredient", return_value=fake_result), app.test_client() as client:
            response = client.get("/dev/product-match?ingredient=unsalted%20butter&limit=2")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["selected_match"]["product_id"], "butter")

    def test_morton_williams_recipe_matching_uses_product_match_service(self):
        import model

        fake_feature = {
            "product_id": "mw_chicken",
            "original_product_name": "Bell & Evans Chicken Breast",
            "normalized_name": "bell and evans chicken breast",
            "canonical_name": "chicken breast",
            "category": "meat",
            "eligible_for_retrieval": True,
            "price": 9.99,
            "package_quantity": 1,
            "package_unit": "pound",
        }
        fake_item = SimpleNamespace(
            product_id="mw_chicken",
            checkout_cost=9.99,
            package=SimpleNamespace(package_quantity=1, package_unit="pound"),
            packages_required=1,
            total_required=SimpleNamespace(to_dict=lambda: {"quantity": 1, "unit": "pound"}),
            leftover=SimpleNamespace(to_dict=lambda: {"quantity": 0, "unit": "pound"}),
            warnings=[],
            ingredients=["1 lb chicken breast"],
            product_name="Bell & Evans Chicken Breast",
        )
        fake_basket = SimpleNamespace(shopping_basket=[fake_item])

        class FakeService:
            feature_by_id = {"mw_chicken": fake_feature}

        recipe = {
            "extendedIngredients": [
                {"name": "chicken breast", "original": "1 lb chicken breast"},
                {"name": "water", "original": "2 cups boiling water"},
            ]
        }
        with patch("basket_quantity.build_recipe_basket", return_value=fake_basket), patch(
            "model.basket_builder_match_service", return_value=FakeService()
        ):
            matches = model.match_recipe_ingredients_to_morton_williams(recipe)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][1]["id"], "mw_chicken")
        self.assertEqual(matches[0][1]["store_id"], "morton-williams")
        self.assertEqual(matches[0][1]["pricing_source"], "morton_williams_quantity_engine")
        self.assertEqual(matches[0][1]["estimated_price_total"], 9.99)

    def test_pantry_adjustment_filters_covered_items_and_spices(self):
        import model

        recipe = {
            "extendedIngredients": [
                {"name": "flour", "original": "1/4 cup flour"},
                {"name": "salt and pepper", "original": "salt and pepper"},
                {"name": "carrots", "original": "3 medium carrots"},
            ]
        }
        adjusted, _originals = model.pantry_adjusted_recipe_ingredients(
            recipe,
            [
                {"name": "flour", "quantity": "1 cup"},
                {"name": "salt", "quantity": "1 jar"},
                {"name": "black pepper", "quantity": "1 jar"},
                {"name": "carrots", "quantity": "1 carrot"},
            ],
        )
        self.assertEqual(adjusted, ["2 carrots"])

    def test_per_person_recipe_quantities_are_scaled_for_matching(self):
        import model

        recipe = {
            "extendedIngredients": [
                {"name": "chicken thighs", "original": "2 chicken, thighs per person"},
                {"name": "pepper", "original": "1/2 pepper, per person"},
            ]
        }
        adjusted, _originals = model.pantry_adjusted_recipe_ingredients(recipe, [], servings=4)
        self.assertEqual(adjusted, ["8 chicken thighs", "2 peppers"])

    def test_demo_dish_does_not_emit_unavailable_buy_rows(self):
        import model

        recipe = {
            "id": "r1",
            "title": "Test Recipe",
            "sourceUrl": "https://example.test",
            "extendedIngredients": [
                {"name": "water", "original": "2 cups water"},
                {"name": "missing", "original": "1 missing ingredient"},
            ],
            "instructions": "Cook.",
        }
        dish = model.spoonacular_recipe_to_demo_dish(
            recipe,
            [({"name": "missing", "measure": "1 missing ingredient"}, None)],
            model.morton_williams_store_lookup(),
            2,
            grocery_label="Morton Williams",
        )
        self.assertEqual(dish["ingredients_to_buy"], [])

    def test_evaluation_helper(self):
        from evaluate_product_matching import evaluate

        svc = service([feature("butter", "Unsalted Butter", "butter", "dairy", salted_status="unsalted")])
        metrics = evaluate(
            [
                {
                    "query": "unsalted butter",
                    "acceptable_patterns": ["unsalted butter"],
                    "unacceptable_patterns": ["margarine"],
                }
            ],
            svc,
        )
        self.assertEqual(metrics["case_count"], 1)
        self.assertEqual(metrics["hard_conflict_selection_count"], 0)


if __name__ == "__main__":
    unittest.main()
