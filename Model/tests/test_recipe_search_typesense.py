import json
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recipe_search_typesense as search  # noqa: E402


SAMPLE_RECIPE = {
    "accepted_stage": "initial",
    "cook_time_min": 25.0,
    "dish_categories": ["main_dish", "stew"],
    "equipment": ["pot"],
    "ingredients": [
        {"name": "beef chuck", "quantity": 1.0, "unit": "pound"},
        {"name": "potatoes", "quantity_text": "2", "unit": "cups"},
    ],
    "instructions": ["Cook the beef and potatoes."],
    "meal_categories": ["lunch_dinner"],
    "prep_time_min": None,
    "servings": None,
    "source_id": "abc-123",
    "source_index": 7,
    "title": "Beef and Potato Stew",
    "total_time_min": 45.0,
}


class RecipeSearchTypesenseTests(unittest.TestCase):
    def test_document_transform_uses_stable_id_and_existing_facts(self):
        document = search.recipe_to_typesense_document(SAMPLE_RECIPE)
        self.assertEqual(document["id"], "abc-123")
        self.assertEqual(document["source_id"], "abc-123")
        self.assertEqual(document["source_index"], 7)
        self.assertEqual(document["title"], "Beef and Potato Stew")
        self.assertEqual(document["normalized_title"], "beef and potato stew")
        self.assertEqual(document["ingredient_names"], ["beef chuck", "potatoes"])
        self.assertEqual(document["categories"], ["lunch_dinner", "main_dish", "stew"])
        self.assertEqual(document["total_time_minutes"], 45)
        self.assertNotIn("meal_type", document)
        self.assertNotIn("cuisine", document)

    def test_stored_detail_does_not_change_search_or_embedding(self):
        recipe = {**SAMPLE_RECIPE, "instructions": ["  First step.  ", "Second step."]}
        document = search.recipe_to_typesense_document(recipe)
        self.assertEqual(document["instructions"], recipe["instructions"])
        self.assertEqual(document["ingredients"], recipe["ingredients"])
        baseline = search.recipe_to_typesense_document({**recipe, "instructions": []})
        self.assertEqual(document["search_text"], baseline["search_text"])
        fields = {field["name"]: field for field in search.typesense_collection_schema()["fields"]}
        self.assertFalse(fields["instructions"]["index"])
        self.assertNotIn("instructions", fields["embedding"]["embed"]["from"])
        self.assertNotIn("instructions", search.KEYWORD_FIELDS)
        hit = search.format_search_hit(1, {"document": document})
        self.assertNotIn("instructions", hit)
        self.assertNotIn("ingredients", hit)

    def test_exact_document_lookup_and_no_search_fallback(self):
        document = search.recipe_to_typesense_document(SAMPLE_RECIPE)
        with mock.patch.object(search, 'typesense_request', return_value=document) as wire:
            self.assertEqual(search.get_recipe_by_id('abc-123')["instructions"], SAMPLE_RECIPE["instructions"])
            self.assertEqual(wire.call_args.args[1], 'GET')
            self.assertTrue(wire.call_args.args[2].endswith('/documents/abc-123'))
        with mock.patch.object(search, 'typesense_request', return_value=document) as wire:
            self.assertIsNone(search.get_recipe_by_id('wrong-id'))
            self.assertEqual(wire.call_count, 1)
        from urllib.error import HTTPError
        with mock.patch.object(search, 'typesense_request', side_effect=HTTPError('fixture', 404, 'missing', {}, None)) as wire:
            self.assertIsNone(search.get_recipe_by_id('missing-id'))
            self.assertEqual(wire.call_count, 1)

    def test_search_text_is_deterministic(self):
        first = search.recipe_to_typesense_document(SAMPLE_RECIPE)["search_text"]
        second = search.recipe_to_typesense_document(SAMPLE_RECIPE)["search_text"]
        self.assertEqual(first, second)
        self.assertIn("Beef and Potato Stew", first)
        self.assertIn("beef chuck", first)

    def test_fallback_document_id_is_deterministic(self):
        recipe = {**SAMPLE_RECIPE, "source_id": "", "source_index": None}
        self.assertEqual(search.stable_document_id(recipe), search.stable_document_id(recipe))

    def test_export_documents_rejects_duplicate_ids(self):
        temp_dir = Path(self.id().replace(".", "_"))
        temp_dir.mkdir(exist_ok=True)
        try:
            corpus = temp_dir / "corpus.jsonl"
            output = temp_dir / "docs.jsonl"
            corpus.write_text(json.dumps(SAMPLE_RECIPE) + "\n" + json.dumps(SAMPLE_RECIPE) + "\n", encoding="utf-8")
            summary = search.export_documents(corpus, output)
            self.assertEqual(summary["processed"], 2)
            self.assertEqual(summary["unique_document_ids"], 1)
            self.assertEqual(summary["duplicate_ids"], ["abc-123"])
        finally:
            for path in temp_dir.glob("*"):
                path.unlink()
            temp_dir.rmdir()

    def test_duration_parser(self):
        query, parsed = search.parse_natural_language_query("beef recipe under 30 minutes")
        self.assertEqual(parsed["max_time"], 30)
        self.assertEqual(query, "recipe")
        self.assertEqual(parsed["include_ingredients"], ["beef"])

    def test_include_and_exclude_ingredient_parser(self):
        _query, parsed = search.parse_natural_language_query("chicken dinner with rice without cheese")
        self.assertEqual(parsed["include_ingredients"], ["rice", "chicken"])
        self.assertEqual(parsed["exclude_ingredients"], ["cheese"])

    def test_conversational_state_merging(self):
        state = search.merge_search_state({}, search.parse_natural_language_query("with chicken")[1])
        self.assertEqual(state.include_ingredients, ["chicken"])
        state = search.merge_search_state(state.to_dict(), search.parse_natural_language_query("under 20 minutes")[1])
        self.assertEqual(state.include_ingredients, ["chicken"])
        self.assertEqual(state.max_time, 20)
        state = search.merge_search_state(state.to_dict(), search.parse_natural_language_query("actually beef")[1])
        self.assertEqual(state.include_ingredients, ["beef"])
        state = search.merge_search_state(state.to_dict(), search.parse_natural_language_query("forget the time limit")[1])
        self.assertIsNone(state.max_time)

    def test_filter_construction(self):
        state = search.SearchState(
            max_time=30,
            min_time=10,
            include_ingredients=["chicken"],
            exclude_ingredients=["cheese"],
            categories=["breakfast"],
            dietary=["vegetarian"],
        )
        filters = search.build_typesense_filter(state)
        for expected in ("total_time_minutes:<=30", "total_time_minutes:>=10",
                         "ingredient_filter_tokens:=", "ingredient_filter_tokens:!=", "`chicken`",
                         "`cheese`", "categories:=`breakfast`", "categories:=`vegetarian`"):
            self.assertIn(expected, filters)


    def test_no_api_key_leakage_in_redaction_helper(self):
        self.assertEqual(search.redact_secret("super-secret"), "[redacted]")
        self.assertEqual(search.redact_secret(""), "")


