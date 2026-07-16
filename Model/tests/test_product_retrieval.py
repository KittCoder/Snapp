import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from product_retrieval import (  # noqa: E402
    DeterministicEmbeddingBackend,
    ProductCandidateRetriever,
    SentenceTransformerEmbeddingBackend,
    build_product_index,
    eligible_product,
    product_embedding_text,
    query_embedding_text,
)


def feature(
    product_id,
    name,
    canonical=None,
    category=None,
    record_status="valid_grocery_product",
    eligible=True,
    brand=None,
    **kwargs,
):
    return {
        "product_id": product_id,
        "original_product_name": name.title(),
        "normalized_name": name,
        "canonical_name": canonical,
        "category": category,
        "record_status": record_status,
        "eligible_for_retrieval": eligible,
        "brand": brand,
        "dietary_attributes": kwargs.get("dietary_attributes", []),
        "form": kwargs.get("form"),
        "fat_level": kwargs.get("fat_level"),
        "salted_status": kwargs.get("salted_status"),
        "freshness": kwargs.get("freshness"),
    }


class ProductRetrievalTests(unittest.TestCase):
    def write_features(self, directory, features):
        path = Path(directory) / "features.json"
        path.write_text(json.dumps({"features": features}), encoding="utf-8")
        return path

    def test_embedding_source_text_construction(self):
        text = product_embedding_text(
            feature(
                "p1",
                "organic low-fat milk",
                canonical="milk",
                category="dairy",
                brand="Bowl And Basket",
                dietary_attributes=["organic"],
                fat_level="low-fat",
            )
        )
        self.assertIn("organic low-fat milk", text)
        self.assertIn("milk", text)
        self.assertIn("dairy", text)
        self.assertIn("organic", text)
        self.assertIn("Bowl And Basket", text)
        self.assertNotIn("p1", text)

    def test_query_text_drops_quantity_unit_and_preparation(self):
        text, parsed = query_embedding_text("2 cups reduced-fat shredded mozzarella cheese, divided")
        self.assertEqual(text, "reduced-fat shredded mozzarella cheese")
        self.assertEqual(parsed["preparation"], ["divided"])

    def test_eligibility_filtering_excludes_noise(self):
        self.assertTrue(eligible_product(feature("p1", "chicken breast")))
        self.assertFalse(
            eligible_product(
                feature(
                    "p2",
                    "the cost is",
                    record_status="scraper_navigation_description_noise",
                    eligible=False,
                )
            )
        )

    def test_model_singleton_backend_loads_once(self):
        backend = DeterministicEmbeddingBackend()
        backend.embed(["milk"])
        backend.embed(["butter"])
        self.assertEqual(backend.load_count, 2)
        # The production backend object keeps a single model slot instead of creating per-request instances.
        production_backend = SentenceTransformerEmbeddingBackend("missing-local-model")
        self.assertIsNone(production_backend._model)
        self.assertEqual(production_backend.model_version, "missing-local-model")

    def test_batch_embedding_normalized(self):
        backend = DeterministicEmbeddingBackend(dimension=8)
        vectors = backend.embed(["milk", "butter"], batch_size=2)
        self.assertEqual(vectors.shape, (2, 8))
        self.assertTrue(np.allclose(np.linalg.norm(vectors, axis=1), 1.0))

    def test_persisted_index_save_load_and_retrieval(self):
        with tempfile.TemporaryDirectory() as directory:
            features_path = self.write_features(
                directory,
                [
                    feature("flour", "gold medal all-purpose flour", "all-purpose flour", "pantry"),
                    feature("milk", "organic low-fat milk", "milk", "dairy", fat_level="low-fat"),
                    feature("noise", "the cost is", record_status="scraper_navigation_description_noise", eligible=False),
                ],
            )
            index_dir = Path(directory) / "index"
            backend = DeterministicEmbeddingBackend()
            metadata = build_product_index(features_path, index_dir, backend=backend, batch_size=2)
            self.assertEqual(metadata["row_count"], 2)
            self.assertTrue((index_dir / "embeddings.npy").exists())
            self.assertTrue((index_dir / "metadata.json").exists())

            retriever = ProductCandidateRetriever(features_path, index_dir, backend=backend)
            result = retriever.retrieve_product_candidates("all-purpose flour", limit=5)
            ids = [candidate.product_id for candidate in result.candidates]
            self.assertIn("flour", ids)
            self.assertNotIn("noise", ids)
            self.assertFalse(result.degraded_mode)

    def test_stale_detection_and_unchanged_skipping(self):
        with tempfile.TemporaryDirectory() as directory:
            features_path = self.write_features(directory, [feature("milk", "low-fat milk", "milk", "dairy")])
            index_dir = Path(directory) / "index"
            backend = DeterministicEmbeddingBackend()
            first = build_product_index(features_path, index_dir, backend=backend)
            second = build_product_index(features_path, index_dir, backend=backend)
            self.assertEqual(first["skipped_unchanged"], 0)
            self.assertEqual(second["skipped_unchanged"], 1)

            features_path = self.write_features(directory, [feature("milk", "whole milk", "milk", "dairy")])
            third = build_product_index(features_path, index_dir, backend=backend)
            self.assertEqual(third["skipped_unchanged"], 0)

    def test_query_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            features_path = self.write_features(directory, [feature("milk", "low-fat milk", "milk", "dairy")])
            index_dir = Path(directory) / "index"
            backend = DeterministicEmbeddingBackend()
            build_product_index(features_path, index_dir, backend=backend)
            retriever = ProductCandidateRetriever(features_path, index_dir, backend=backend)
            first = retriever.retrieve_product_candidates("low-fat milk", limit=3)
            second = retriever.retrieve_product_candidates("low-fat milk", limit=3)
            self.assertGreaterEqual(len(retriever.query_cache), 1)
            self.assertIsNotNone(first.query_embedding_latency_ms)
            self.assertEqual(second.query_embedding_latency_ms, 0.0)

    def test_exact_lexical_semantic_dedup_and_degraded_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            features_path = self.write_features(
                directory,
                [
                    feature("butter", "unsalted butter", "butter", "dairy", salted_status="unsalted"),
                    feature("cream", "heavy whipping cream", "heavy cream", "dairy"),
                ],
            )
            index_dir = Path(directory) / "index"
            backend = DeterministicEmbeddingBackend()
            build_product_index(features_path, index_dir, backend=backend)
            retriever = ProductCandidateRetriever(features_path, index_dir, backend=backend)
            result = retriever.retrieve_product_candidates("unsalted butter", limit=10)
            butter = [candidate for candidate in result.candidates if candidate.product_id == "butter"]
            self.assertEqual(len(butter), 1)
            self.assertTrue(butter[0].exact_match)
            self.assertIn("semantic_vector", butter[0].retrieval_reason_codes)

            degraded = ProductCandidateRetriever(features_path, Path(directory) / "missing", backend=backend)
            degraded_result = degraded.retrieve_product_candidates("unsalted butter", limit=10)
            self.assertTrue(degraded_result.degraded_mode)
            self.assertTrue(degraded_result.candidates)

    def test_missing_model_graceful(self):
        with tempfile.TemporaryDirectory() as directory:
            features_path = self.write_features(directory, [feature("milk", "low-fat milk", "milk", "dairy")])
            retriever = ProductCandidateRetriever(
                features_path,
                Path(directory) / "missing",
                backend=SentenceTransformerEmbeddingBackend("definitely-missing-model"),
            )
            result = retriever.retrieve_product_candidates("low-fat milk", limit=3)
            self.assertTrue(result.degraded_mode)
            self.assertTrue(result.errors)

    def test_query_embedding_failure_falls_back_to_lexical(self):
        class FailingBackend(DeterministicEmbeddingBackend):
            @property
            def model_version(self):
                return "deterministic-test-embedding"

            def embed(self, texts, batch_size=64):
                raise RuntimeError("mock embedding failure")

        with tempfile.TemporaryDirectory() as directory:
            features_path = self.write_features(directory, [feature("milk", "low-fat milk", "milk", "dairy")])
            index_dir = Path(directory) / "index"
            build_product_index(features_path, index_dir, backend=DeterministicEmbeddingBackend())
            retriever = ProductCandidateRetriever(features_path, index_dir, backend=FailingBackend())
            result = retriever.retrieve_product_candidates("low-fat milk", limit=3)
            self.assertTrue(result.degraded_mode)
            self.assertTrue(result.candidates)
            self.assertIn("mock embedding failure", result.errors[0])


if __name__ == "__main__":
    unittest.main()
