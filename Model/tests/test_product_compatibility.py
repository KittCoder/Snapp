import json
import sys
import tempfile
import unittest
from pathlib import Path
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