class RecipeSearchApiTests(unittest.TestCase):
    def setUp(self):
        import model

        self.model = model
        self.client = model.app.test_client()

    def test_api_request_response_behavior(self):
        fake_result = {
            "query": "quick breakfast with eggs",
            "effective_query": "quick breakfast with eggs",
            "parsed_constraints": {"max_time": None, "include_ingredients": [], "exclude_ingredients": [], "categories": ["breakfast"], "dietary": []},
            "state": {"max_time": None, "min_time": None, "include_ingredients": [], "exclude_ingredients": [], "categories": ["breakfast"], "dietary": []},
            "results": [{"id": "1", "title": "Egg Breakfast", "key_ingredients": ["eggs"], "rank": 1}],
            "typesense_latency_ms": 5.0,
            "total_latency_ms": 7.0,
            "found": 1,
            "out_of": 28522,
            "filter_by": "categories:=`breakfast`",
        }
        with mock.patch("recipe_search_typesense.search_recipes", return_value=fake_result):
            response = self.client.post("/api/recipes/search", json={"query": "quick breakfast with eggs", "limit": 10})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["results"][0]["title"], "Egg Breakfast")
        self.assertEqual(payload["state"]["categories"], ["breakfast"])

    def test_missing_typesense_connection_behavior_hides_secret(self):
        with mock.patch(
            "recipe_search_typesense.search_recipes",
            side_effect=search.TypesenseUnavailable("Typesense is unavailable at http://localhost:8108 key=super-secret"),
        ):
            response = self.client.post("/api/recipes/search", json={"query": "rice"})
        self.assertEqual(response.status_code, 503)
        payload_text = response.get_data(as_text=True)
        self.assertIn("Recipe search is temporarily unavailable.", payload_text)
        self.assertNotIn("super-secret", payload_text)


if __name__ == "__main__":
    unittest.main()
