#!/usr/bin/env python3
"""Replay fixed local recipe fixtures through the final shopping API adapter.

Before runs use source snapshots in the audit directory. This is a diagnostic
comparison, not a human QA holdout or a matcher answer key.
"""
import argparse
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Model'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/matcher_shopping_path_audit')
    args = parser.parse_args()
    if args.phase == 'before':
        for name in ('food_identity_rules', 'product_ontology', 'recipe_ingredient_adapter', 'basket_quantity', 'model'):
            module = types.ModuleType(name)
            module.__file__ = str(ROOT / 'Model' / (name + '.py'))
            sys.modules[name] = module
            exec(compile((args.output / (name + '.py.before')).read_text(), module.__file__, 'exec'), module.__dict__)
    import model
    rows = []
    service = model.basket_builder_match_service()
    original_match = service.match_recipe_ingredients
    trace = []
    def traced_match(texts, **kwargs):
        results = original_match(texts, **kwargs)
        trace.extend({'query': text, 'result': result.to_dict()} for text, result in zip(texts, results))
        return results
    service.match_recipe_ingredients = traced_match
    for recipe in json.loads((args.output / 'recipes.json').read_text()):
        trace.clear()
        __import__('basket_quantity').get_basket_builder().clear_caches()
        matches = model.match_recipe_ingredients_to_morton_williams(recipe, pantry_items=[], servings=recipe.get('servings'))
        rows.append({'recipe': recipe.get('name', recipe.get('title')), 'source': recipe.get('source_url'),
                     'augmentation': recipe.get('audit_augmentation'), 'inputs': recipe.get('ingredients'), 'matcher_trace': list(trace),
                     'purchase_rows': [{'ingredient': ingredient, 'product': product['product_name']} for ingredient, product in matches]})
    (args.output / ('recipes_' + args.phase + '.json')).write_text(json.dumps(rows, indent=2) + '\n')
    print([(row['recipe'], len(row['purchase_rows'])) for row in rows])


if __name__ == '__main__':
    main()
