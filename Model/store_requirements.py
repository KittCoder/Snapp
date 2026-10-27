"""Lossless recipe requirements shared by chat and combined store baskets."""
import math
import re
from recipe_ingredient_adapter import canonical_recipe_ingredients, ingredient_with_quantity
from store_catalogs import CatalogError


def prepare_recipes(recipes, pantry_items=None):
    # Reuse SNAPP's configured non-depleting spices and quantity-aware pantry buckets.
    from model import (pantry_quantity_buckets, pantry_spice_keys,
                       pantry_adjusted_ingredient_text, should_buy_recipe_ingredient)
    if pantry_items is not None and (not isinstance(pantry_items, list) or len(pantry_items)>200 or any(not isinstance(p, dict) or not isinstance(p.get('name'), str) or len(str(p))>4000 for p in pantry_items)):
        raise CatalogError('Invalid pantry items')
    buckets = pantry_quantity_buckets(pantry_items or [])
    spices = pantry_spice_keys(pantry_items or [])
    prepared, pantry = [], []
    for recipe in recipes:
        source = recipe.get('source_servings') or recipe.get('servings')
        target = recipe.get('target_servings')
        multiplier = 1.0
        if target is not None:
            try:
                source, target = float(source), float(target)
                if not all(math.isfinite(x) and 0 < x <= 1000 for x in (source, target)):
                    raise ValueError()
                multiplier = target / source
            except (ValueError, TypeError):
                raise CatalogError('Scaling requires positive source and target servings')
        lines = []
        for item in canonical_recipe_ingredients(recipe):
            text = item.raw_text if item.source_schema == 'raw_text_line' else item.matcher_text
            if multiplier != 1 and item.quantity is not None:
                text = ingredient_with_quantity(text, item.quantity * multiplier, item.unit)
            ingredient = {'name': item.ingredient_name, 'display': text}
            # Tap water is not a purchase; explicitly bottled water still is.
            water = bool(re.fullmatch(r'(?:tap |cold |warm |hot |boiling |fresh )*water', item.ingredient_name.lower()))
            buy = should_buy_recipe_ingredient(ingredient) or ('water' in item.ingredient_name.lower() and not water)
            adjusted = pantry_adjusted_ingredient_text(ingredient, buckets, spices) if buy and not water else None
            if adjusted:
                lines.append(adjusted)
            else:
                pantry.append(text)
        prepared.append({'id': recipe.get('id'), 'name': recipe.get('name') or recipe.get('title'),
                         'ingredients': lines, 'source_servings': target or source, 'target_servings': None})
    return prepared, list(dict.fromkeys(pantry))
