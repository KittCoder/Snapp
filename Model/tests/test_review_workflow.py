import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from review_workflow import mutate_override, require_admin  # noqa: E402


class FakeCache:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class FakeOverrides:
    _data = None
    load_error = None


class FakeService:
    def __init__(self):
        self.overrides = FakeOverrides()
        self.cache = FakeCache()


class ReviewWorkflowTests(unittest.TestCase):
    def test_admin_token_required_and_compared(self):
        with patch.dict(os.environ, {"SNAPP_ADMIN_TOKEN": "secret"}, clear=False):
            ok, _message = require_admin({"X-SNAPP-Admin-Token": "secret"})
            self.assertTrue(ok)
            ok, message = require_admin({"X-SNAPP-Admin-Token": "wrong"})
            self.assertFalse(ok)
            self.assertIn("Invalid", message)

    def test_admin_token_must_be_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            ok, message = require_admin({"X-SNAPP-Admin-Token": "secret"})
            self.assertFalse(ok)
            self.assertIn("configured", message)

    def test_override_mutation_writes_audit_and_clears_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            override_path = Path(directory) / "overrides.json"
            audit_path = Path(directory) / "audit.jsonl"
            override_path.write_text(
                json.dumps(
                    {
                        "version": "test-v1",
                        "forbidden_products": [],
                        "forced_matches": [],
                        "approved_matches": [],
                        "canonical_overrides": [],
                        "aliases": [],
                        "substitutions": [],
                        "incompatible_families": [],
                    }
                ),
                encoding="utf-8",
            )
            service = FakeService()
            with patch("review_workflow.get_product_match_service", return_value=service):
                result = mutate_override(
                    "define_alias",
                    {"query": "caster sugar", "canonical": "sugar", "reason": "common recipe alias"},
                    actor="tester",
                    path=override_path,
                    audit_path=audit_path,
                )
            payload = json.loads(override_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["aliases"][0]["alias"], "caster sugar")
            self.assertTrue(result["version"].startswith("overrides-"))
            self.assertTrue(service.cache.cleared)
            audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(audit_lines), 1)
            self.assertEqual(json.loads(audit_lines[0])["actor"], "tester")

    def test_override_input_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                mutate_override(
                    "define_alias",
                    {"query": "x", "canonical": "", "reason": "missing canonical"},
                    actor="tester",
                    path=Path(directory) / "overrides.json",
                    audit_path=Path(directory) / "audit.jsonl",
                )


if __name__ == "__main__":
    unittest.main()
