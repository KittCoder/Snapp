import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matcher_warmup  # noqa: E402


class FakeBackend:
    load_error = None

    def __init__(self):
        self.load_count = 0

    def load(self):
        self.load_count += 1
        return self


class FakeRetriever:
    def __init__(self):
        self.backend = FakeBackend()
        self.load_index_count = 0

    @property
    def features(self):
        return [{"product_id": "milk"}]

    @property
    def eligible_features(self):
        return self.features

    @property
    def lexical_docs(self):
        return []

    def lexical_indexes(self):
        return {}, {}

    def load_index(self):
        self.load_index_count += 1
        return True


class FakeOverrides:
    version = "test-overrides"


class FakeService:
    def __init__(self):
        self.retriever = FakeRetriever()
        self.overrides = FakeOverrides()
        self.match_calls = 0

    def match_recipe_ingredients(self, queries):
        self.match_calls += 1
        return []


class FakeValidation:
    ok = True
    status = "ready"
    errors = []
    manifest = {"index_hash": "test-index"}


class MatcherWarmupTests(unittest.TestCase):
    def setUp(self):
        matcher_warmup._state = matcher_warmup.WarmupState()
        matcher_warmup._thread = None

    def test_readiness_false_before_warmup_and_true_after(self):
        service = FakeService()
        self.assertEqual(matcher_warmup.warmup_status().status, "not_started")
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()):
            state = matcher_warmup.warmup_matcher()
        self.assertEqual(state.status, "ready")
        self.assertTrue(state.warmup_completed)
        self.assertTrue(state.model_loaded)
        self.assertTrue(state.index_loaded)

    def test_repeated_warmup_does_not_reload_components(self):
        service = FakeService()
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()):
            matcher_warmup.warmup_matcher()
            matcher_warmup.warmup_matcher()
        self.assertEqual(service.retriever.load_index_count, 1)
        self.assertEqual(service.retriever.backend.load_count, 1)
        self.assertEqual(service.match_calls, 1)


if __name__ == "__main__":
    unittest.main()
