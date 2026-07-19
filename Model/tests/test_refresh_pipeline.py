import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from refresh_morton_williams_artifacts import promote_dir, validate_source_schema  # noqa: E402


class RefreshPipelineTests(unittest.TestCase):
    def test_source_schema_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database.merged.json"
            path.write_text(json.dumps({"products": [{"name": "Milk"}]}), encoding="utf-8")
            self.assertEqual(validate_source_schema(path)["product_rows"], 1)
            path.write_text(json.dumps({"products": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_source_schema(path)

    def test_failed_directory_promotion_restores_active_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active"
            staged = root / "staged"
            active.mkdir()
            staged.mkdir()
            (active / "marker.txt").write_text("active", encoding="utf-8")
            (staged / "marker.txt").write_text("staged", encoding="utf-8")
            with patch("refresh_morton_williams_artifacts.os.replace", side_effect=[None, RuntimeError("mock failure"), None]):
                with self.assertRaises(RuntimeError):
                    promote_dir(staged, active)
            self.assertEqual((active / "marker.txt").read_text(encoding="utf-8"), "active")


if __name__ == "__main__":
    unittest.main()
