"""Stable evidence for catalog-independent identity and package regressions."""
import json
from pathlib import Path
from ingredient_normalization import extract_product_features
from product_compatibility import ProductMatchService
from test_product_compatibility import FakeRetriever

FIXTURE=Path(__file__).parent/'fixtures/recipe_catalog_regression.json'
def fixed_recipe_service():
    rows=[]
    for product in json.loads(FIXTURE.read_text())['products']:
        f=extract_product_features(product);f.update(lexical=1.0,semantic=1.0);rows.append(f)
    return ProductMatchService(retriever=FakeRetriever(rows))
