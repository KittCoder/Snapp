import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_manifest import validate_runtime_artifacts, write_manifest  # noqa: E402
from product_retrieval import DeterministicEmbeddingBackend, build_product_index  # noqa: E402


def feature(product_id, name):
    return {
        "product_id": product_id,
        "original_product_name": name.title(),
        "normalized_name": name,
        "canonical_name": name,
        "category": "pantry",
        "record_status": "valid_grocery_product",
        "eligible_for_retrieval": True,
    }


class ArtifactManifestTests(unittest.TestCase):
    def write_features(self, directory, features):
        path = Path(directory) / "features.json"
        path.write_text(
            json.dumps(
                {
                    "metadata": {"feature_extraction_version": "test-features"},
                    "features": features,
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_source(self, directory):
        path = Path(directory) / "database.merged.json"
        path.write_text(json.dumps({"products": [{"name": "milk"}]}), encoding="utf-8")
        return path

    def test_valid_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = self.write_source(directory)
            features_path = self.write_features(directory, [feature("milk", "milk")])
            index_dir = Path(directory) / "index"
            build_product_index(features_path, index_dir, backend=DeterministicEmbeddingBackend())
            manifest_path = Path(directory) / "manifest.json"
            write_manifest(
                path=manifest_path,
                source_path=source_path,
                features_path=features_path,
                index_dir=index_dir,
                generation_command="test",
            )
            result = validate_runtime_artifacts(
                manifest_path=manifest_path,
                source_path=source_path,
                features_path=features_path,
                index_dir=index_dir,
                expected_model_name="deterministic-test-embedding",
            )
            self.assertTrue(result.ok, result.errors)

    def test_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = self.write_source(directory)
            features_path = self.write_features(directory, [feature("milk", "milk")])
            index_dir = Path(directory) / "index"
            build_product_index(features_path, index_dir, backend=DeterministicEmbeddingBackend())
            manifest_path = Path(directory) / "manifest.json"
            write_manifest(path=manifest_path, source_path=source_path, features_path=features_path, index_dir=index_dir)
            features_path.write_text(json.dumps({"metadata": {"feature_extraction_version": "test-features"}, "features": [feature("butter", "butter")]}), encoding="utf-8")
            result = validate_runtime_artifacts(
                manifest_path=manifest_path,
                source_path=source_path,
                features_path=features_path,
                index_dir=index_dir,
                expected_model_name="deterministic-test-embedding",
            )
            self.assertFalse(result.ok)
            self.assertTrue(any("normalized_feature_hash" in error for error in result.errors))

    def test_row_count_and_dimension_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = self.write_source(directory)
            features_path = self.write_features(directory, [feature("milk", "milk")])
            index_dir = Path(directory) / "index"
            build_product_index(features_path, index_dir, backend=DeterministicEmbeddingBackend())
            manifest_path = Path(directory) / "manifest.json"
            write_manifest(path=manifest_path, source_path=source_path, features_path=features_path, index_dir=index_dir)
            np.save(index_dir / "embeddings.npy", np.zeros((2, 8), dtype=np.float32))
            result = validate_runtime_artifacts(
                manifest_path=manifest_path,
                source_path=source_path,
                features_path=features_path,
                index_dir=index_dir,
                expected_model_name="deterministic-test-embedding",
            )
            self.assertFalse(result.ok)
            self.assertTrue(any("row count" in error or "dimension" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
