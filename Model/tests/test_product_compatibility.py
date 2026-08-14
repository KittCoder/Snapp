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


class FakeBatchRetriever(FakeRetriever):
    def __init__(self, features):
        super().__init__(features)
        self.batch_calls = 0

    def retrieve_product_candidates_batch(self, ingredient_texts, limit=50, **_kwargs):
        self.batch_calls += 1
        return [
            CandidateRetrievalResult(
                ingredient_text=ingredient_text,
                parsed_query={},
                normalized_semantic_query=ingredient_text,
                candidates=[
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
                        retrieval_reason_codes=["test_batch"],
                    )
                    for item in self.features[:limit]
                ],
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
            for ingredient_text in ingredient_texts
        ]


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
            ("1 jar spaghetti sauce", "sauce", ["linguine"], [feature("linguine", "Colavita Linguine Pasta", "pasta", "pantry"), feature("sauce", "Rao's Homemade Marinara Sauce", "pasta sauce", "pantry")]),
            ("heavy cream", "heavy", ["half"], [feature("half", "Half And Half", None, "dairy"), feature("heavy", "Bowl & Basket Heavy Cream", "heavy cream", "dairy")]),
            ("pancake mix", "pancake", ["potato"], [feature("potato", "Streit's Potato Pancake Mix", None, "produce"), feature("pancake", "Pancake Mix", None, None)]),
            ("all-purpose flour", "ap", ["cake"], [feature("bread", "Bread Flour", "bread flour", "pantry"), feature("cake", "Cake Flour", "cake flour", "pantry"), feature("ap", "Gold Medal All Purpose Flour", "all-purpose flour", "pantry")]),
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
                unsafe_ids = {item.product_id for item in result.rejected_candidates + result.substitution_candidates}
                self.assertTrue(set(rejected) <= unsafe_ids)

    def test_compatibility_signal_classification(self):
        query, _ = profile_from_query("gluten-free flour")
        product = profile_from_feature(feature("ap", "Gold Medal All Purpose Flour", "all-purpose flour", "pantry"))
        signals = compatibility_signals(query, product)
        self.assertTrue(any(signal.classification == HARD_REJECT for signal in signals))

    def test_nuts_olives_and_spices_remain_buyable(self):
        cases = [
            ("walnuts", "walnuts", ["cookies", "dressing"], [feature("cookies", "Walnut Chocolate Chip Cookies", None, "snacks"), feature("dressing", "Walnut Dressing", None, "pantry"), feature("walnuts", "Fisher Chopped Walnuts", "walnuts", "pantry")]),
            ("pecans", "pecans", ["tarte"], [feature("tarte", "Chambord Pecan Tarte", None, "prepared"), feature("pecans", "Diamond Chopped Pecans", "pecans", "pantry")]),
            ("almonds", "almonds", ["milk"], [feature("milk", "Almond Milk", "almond milk", "dairy"), feature("almonds", "Bowl & Basket Almonds", "almonds", "pantry")]),
            ("pitted Kalamata olives", "olives", ["oil"], [feature("oil", "Extra Virgin Olive Oil", "olive oil", "pantry"), feature("olives", "Bowl & Basket Kalamata Olives", "olives", "pantry")]),
            ("cumin", "cumin", ["curry"], [feature("curry", "Chicken Curry with Cumin Rice", None, "prepared"), feature("cumin", "Simply Organic Cumin", "cumin", "pantry")]),
            ("chili powder", "chili", ["garlic"], [feature("garlic", "McCormick Garlic Powder", "garlic powder", "pantry"), feature("chili", "McCormick Chili Powder", "chili powder", "pantry")]),
            ("paprika", "paprika", ["hummus"], [feature("hummus", "Roasted Red Pepper Paprika Hummus", None, "prepared"), feature("paprika", "Simply Organic Paprika", "paprika", "pantry")]),
            ("vanilla", "vanilla", ["syrup"], [feature("syrup", "Vanilla Syrup", None, "beverage"), feature("vanilla", "Pure Vanilla Extract", "vanilla extract", "pantry")]),
            ("lime juice", "lime", ["apple"], [feature("apple", "Apple Juice", "apple juice", "beverage"), feature("lime", "ReaLime 100% Lime Juice", "lime juice", "pantry")]),
            ("mustard", "mustard", ["crackers"], [feature("crackers", "Honey Mustard Pretzel Crackers", None, "snacks"), feature("mustard", "Gulden's Spicy Brown Mustard", "mustard", "pantry")]),
            ("honey", "honey", ["ham"], [feature("ham", "Honey Ham", "ham", "meat"), feature("honey", "Bowl & Basket Honey", "honey", "pantry")]),
        ]
        for query, expected, rejected, features in cases:
            with self.subTest(query=query):
                result = service(features).match_recipe_ingredient(query)
                self.assertEqual(result.selected_match.product_id, expected)
                unsafe_ids = {item.product_id for item in result.rejected_candidates + result.substitution_candidates}
                self.assertTrue(set(rejected) <= unsafe_ids)

    def test_bulk_matching_uses_batched_retrieval_for_unique_misses(self):
        retriever = FakeBatchRetriever(
            [
                feature("walnuts", "Fisher Chopped Walnuts", "walnuts", "pantry"),
                feature("milk", "Whole Milk", "milk", "dairy"),
            ]
        )
        svc = ProductMatchService(retriever=retriever, overrides=OverrideStore(Path("/tmp/definitely-missing-overrides.json")))

        results = svc.match_recipe_ingredients(["walnuts", "milk"], limit=5)

        self.assertEqual(retriever.batch_calls, 1)
        self.assertEqual(retriever.calls, 0)
        self.assertEqual(len(results), 2)

    def test_beef_does_not_accept_pork_sausage(self):
        result = service(
            [
                feature("pork_sausage", "Fresh Pork Sausage", "pork sausage", "meat"),
                feature("beef", "Beef For Stew", "beef stew meat", "meat"),
            ]
        ).match_recipe_ingredient("beef")
        self.assertEqual(result.selected_match.product_id, "beef")
        self.assertIn("pork_sausage", {item.product_id for item in result.rejected_candidates})

    def test_generic_beef_rejects_sauces_and_processed_meat_when_raw_beef_exists(self):
        result = service(
            [
                feature("sauce", "Bowl & Basket Steak Sauce", "beef", "meat"),
                feature("franks", "Hebrew National Beef Franks Hot Dogs", "beef", "meat"),
                feature("jerky", "Wholesome Pantry Beef Jerky", "beef", "meat"),
                feature("burger", "Beef Burgers", "beef", "meat"),
                feature("bones", "USDA Choice Beef Marrow Bones", "beef", "meat"),
                feature("pet", "Milk-Bone Original Biscuits Original Beef Flavor", "beef", "meat"),
                feature("stew", "Beef For Stew", "beef stew meat", "meat"),
            ]
        ).match_recipe_ingredient("1 pound beef")
        self.assertEqual(result.selected_match.product_id, "stew")
        rejected_ids = {item.product_id for item in result.rejected_candidates}
        self.assertTrue({"sauce", "franks", "jerky", "bones", "pet"} <= rejected_ids)
        self.assertIn("burger", {item.product_id for item in result.compatible_alternatives})

    def test_suet_absent_inventory_does_not_force_fat_substitute(self):
        result = service(
            [
                feature("shortening", "Crisco Shortening", "shortening", "pantry"),
                feature("lard", "Lard", "lard", "pantry"),
                feature("butter", "Bowl & Basket Butter", "butter", "dairy"),
            ]
        ).match_recipe_ingredient("4 ounce suet")
        self.assertIsNone(result.selected_match)
        self.assertEqual(result.confidence, NO_SAFE_MATCH)

    def test_beef_sausage_and_pork_sausage_stay_distinct(self):
        result = service(
            [
                feature("pork_sausage", "Fresh Pork Sausage", "pork sausage", "meat"),
                feature("beef_sausage", "Hillshire Farm Beef Smoked Sausage", "beef sausage", "meat"),
            ]
        ).match_recipe_ingredient("beef sausage")
        self.assertEqual(result.selected_match.product_id, "beef_sausage")
        self.assertIn("pork_sausage", {item.product_id for item in result.rejected_candidates})

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

    def test_unrequested_evaporated_milk_variant_does_not_outrank_plain(self):
        svc = service(
            [
                feature("lowfat", "Carnation Evaporated Lowfat Milk", "milk", "dairy", fat_level="low-fat"),
                feature("plain", "Bowl & Basket Evaporated Milk", "milk", "dairy"),
            ]
        )
        self.assertEqual(svc.match_recipe_ingredient("evaporated milk").selected_match.product_id, "plain")

    def test_margarine_is_not_reclassified_as_cooking_oil(self):
        svc = service(
            [
                feature("oil", "Bowl & Basket Vegetable Oil", "vegetable oil", "pantry"),
                feature("margarine", "Land O Lakes Margarine Sticks, Made with Vegetable Oil", "margarine", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("margarine")
        self.assertEqual(result.selected_match.product_id, "margarine")
        self.assertIn("oil", {item.product_id for item in result.rejected_candidates})

    def test_product_descriptor_words_do_not_override_core_identity(self):
        cases = [
            (
                "2 tablespoon margarine",
                "margarine",
                ["pickles"],
                [
                    feature("pickles", "B&G Pickles, Bread & Butter", "butter", "dairy"),
                    feature("margarine", "Land O Lakes Margarine Sticks", "margarine", "dairy"),
                ],
            ),
            (
                "0.5 teaspoon salt",
                "salt",
                ["beans"],
                [
                    feature("beans", "Del Monte No Salt Added Cut Green Beans", "salt", "pantry"),
                    feature("salt", "Bowl & Basket Salt", "salt", "pantry"),
                ],
            ),
            (
                "2 cup milk",
                "milk",
                ["matzos"],
                [
                    feature("matzos", "Streit's Milk Chocolate Matzos", "milk", "dairy"),
                    feature("milk", "a2 Milk Whole Milk", "milk", "dairy"),
                ],
            ),
        ]
        for query, expected, rejected, features in cases:
            with self.subTest(query=query):
                result = service(features).match_recipe_ingredient(query)
                self.assertEqual(result.selected_match.product_id, expected)
                rejected_ids = {item.product_id for item in result.rejected_candidates}
                self.assertTrue(set(rejected) <= rejected_ids)

    def test_fresh_prepped_produce_rejects_seasoned_or_pickled_forms(self):
        cases = [
            (
                "1 cup diced celery diced",
                "celery",
                ["sticks", "salt"],
                [
                    feature("sticks", "Sunnyside Fresh Celery Sticks", "celery", "produce", freshness="fresh"),
                    feature("salt", "McCormick Celery Salt", "celery", "produce"),
                    feature("celery", "Celery Heart Bag", "celery", "produce", freshness="fresh"),
                ],
            ),
            (
                "0.5 cup diced green pepper diced",
                "green",
                ["pickled"],
                [
                    feature("pickled", "B&G Sweet Peppers", "peppers", "produce"),
                    feature("green", "Green Bell Pepper", "peppers", "produce", freshness="fresh"),
                ],
            ),
            (
                "0.25 cup minced onion minced",
                "onion",
                ["granulated"],
                [
                    feature("granulated", "Watertown Choice Granulated Onion", "onions", "produce"),
                    feature("onion", "White Onion", "onions", "produce", freshness="fresh"),
                ],
            ),
        ]
        for query, expected, rejected, features in cases:
            with self.subTest(query=query):
                result = service(features).match_recipe_ingredient(query)
                self.assertEqual(result.selected_match.product_id, expected)
                unsafe_ids = {item.product_id for item in result.rejected_candidates + result.substitution_candidates}
                self.assertTrue(set(rejected) <= unsafe_ids)

    def test_sour_cream_phrase_requires_sour_cream_not_salad_dressing(self):
        result = service(
            [
                feature("dressing", "Wish-Bone Creamy French Salad Dressing", "salad dressing", "pantry"),
                feature("sour", "Daisy Sour Cream, Pure & Natural", "sour cream", "dairy"),
            ]
        ).match_recipe_ingredient("sour cream dressing")
        self.assertEqual(result.selected_match.product_id, "sour")
        self.assertIn("dressing", {item.product_id for item in result.rejected_candidates})

    def test_canned_tuna_can_match_tuna_inventory_with_canned_metadata(self):
        svc = service(
            [
                feature("fresh", "Fresh Tuna Steak", "tuna", "meat", freshness="fresh"),
                feature("canned", "Bumble Bee Chunk Light Tuna In Water 5 Oz Can", "tuna", "pantry", freshness="canned"),
            ]
        )
        result = svc.match_recipe_ingredient("canned tuna")
        self.assertEqual(result.selected_match.product_id, "canned")
        self.assertIn("fresh", {item.product_id for item in result.rejected_candidates + result.substitution_candidates})

    def test_canned_tuna_allows_unmarked_shelf_stable_tuna_but_not_prepared_tuna(self):
        svc = service(
            [
                feature("salad", "Store Prepared Tuna Salad", "tuna", "prepared"),
                feature("oil", "Genova Solid White Tuna In Olive Oil", "tuna", "pantry"),
            ]
        )
        result = svc.match_recipe_ingredient("canned tuna")
        self.assertEqual(result.selected_match.product_id, "oil")
        self.assertIn("salad", {item.product_id for item in result.rejected_candidates})

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

    def test_beef_shank_prefers_raw_shank_and_rejects_processed_beef(self):
        svc = service(
            [
                feature("frank", "Sabrett Skinless Beef Frankfurters Bun Size", "beef", "meat"),
                feature("deli", "Black Bear London Broil Roast Beef", "beef", "meat"),
                feature("shank", "USDA Choice Beef Hindshank, Bone In, Average Weight 1 lb Pack", "beef", "meat"),
                feature("stew", "Beef For Stew", "beef stew meat", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("2 pound beef, shank")
        self.assertEqual(result.selected_match.product_id, "shank")
        rejected_ids = {item.product_id for item in result.rejected_candidates}
        self.assertTrue({"frank", "deli"} <= rejected_ids)

    def test_beef_chuck_roast_can_fallback_to_raw_slow_cooking_beef_cut(self):
        svc = service(
            [
                feature("coffee", "Folgers Half Caff Medium Roast Coffee", None, "pantry"),
                feature("frank", "Sabrett Skinless Beef Frankfurters Bun Size", "beef", "meat"),
                feature("deli", "Black Bear London Broil Roast Beef", "beef", "meat"),
                feature("stew", "USDA choice boneless beef for stew", "beef stew meat", "meat"),
                feature("chuck", "Fresh Beef 1st Cut Chuck Steak", "beef", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("2 1/2 pounds boneless lean beef chuck roast")
        self.assertIn(result.selected_match.product_id, {"stew", "chuck"})
        rejected_ids = {item.product_id for item in result.rejected_candidates}
        self.assertTrue({"coffee", "frank", "deli"} <= rejected_ids)

    def test_old_recipe_steak_wording_retrieves_raw_beef_not_steak_sauce(self):
        svc = service(
            [
                feature("sauce", "Peter Luger Steak House Sauce, Old Fashioned", None, "pantry"),
                feature("round", "Certified angus beef top round london broil", "beef", "meat"),
                feature("sirloin", "Sirloin Steak (Palomilla)", "beef", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("1 1/2 pound round or flank steak")
        self.assertIn(result.selected_match.product_id, {"round", "sirloin"})
        self.assertIn("sauce", {item.product_id for item in result.rejected_candidates})

    def test_stewing_meat_accepts_raw_beef_or_lamb_but_not_prepared_food(self):
        svc = service(
            [
                feature("prepared", "Yellowstone Bunkhouse Braised Beef Stew", "beef", "meat"),
                feature("soup", "Rao's Made For Home Tuscan Style Beef Stew Soup", "beef", "meat"),
                feature("pork", "Pork For Stew", "pork", "meat"),
                feature("beef", "Beef For Stew", "beef stew meat", "meat"),
                feature("lamb", "Lamb For Stew", "lamb stew meat", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("stewing meat")
        self.assertIn(result.selected_match.product_id, {"beef", "lamb"})
        rejected_ids = {item.product_id for item in result.rejected_candidates}
        self.assertTrue({"prepared", "soup", "pork"} <= rejected_ids)

    def test_specified_lamb_stew_meat_does_not_become_beef(self):
        svc = service(
            [
                feature("beef", "Beef For Stew", "beef stew meat", "meat"),
                feature("lamb", "Lamb For Stew", "lamb stew meat", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("lamb stew meat")
        self.assertEqual(result.selected_match.product_id, "lamb")
        self.assertIn("beef", {item.product_id for item in result.rejected_candidates})

    def test_raw_beef_roast_rejects_deli_or_premade_roast_beef(self):
        svc = service(
            [
                feature("deli", "Black Bear London Broil Roast Beef", "beef", "meat"),
                feature("sandwich", "Morton Williams Roast Beef and Tillamook Cheddar Sandwich", "beef", "meat"),
                feature("raw", "Certified Angus Beef Eye Round Roast, Boneless", "beef", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("standing rib roast beef")
        self.assertEqual(result.selected_match.product_id, "raw")
        rejected_ids = {item.product_id for item in result.rejected_candidates}
        self.assertTrue({"deli", "sandwich"} <= rejected_ids)

    def test_beef_cut_table_prefers_raw_cut_substitutes_and_rejects_prepared_items(self):
        svc = service(
            [
                feature("entree", "Ajinomoto Tai Pei Beef & Broccoli Frozen Asian Entrée", "beef", "prepared"),
                feature("bacon", "Peter Luger Steak House extra thick cut bacon, 12oz package", "bacon", "meat"),
                feature("soup", "Progresso Pitmaster Steak and Potatoes with Roasted Vegetables Canned Soup", "beef", "pantry"),
                feature("hanger", "Beef Hanger Steak", "beef", "meat"),
                feature("strip", "Certified Angus Beef New York Strip Steak, Bone In", "beef", "meat"),
                feature("stew", "Beef For Stew", "beef stew meat", "meat"),
            ]
        )
        strips = svc.match_recipe_ingredient("1/2 lb Beef, cut into strips")
        self.assertIn(strips.selected_match.product_id, {"hanger", "strip"})
        self.assertTrue({"entree", "bacon", "soup"} <= {item.product_id for item in strips.rejected_candidates})

        stew = svc.match_recipe_ingredient("2 pounds beef, stew meat")
        self.assertEqual(stew.selected_match.product_id, "stew")
        self.assertTrue({"entree", "bacon", "soup"} <= {item.product_id for item in stew.rejected_candidates})

    def test_fillet_beef_prefers_tenderloin_table_substitutes_not_chuck(self):
        svc = service(
            [
                feature("chuck", "Fresh Beef 1st Cut Chuck Steak", "beef", "meat"),
                feature("hanger", "Beef Hanger Steak", "beef", "meat"),
                feature("tenderloin", "Certified Angus Beef Loin Tenderloin Steak, Boneless", "beef", "meat"),
                feature("strip", "Certified Angus Beef New York Strip Steak, Bone In", "beef", "meat"),
            ]
        )
        result = svc.match_recipe_ingredient("1lb of Fillet Beef")
        self.assertIn(result.selected_match.product_id, {"tenderloin", "strip"})
        self.assertIn("chuck", {item.product_id for item in result.rejected_candidates})

    def test_egg_yolks_match_whole_egg_inventory_not_no_yolks_products(self):
        svc = service(
            [
                feature("no_yolks", "No Yolks Extra Broad Enriched Macaroni Product", None, "pantry"),
                feature("substitute", "Egg Beaters Original Liquid Egg Substitute", "eggs", "dairy"),
                feature("eggs", "Bowl & Basket Eggs", "eggs", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("2 Egg Yolks Beaten")
        self.assertEqual(result.selected_match.product_id, "eggs")
        self.assertIn("no_yolks", {item.product_id for item in result.rejected_candidates})

    def test_puff_pastry_matches_raw_pastry_sheets_not_pastry_snacks(self):
        svc = service(
            [
                feature("crisps", "Special K Pastry Crisps", None, "snacks"),
                feature("franks", "Nathan's Famous Beef Franks in Puff Pastry, Party Size", "beef", "meat"),
                feature("sheets", "Bowl & Basket Puff Pastry Sheets", None, None),
                feature("dough", "Pepperidge Farm Frozen Sheets Pastry Dough", None, None),
            ]
        )
        result = svc.match_recipe_ingredient("7oz of Puff Pastry")
        self.assertIn(result.selected_match.product_id, {"sheets", "dough"})
        self.assertTrue({"crisps", "franks"} <= {item.product_id for item in result.rejected_candidates})

    def test_bouillon_keeps_species_and_is_not_prepared_beef_flavor(self):
        svc = service(
            [
                feature("vegetable", "Knorr Bouillon Cubes Vegetable", None, "pantry"),
                feature("chicken", "Maggi Chicken Flavor Bouillon Tablets", None, "pantry"),
                feature("beef", "HERB-OX Beef Bouillon Cube, 3.25 OZ", None, "pantry"),
            ]
        )
        result = svc.match_recipe_ingredient("1 low-sodium beef bouillon cube")
        self.assertEqual(result.selected_match.product_id, "beef")
        self.assertTrue({"vegetable", "chicken"} <= {item.product_id for item in result.rejected_candidates})
        typo = svc.match_recipe_ingredient("1 beef bouillan cube")
        self.assertEqual(typo.selected_match.product_id, "beef")

    def test_plain_honey_rejects_honey_flavored_bakery_or_snacks(self):
        svc = service(
            [
                feature("cornbread", "Honey Flavored Corn Bread", None, "bakery"),
                feature("crackers", "HONEY MAID Honey Graham Crackers", None, "snacks"),
                feature("honey", "Bowl & Basket Honey", "honey", "pantry"),
            ]
        )
        result = svc.match_recipe_ingredient("1 tablespoon honey")
        self.assertEqual(result.selected_match.product_id, "honey")
        self.assertTrue({"cornbread", "crackers"} <= {item.product_id for item in result.rejected_candidates})

    def test_prepared_mustard_rejects_mustard_seed_or_powder(self):
        svc = service(
            [
                feature("seed", "McCormick Yellow Mustard Seed", None, "pantry"),
                feature("powder", "Colman's Mustard Powder", None, "pantry"),
                feature("mustard", "French's Classic Yellow Mustard", None, "pantry"),
            ]
        )
        result = svc.match_recipe_ingredient("2 tablespoons yellow mustard")
        self.assertEqual(result.selected_match.product_id, "mustard")
        self.assertTrue({"seed", "powder"} <= {item.product_id for item in result.rejected_candidates})

    def test_juice_only_matches_when_recipe_asks_for_juice(self):
        carrots = service(
            [
                feature("juice", "Bolthouse Farms 100% Carrot Juice", "carrots", "produce"),
                feature("carrots", "Wholesome Pantry Whole Carrots", "carrots", "produce"),
            ]
        ).match_recipe_ingredient("1/3 cup julienne carrots")
        self.assertEqual(carrots.selected_match.product_id, "carrots")
        self.assertIn("juice", {item.product_id for item in carrots.rejected_candidates})

        orange_juice = service(
            [
                feature("orange", "Navel Oranges", "orange", "produce"),
                feature("juice", "Florida's Natural 100% Premium Florida Orange Juice", None, "beverage"),
            ]
        ).match_recipe_ingredient("1/16 cup orange juice")
        self.assertEqual(orange_juice.selected_match.product_id, "juice")
        self.assertIn("orange", {item.product_id for item in orange_juice.rejected_candidates})

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
            ("1/8 teaspoon pepper", "black", ["roasted"], [feature("roasted", "Cento Roasted Peppers", "peppers", "pantry"), feature("black", "ShopRite Black Pepper", "peppers", "pantry")]),
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

    def test_culinary_substitution_expands_neufchatel_to_cream_cheese(self):
        svc = service([feature("cream", "Philadelphia Original Cream Cheese", "cream cheese", "dairy")])
        result = svc.match_recipe_ingredient("neufchatel")
        self.assertEqual(result.selected_match.product_id, "cream")
        self.assertIn("culinary_substitute", result.selected_match.reason_codes)

    def test_exact_ingredient_outranks_substitution(self):
        svc = service(
            [
                feature("mascarpone", "BelGioioso Mascarpone", None, "dairy"),
                feature("cream", "Philadelphia Original Cream Cheese", "cream cheese", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("cream cheese")
        self.assertEqual(result.selected_match.product_id, "cream")
        self.assertIn("mascarpone", {item.product_id for item in result.compatible_alternatives + result.substitution_candidates})

    def test_cream_cheese_does_not_become_cheddar(self):
        svc = service([feature("cheddar", "Bowl & Basket Mild Cheddar Cheese", "cheddar cheese", "dairy")])
        result = svc.match_recipe_ingredient("cream cheese")
        self.assertIsNone(result.selected_match)
        self.assertIn("cheddar", {item.product_id for item in result.rejected_candidates})

    def test_parmesan_accepts_grana_padano_but_not_mozzarella(self):
        svc = service(
            [
                feature("mozz", "Low Moisture Mozzarella Cheese", "mozzarella cheese", "dairy"),
                feature("grana", "BelGioioso Grana Padano Cheese", None, "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("parmesan")
        self.assertEqual(result.selected_match.product_id, "grana")
        self.assertIn("mozz", {item.product_id for item in result.rejected_candidates})

    def test_heavy_cream_rejects_half_and_half_when_whipping(self):
        svc = service(
            [
                feature("half", "Bowl & Basket Half And Half", None, "dairy"),
                feature("heavy", "Bowl & Basket Heavy Whipping Cream", "heavy cream", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("heavy cream for whipping")
        self.assertEqual(result.selected_match.product_id, "heavy")
        self.assertIn("half", {item.product_id for item in result.rejected_candidates})

    def test_heavy_cream_allows_half_and_half_for_sauce(self):
        result = service([feature("half", "Bowl & Basket Half And Half", None, "dairy")]).match_recipe_ingredient(
            "heavy cream for sauce"
        )
        self.assertEqual(result.selected_match.product_id, "half")
        self.assertIn("culinary_substitute", result.selected_match.reason_codes)

    def test_sweetened_condensed_milk_never_matches_evaporated_milk(self):
        svc = service(
            [
                feature("evap", "Carnation Evaporated Milk", "milk", "dairy"),
                feature("condensed", "Eagle Brand Sweetened Condensed Milk", "milk", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("sweetened condensed milk")
        self.assertEqual(result.selected_match.product_id, "condensed")
        self.assertIn("evap", {item.product_id for item in result.rejected_candidates})

    def test_plain_greek_yogurt_can_substitute_for_sour_cream_but_not_flavored(self):
        svc = service(
            [
                feature("mango", "Chobani Mango Greek Yogurt", "yogurt", "dairy"),
                feature("greek", "Fage Plain Greek Yogurt", "yogurt", "dairy"),
            ]
        )
        result = svc.match_recipe_ingredient("sour cream")
        self.assertEqual(result.selected_match.product_id, "greek")
        self.assertIn("mango", {item.product_id for item in result.rejected_candidates})

    def test_starch_and_grain_incompatibilities_are_preserved(self):
        svc = service(
            [
                feature("flour", "Gold Medal All Purpose Flour", "all-purpose flour", "pantry"),
                feature("panko", "Kikkoman Panko Bread Crumbs", None, "pantry"),
                feature("cornmeal", "Indian Head Yellow Corn Meal", None, "pantry"),
                feature("cornstarch", "Argo Corn Starch", "corn starch", "pantry"),
            ]
        )
        breadcrumbs = svc.match_recipe_ingredient("breadcrumbs")
        self.assertEqual(breadcrumbs.selected_match.product_id, "panko")
        self.assertIn("flour", {item.product_id for item in breadcrumbs.rejected_candidates})

        starch = svc.match_recipe_ingredient("cornstarch")
        self.assertEqual(starch.selected_match.product_id, "cornstarch")
        self.assertIn("cornmeal", {item.product_id for item in starch.rejected_candidates})

    def test_flour_and_starch_substitutions_are_functional(self):
        bread = service([feature("ap", "Gold Medal All Purpose Flour", "all-purpose flour", "pantry")]).match_recipe_ingredient(
            "bread flour"
        )
        self.assertEqual(bread.selected_match.product_id, "ap")

        cake = service([feature("bread", "King Arthur Bread Flour", "bread flour", "pantry")]).match_recipe_ingredient(
            "cake flour"
        )
        self.assertIsNone(cake.selected_match)
        self.assertIn("bread", {item.product_id for item in cake.rejected_candidates})

        starch = service([feature("potato", "Bob's Red Mill Potato Starch", None, "pantry")]).match_recipe_ingredient(
            "cornstarch"
        )
        self.assertEqual(starch.selected_match.product_id, "potato")

    def test_rice_and_pasta_functional_substitution(self):
        rice = service([feature("jasmine", "Mahatma Jasmine Rice", "rice", "pantry")]).match_recipe_ingredient("long grain white rice")
        self.assertEqual(rice.selected_match.product_id, "jasmine")

        pasta = service([feature("rigatoni", "De Cecco Rigatoni Pasta", "pasta", "pantry")]).match_recipe_ingredient("penne")
        self.assertEqual(pasta.selected_match.product_id, "rigatoni")

    def test_rice_and_pasta_poor_shape_substitutions(self):
        arborio = service([feature("long", "Mahatma Long Grain White Rice", "rice", "pantry")]).match_recipe_ingredient(
            "Arborio rice"
        )
        self.assertIsNone(arborio.selected_match)
        self.assertIn("long", {item.product_id for item in arborio.compatible_alternatives})

        spaghetti = service([feature("lasagna", "Barilla Lasagna Sheets", "pasta", "pantry")]).match_recipe_ingredient(
            "spaghetti"
        )
        self.assertIsNone(spaghetti.selected_match)
        self.assertIn("lasagna", {item.product_id for item in spaghetti.rejected_candidates})

    def test_green_onions_stay_distinct_from_yellow_onions(self):
        svc = service(
            [
                feature("yellow", "Yellow Onions", "onions", "produce"),
                feature("scallions", "Green Onions Scallions", None, "produce"),
            ]
        )
        result = svc.match_recipe_ingredient("green onions")
        self.assertEqual(result.selected_match.product_id, "scallions")
        self.assertIn("yellow", {item.product_id for item in result.rejected_candidates + result.substitution_candidates})

    def test_vegetable_functional_substitutions_and_pepper_identity(self):
        broccoli = service([feature("broccolini", "Fresh Broccolini", None, "produce")]).match_recipe_ingredient("broccoli")
        self.assertEqual(broccoli.selected_match.product_id, "broccolini")

        pepper = service(
            [
                feature("black", "ShopRite Black Pepper", "peppers", "pantry"),
                feature("red", "Red Bell Pepper", "peppers", "produce"),
            ]
        ).match_recipe_ingredient("bell pepper")
        self.assertEqual(pepper.selected_match.product_id, "red")
        self.assertIn("black", {item.product_id for item in pepper.rejected_candidates})

    def test_tomato_legume_and_form_rules(self):
        tomato = service([feature("whole", "San Marzano Whole Peeled Tomatoes", "tomatoes", "pantry")]).match_recipe_ingredient(
            "diced canned tomatoes for cooked sauce"
        )
        self.assertEqual(tomato.selected_match.product_id, "whole")

        raw_tomato = service([feature("canned", "Bowl & Basket Diced Tomatoes", "tomatoes", "pantry")]).match_recipe_ingredient(
            "fresh tomato salad"
        )
        self.assertIsNone(raw_tomato.selected_match)
        self.assertIn("canned", {item.product_id for item in raw_tomato.rejected_candidates})

        paste = service([feature("ketchup", "Heinz Ketchup", None, "pantry")]).match_recipe_ingredient("tomato paste")
        self.assertIsNone(paste.selected_match)
        self.assertIn("ketchup", {item.product_id for item in paste.rejected_candidates})

        beans = service([feature("great", "Great Northern Beans", "beans", "pantry")]).match_recipe_ingredient("cannellini beans")
        self.assertEqual(beans.selected_match.product_id, "great")

        chickpeas = service([feature("garbanzo", "Goya Garbanzo Beans", "beans", "pantry")]).match_recipe_ingredient("chickpeas")
        self.assertEqual(chickpeas.selected_match.product_id, "garbanzo")

        lentils = service([feature("red", "Red Lentils", None, "pantry")]).match_recipe_ingredient("green lentils")
        self.assertIsNone(lentils.selected_match)
        self.assertIn("red", {item.product_id for item in lentils.rejected_candidates})

    def test_frozen_spinach_form_depends_on_context(self):
        cooked = service([feature("frozen", "Frozen Chopped Spinach", "spinach", "produce", freshness="frozen")]).match_recipe_ingredient(
            "cooked fresh spinach"
        )
        self.assertEqual(cooked.selected_match.product_id, "frozen")

        salad = service([feature("frozen", "Frozen Chopped Spinach", "spinach", "produce", freshness="frozen")]).match_recipe_ingredient(
            "fresh spinach salad"
        )
        self.assertIsNone(salad.selected_match)
        self.assertIn("frozen", {item.product_id for item in salad.rejected_candidates})


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
        self.assertEqual(matches[0][1]["purchase_quantity_display"], "1 lb")

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

    def test_traditional_pantry_spices_are_non_depleting(self):
        import model

        recipe = {
            "extendedIngredients": [
                {"name": "smoked paprika", "original": "1 teaspoon smoked paprika"},
                {"name": "pepper", "original": "1/2 teaspoon pepper"},
                {"name": "poultry seasoning", "original": "1 teaspoon poultry seasoning"},
                {"name": "celery seed", "original": "1/4 teaspoon celery seed"},
                {"name": "chicken thighs", "original": "2 pound chicken thighs"},
            ]
        }
        adjusted, _originals = model.pantry_adjusted_recipe_ingredients(
            recipe,
            [
                {"name": "smoked paprika", "quantity": "pantry staple"},
                {"name": "black pepper", "quantity": "pantry staple"},
                {"name": "poultry seasoning", "quantity": "pantry staple"},
                {"name": "celery seed", "quantity": "pantry staple"},
            ],
        )
        self.assertEqual(adjusted, ["2 pound chicken thighs"])

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

    def test_prep_only_recipe_fragments_are_not_purchased(self):
        import model

        recipe = {
            "extendedIngredients": [
                {"name": "thinly sliced", "original": "2 cup thinly sliced"},
                {"name": "celery", "original": "1 cup diced celery"},
            ]
        }
        adjusted, _originals = model.pantry_adjusted_recipe_ingredients(recipe, [], servings=4)
        self.assertEqual(adjusted, ["1 cup diced celery"])

    def test_recipe_servings_parses_database_yield(self):
        import model

        self.assertEqual(model.recipe_servings({"yield": "3 - 4 servings"}, 2), 4)
        self.assertEqual(model.recipe_servings({"servings": "6 servings"}, 2), 6)
        self.assertEqual(model.recipe_servings({"servings": 5}, 2), 5)
        self.assertEqual(model.recipe_servings({"servings": "6-8"}, 2), 8)
        self.assertEqual(model.recipe_servings({"yield": "Serves 3"}, 2), 3)
        self.assertEqual(model.recipe_servings({"yield": ""}, 4), 4)
        self.assertEqual(model.source_recipe_servings({"servings": "6-8"}), 8)
        self.assertIsNone(model.source_recipe_servings({"yield": ""}))

    def test_required_quantity_drives_display_grams_not_household_size(self):
        import model

        self.assertEqual(
            model.estimated_grams_from_required_quantity(
                {
                    "base_quantity": 473.176,
                    "base_unit": "milliliter",
                },
                "milk",
            ),
            487,
        )
        self.assertEqual(
            model.estimated_grams_from_required_quantity(
                {
                    "base_quantity": 907.184,
                    "base_unit": "gram",
                },
                "beef",
            ),
            907,
        )

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

    def test_demo_dish_keeps_variable_weight_beef_purchase_row(self):
        import model

        recipe = {
            "id": "beef-steak-pudding-regression",
            "title": "Beef Steak Pudding",
            "sourceUrl": "https://example.test/beef",
            "extendedIngredients": [
                {"name": "beef", "original": "1 pound beef"},
                {"name": "flour", "original": "3/4 pound flour"},
                {"name": "water", "original": "3/4 cup water"},
                {"name": "baking powder", "original": "1 teaspoon baking powder"},
            ],
            "instructions": "Cook.",
        }
        matches = model.match_recipe_ingredients_to_morton_williams(recipe, pantry_items=[], servings=4)
        dish = model.spoonacular_recipe_to_demo_dish(
            recipe,
            matches,
            model.morton_williams_store_lookup(),
            4,
            grocery_label="Morton Williams",
        )
        product_names = [ingredient["product_name"].casefold() for ingredient in dish["ingredients_to_buy"]]
        self.assertTrue(any("beef" in name for name in product_names), product_names)
        self.assertGreater(dish["estimated_price_total"], 4.38)

    def test_recipe_result_displays_source_serving_range(self):
        import model

        recipe = {
            "id": "range-recipe",
            "title": "Range Recipe",
            "servings": "6-8",
            "_snapp_database_recipe": {
                "servings": "6-8",
                "yield": "6-8 servings",
                "source": "Public Domain Recipes",
                "source_url": "https://example.test/range",
            },
            "extendedIngredients": [{"name": "milk", "original": "2 cups milk"}],
            "instructions": "Cook.",
        }
        filters = {
            "servings": 4,
            "dietary_restrictions": "",
            "avoid_ingredients": [],
            "include_ingredients": [],
            "dietary_preference": "",
            "max_cook_time": None,
            "max_budget": None,
        }
        matches = [
            (
                {"name": "milk", "measure": "2 cups milk"},
                {
                    "id": "milk",
                    "ingredient": "milk",
                    "product_name": "Milk",
                    "store_id": "morton-williams",
                    "package_size": "64 fl oz",
                    "package_grams": 1893,
                    "estimated_price_total": 4.0,
                    "required_quantity": {
                        "base_quantity": 473.176,
                        "base_unit": "milliliter",
                    },
                },
            )
        ]

        dish = model.recipe_result_from_recipe(recipe, matches, {}, filters, 10, True)
        self.assertEqual(dish["servings"], 8)
        self.assertEqual(dish["servings_display"], "6-8")
        self.assertEqual(dish["recipe"]["servings_display"], "6-8")

    def test_real_recipe_results_sample_three_exact_candidates(self):
        import model

        recipes = [
            {"id": f"recipe-{index}", "title": f"Recipe {index}", "extendedIngredients": [{"name": "beef"}]}
            for index in range(5)
        ]
        filters = {
            "servings": 4,
            "dietary_restrictions": "",
            "avoid_ingredients": [],
            "include_ingredients": [],
            "dietary_preference": "",
            "max_cook_time": None,
            "max_budget": None,
        }
        fake_products = [({"name": "beef", "measure": "1 pound beef"}, {"id": "beef", "product_name": "Beef"})]

        def fake_result(recipe, _matches, _stores, _filters, relevance_score, exact_match, grocery_label="grocery database"):
            return {
                "recipe_id": recipe["id"],
                "name": recipe["title"],
                "estimated_price_total": 1,
                "relevance_score": relevance_score,
                "exact_match": exact_match,
            }

        with patch("model.collect_recipe_candidates", return_value=recipes), patch(
            "model.match_recipe_ingredients_to_morton_williams", return_value=fake_products
        ), patch("model.recipe_constraint_score", return_value=10), patch(
            "model.recipe_passes_hard_filters", return_value=True
        ), patch("model.recipe_result_from_recipe", side_effect=fake_result), patch(
            "model.random.sample", return_value=[fake_result(recipes[3], fake_products, {}, filters, 10, True), fake_result(recipes[1], fake_products, {}, filters, 10, True), fake_result(recipes[4], fake_products, {}, filters, 10, True)]
        ) as sample:
            results, relaxed = model.build_real_recipe_results("beef", filters, stores={}, result_limit=3)
        self.assertFalse(relaxed)
        sample.assert_called_once()
        self.assertEqual([result["recipe_id"] for result in results], ["recipe-3", "recipe-1", "recipe-4"])

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
