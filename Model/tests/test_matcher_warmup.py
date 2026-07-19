import importlib
import sys
import threading
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

    def safe_dict(self):
        return {"ok": self.ok, "status": self.status, "errors": [], "warnings": [], "manifest": self.manifest}


class MatcherWarmupTests(unittest.TestCase):
    def setUp(self):
        matcher_warmup.reset_for_tests()

    def test_readiness_false_before_warmup_and_true_after(self):
        service = FakeService()
        self.assertEqual(matcher_warmup.get_warmup_status().status, "not_started")
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

    def test_status_returns_fresh_copy_not_shared_state(self):
        service = FakeService()
        first_state_id = id(matcher_warmup._MANAGER._state)
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()):
            ready_snapshot = matcher_warmup.warmup_matcher()
        self.assertEqual(id(matcher_warmup._MANAGER._state), first_state_id)
        self.assertNotEqual(id(ready_snapshot), first_state_id)
        ready_snapshot.status = "mutated"
        self.assertEqual(matcher_warmup.get_warmup_status().status, "ready")

    def test_exactly_one_manager_is_created_for_imported_worker(self):
        manager_id = id(matcher_warmup._MANAGER)
        state_id = id(matcher_warmup._MANAGER._state)
        with patch.dict("os.environ", {"SNAPP_DISABLE_MATCHER_WARMUP": "1"}):
            app_module = importlib.import_module("model")
        self.assertIs(app_module.matcher_warmup._MANAGER, matcher_warmup._MANAGER)
        self.assertEqual(id(matcher_warmup._MANAGER), manager_id)
        self.assertEqual(id(matcher_warmup._MANAGER._state), state_id)

    def test_ready_route_reads_same_warmup_module_state(self):
        with patch.dict("os.environ", {"SNAPP_DISABLE_MATCHER_WARMUP": "1"}):
            app_module = importlib.import_module("model")
        self.assertIs(app_module.matcher_warmup, matcher_warmup)
        self.assertIs(app_module.matcher_warmup._MANAGER, matcher_warmup._MANAGER)
        state_id = id(matcher_warmup._MANAGER._state)
        service = FakeService()
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()), patch.object(
            app_module, "validate_runtime_artifacts", return_value=FakeValidation()
        ):
            matcher_warmup.warmup_matcher()
            response = app_module.app.test_client().get("/ready")
        self.assertEqual(id(matcher_warmup._MANAGER._state), state_id)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["semantic_readiness"], "ready")
        self.assertTrue(payload["artifact_validation_ok"])
        self.assertTrue(payload["artifact_validation"]["ok"])

    def test_gunicorn_style_model_import_does_not_create_duplicate_warmup_module(self):
        with patch.dict("os.environ", {"SNAPP_DISABLE_MATCHER_WARMUP": "1"}):
            app_module = importlib.import_module("model")
        self.assertIs(app_module.matcher_warmup, matcher_warmup)
        self.assertNotIn("Model.matcher_warmup", sys.modules)
        self.assertEqual(matcher_warmup.module_diagnostics()["duplicate_module_keys"], [])

    def test_application_import_order_does_not_split_state_or_reset_ready(self):
        with patch.dict("os.environ", {"SNAPP_DISABLE_MATCHER_WARMUP": "1"}):
            app_module = importlib.import_module("model")
        service = FakeService()
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()):
            matcher_warmup.warmup_matcher()
        state_id = id(matcher_warmup._MANAGER._state)
        app_module.matcher_warmup.start_background_warmup()
        self.assertEqual(id(matcher_warmup._MANAGER._state), state_id)
        self.assertEqual(matcher_warmup.get_warmup_status().status, "ready")

    def test_status_snapshots_reflect_updates_from_another_thread(self):
        service = FakeService()
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()):
            thread = threading.Thread(target=matcher_warmup.warmup_matcher)
            thread.start()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(matcher_warmup.get_warmup_status().status, "ready")

    def test_completed_state_remains_ready_across_repeated_ready_requests(self):
        with patch.dict("os.environ", {"SNAPP_DISABLE_MATCHER_WARMUP": "1"}):
            app_module = importlib.import_module("model")
        service = FakeService()
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()), patch.object(
            app_module, "validate_runtime_artifacts", return_value=FakeValidation()
        ):
            matcher_warmup.warmup_matcher()
            client = app_module.app.test_client()
            responses = [client.get("/ready") for _ in range(3)]
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(all(response.get_json()["status"] == "ready" for response in responses))

    def test_background_warmup_completion_makes_ready_return_200(self):
        with patch.dict("os.environ", {"SNAPP_DISABLE_MATCHER_WARMUP": "1"}):
            app_module = importlib.import_module("model")
        service = FakeService()
        with patch.object(matcher_warmup, "validate_runtime_artifacts", return_value=FakeValidation()), patch.object(
            matcher_warmup, "get_product_match_service", return_value=service
        ), patch.object(matcher_warmup, "get_basket_builder", return_value=object()), patch.object(
            app_module, "validate_runtime_artifacts", return_value=FakeValidation()
        ):
            matcher_warmup.start_background_warmup()
            matcher_warmup._MANAGER._thread.join(timeout=5)
            response = app_module.app.test_client().get("/ready")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["warmup_completed"])
        self.assertEqual(payload["artifact_validation_status"], payload["artifact_validation"]["status"])

    def test_duplicate_module_condition_is_detected(self):
        original = sys.modules.get("Model.matcher_warmup")
        sys.modules["Model.matcher_warmup"] = matcher_warmup
        try:
            diagnostics = matcher_warmup.module_diagnostics(include_private_ids=True)
        finally:
            if original is None:
                sys.modules.pop("Model.matcher_warmup", None)
            else:
                sys.modules["Model.matcher_warmup"] = original
        self.assertIn("Model.matcher_warmup", diagnostics["duplicate_module_keys"])


if __name__ == "__main__":
    unittest.main()
