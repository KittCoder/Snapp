"""Cached display-only recipe localization; canonical facts stay untouched."""
from copy import deepcopy
from functools import lru_cache
import json
import re
from pathlib import Path
from recipe_chat_multilingual import locale_code, translation_provider as configured_translation_provider
from recipe_line_translator import valid_translation
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile

# Initial Spanish ingredient display support. Quantities/units are retained
# verbatim; no product/brand names enter this translator.
SPANISH_INGREDIENTS={
 'chicken':'pollo','beef':'carne de res','turkey':'pavo','rice':'arroz',
 'cheese':'queso','cheddar cheese':'queso cheddar','provolone cheese':'queso provolone',
 'eggs':'huevos','egg':'huevo','milk':'leche','tomatoes':'tomates','tomato':'tomate',
 'onions':'cebollas','onion':'cebolla','garlic':'ajo','broccoli':'brócoli',
 'spinach':'espinaca','salt':'sal','black pepper':'pimienta negra','pepper':'pimienta',
 'olive oil':'aceite de oliva','vegetable oil':'aceite vegetal','butter':'mantequilla',
 'water':'agua','flour':'harina','sugar':'azúcar','potatoes':'papas','potato':'papa',
 'carrots':'zanahorias','carrot':'zanahoria','mushrooms':'champiñones','beans':'frijoles',
 'black beans':'frijoles negros','pasta':'pasta','lemon':'limón','parsley':'perejil',
 'cilantro':'cilantro','soy sauce':'salsa de soya','chicken broth':'caldo de pollo',
 'beef broth':'caldo de res','vegetable broth':'caldo de verduras','cream':'crema',
}

CACHE_DIRECTORY = Path(__file__).resolve().parent/'recipe_chat_translations'


def static_recipe_cache(locale):
    # Read the file again when another process finishes a translation batch.
    path = CACHE_DIRECTORY/f'{locale}.json'
    try:
        signature = (path.stat().st_mtime_ns, path.stat().st_size)
    except OSError:
        return {}
    return _read_static_cache(str(path), signature)


@lru_cache(maxsize=48)
def _read_static_cache(path, signature):
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def cached_text(recipe_id, locale, field, text):
    candidate = static_recipe_cache(locale).get(recipe_id, {}).get(field, {}).get(text.strip())
    if valid_translation(text, candidate):
        return candidate
    return None


@lru_cache(maxsize=1)
def default_recipe_translator():
    from recipe_line_translator import RecipeLineTranslator
    return RecipeLineTranslator()


def translation_provider():
    return configured_translation_provider() or default_recipe_translator()


def spanish_ingredient(line):
    # Only a whole known identity at the end of a quantity/unit prefix is changed.
    # Compound, branded or prepared ingredients fall back to original English.
    for name in sorted(SPANISH_INGREDIENTS,key=len,reverse=True):
        match=re.fullmatch(r'(.*?)\b'+re.escape(name)+r'\s*',line,re.I)
        if match and re.fullmatch(r'[\d\s./¼½¾⅓⅔⅛⅜⅝⅞-]*(?:(?:cups?|tbsp|tsp|tablespoons?|teaspoons?|oz|ounces?|pounds?|lbs?|slices?|cans?|cloves?|grams?|g|ml|liters?|kg|pinch|pinches)\s*(?:of\s*)?)?',match[1],re.I):
            return match[1]+SPANISH_INGREDIENTS[name]
    return line

def _save_lines(recipe_id, locale, additions):
    if not additions:
        return
    # Serialize writers across Flask threads and local server processes.
    import fcntl
    CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIRECTORY/f'{locale}.json'
    with (CACHE_DIRECTORY/f'.{locale}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = deepcopy(static_recipe_cache(locale))
        recipe = data.setdefault(recipe_id, {})
        for field, original, translated in additions:
            recipe.setdefault(field, {})[original.strip()] = translated
        fd, temporary = tempfile.mkstemp(dir=CACHE_DIRECTORY, prefix=f'.{locale}-')
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write('\n')
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def localize_detail(recipe_id, detail, locale):
    locale = locale_code(locale)
    if locale == 'en':
        return None
    localized = deepcopy(detail)
    lines = []
    for field in ('name', 'title'):
        if isinstance(detail.get(field), str) and detail[field].strip():
            lines.append((field, detail[field], lambda value, field=field: localized.__setitem__(field, value)))
    for item in localized.get('ingredients', []):
        original = item.get('display') or item.get('measure') or item.get('name') or ''
        if original.strip():
            lines.append(('ingredients', original, lambda value, item=item: item.__setitem__('display', value)))
    for field in ('ingredients_text', 'ingredient_names', 'key_ingredients', 'equipment'):
        for index, original in enumerate(detail.get(field) or []):
            if isinstance(original, str) and original.strip():
                cache_field = 'ingredients' if field in ('ingredients_text', 'ingredient_names', 'key_ingredients') else field
                lines.append((cache_field, original, lambda value, field=field, index=index: localized[field].__setitem__(index, value)))
    instructions = detail.get('instructions')
    originals = instructions if isinstance(instructions, list) else instructions.splitlines() if isinstance(instructions, str) else []
    steps = list(originals)
    for index, original in enumerate(originals):
        if isinstance(original, str) and original.strip():
            lines.append(('instructions', original, lambda value, index=index: steps.__setitem__(index, value)))
    provider = translation_provider()
    additions = []
    batch_translations = {}
    if provider and callable(getattr(provider, 'translate_many', None)):
        missing = list(dict.fromkeys(original for field, original, _ in lines
                                    if cached_text(recipe_id, locale, field, original) is None))
        batches, batch, size = [], [], 0
        for text in missing:
            length = len(quote(text)) + 100
            if batch and size + length > 4000:
                batches.append(batch)
                batch, size = [], 0
            batch.append(text)
            size += length
        if batch:
            batches.append(batch)
        def translate_batch(texts):
            try:
                candidates = provider.translate_many(texts, source='en', target=locale)
                if len(candidates) == len(texts):
                    return dict(zip(texts, candidates))
            except Exception:
                pass
            return dict.fromkeys(texts)
        with ThreadPoolExecutor(max_workers=3) as executor:
            for translated_batch in executor.map(translate_batch, batches):
                batch_translations.update(translated_batch)
    def translate(line):
        field, original, setter = line
        candidate = cached_text(recipe_id, locale, field, original)
        if candidate is None and provider:
            try:
                candidate = batch_translations[original] if original in batch_translations else provider.translate(original, source='en', target=locale)
                if not valid_translation(original, candidate):
                    candidate = None
                elif candidate:
                    return line, candidate, True
            except Exception:
                candidate = None
        return line, candidate, False
    with ThreadPoolExecutor(max_workers=8) as executor:
        translated = list(executor.map(translate, lines))
    completed = 0
    instructions_complete = True
    for (field, original, setter), candidate, fresh in translated:
        if candidate:
            setter(candidate)
            completed += 1
            if fresh:
                additions.append((field, original, candidate))
        else:
            if field == 'instructions':
                instructions_complete = False
            if locale == 'es' and field == 'ingredients':
                setter(spanish_ingredient(original))
    if instructions is not None:
        localized['instructions'] = steps if isinstance(instructions, list) else '\n'.join(steps)
    _save_lines(recipe_id, locale, additions)
    localized['_locale'] = locale
    localized['_translation_status'] = 'translated' if completed == len(lines) else 'partial' if completed else 'original'
    localized['_instructions_locale'] = locale if instructions_complete else 'en'
    return localized
