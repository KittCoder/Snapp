import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parent
PUBLIC_DOMAIN_RECIPES_PATH = MODEL_DIR / "recipes.json"
PUBLIC_DOMAIN_DOTCOM_RECIPES_PATH = MODEL_DIR / "publicdomainrecipes_com.json"
USDA_RECIPES_PATH = MODEL_DIR / "USDA recipes.json"
DEFAULT_OUTPUT_PATH = MODEL_DIR / "all_recipes.json"

RECIPE_FIELDS = (
    "id",
    "name",
    "description",
    "source",
    "source_url",
    "original_usda_url",
    "public_domain",
    "license",
    "author",
    "recipe_by",
    "category",
    "food_groups",
    "tags",
    "yield",
    "servings",
    "servings_source",
    "serving_size",
    "ingredients",
    "equipment",
    "instructions",
    "notes",
    "nutrition",
    "image",
    "date_published",
    "rating",
    "slug",
    "usda_recipe_id",
)

DEFAULT_VALUES = {
    "description": "",
    "original_usda_url": None,
    "license": None,
    "recipe_by": "",
    "food_groups": [],
    "tags": [],
    "serving_size": "",
    "notes": "",
    "nutrition": {},
    "rating": {},
    "slug": None,
    "usda_recipe_id": None,
}

SERVINGS_PATTERNS = (
    re.compile(r"\bservings?\s*:\s*(\d+)\s*(?:-|–|—|to)?\s*(\d+)?\b", re.I),
    re.compile(r"\bserves\s+(\d+)\s*(?:-|–|—|to)?\s*(\d+)?\b", re.I),
    re.compile(r"\byield\s*:\s*(\d+)\s*(?:-|–|—|to)?\s*(\d+)?\s+servings?\b", re.I),
    re.compile(r"\b(\d+)\s*(?:-|–|—|to)\s*(\d+)\s+servings?\b", re.I),
    re.compile(r"\b(\d+)\s+servings?\b", re.I),
)


def load_recipes(path):
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    recipes = data.get("recipes")
    if not isinstance(recipes, list):
        raise RuntimeError(f"{path} does not contain a recipes list.")
    return data, recipes


def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_servings_value(value):
    if isinstance(value, int):
        return value if value > 0 else None
    text = re.sub(r"\s+", " ", str(value or "")).strip().replace("\u2013", "-").replace("\u2014", "-")
    if not text:
        return None
    for pattern in SERVINGS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        first = int(match.group(1))
        second = int(match.group(2)) if match.lastindex and match.lastindex >= 2 and match.group(2) else None
        if second:
            low, high = sorted((first, second))
            return f"{low}-{high}"
        return first
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def servings_from_yield_and_serving_size(yield_value, serving_size):
    yield_text = re.sub(r"\s+", " ", str(yield_value or "")).strip().casefold()
    serving_text = re.sub(r"\s+", " ", str(serving_size or "")).strip().casefold()
    if not yield_text or not serving_text:
        return None
    match = re.match(r"^(\d+)\s+([a-z][a-z\s-]*)$", yield_text)
    if not match:
        return None
    count = int(match.group(1))
    unit = match.group(2).strip()
    singular_unit = unit[:-1] if unit.endswith("s") else unit
    if re.search(rf"\b1\s+{re.escape(singular_unit)}s?\b", serving_text):
        return count
    if re.search(rf"\b1/{count}\s+of\s+recipe\b", serving_text):
        return count
    return None


def dedupe_preserving_order(values):
    seen = set()
    result = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def normalize_recipe(recipe):
    normalized = {}
    for field in RECIPE_FIELDS:
        if field in recipe:
            normalized[field] = recipe[field]
        elif field in DEFAULT_VALUES:
            value = DEFAULT_VALUES[field]
            normalized[field] = value.copy() if isinstance(value, (dict, list)) else value
        else:
            normalized[field] = None

    normalized["author"] = normalize_list(normalized["author"])
    normalized["category"] = normalize_list(normalized["category"])
    normalized["food_groups"] = normalize_list(normalized["food_groups"])
    normalized["tags"] = normalize_list(normalized["tags"])
    normalized["category"] = dedupe_preserving_order([*normalized["category"], *normalized["tags"]])
    normalized["tags"] = dedupe_preserving_order(normalized["tags"])
    normalized["ingredients"] = normalize_list(normalized["ingredients"])
    normalized["equipment"] = normalize_list(normalized["equipment"])
    normalized["instructions"] = normalize_list(normalized["instructions"])
    normalized["public_domain"] = bool(normalized["public_domain"])
    normalized["servings"] = normalize_servings_value(normalized.get("servings"))
    if normalized["servings"] is None:
        normalized["servings"] = normalize_servings_value(normalized.get("yield"))
        if normalized["servings"] is not None and not normalized.get("servings_source"):
            normalized["servings_source"] = "yield"
    if normalized["servings"] is None:
        normalized["servings"] = servings_from_yield_and_serving_size(
            normalized.get("yield"),
            normalized.get("serving_size"),
        )
        if normalized["servings"] is not None and not normalized.get("servings_source"):
            normalized["servings_source"] = "yield_and_serving_size"
    if normalized["servings"] is None:
        raise ValueError("missing source-provided servings")
    return normalized


def merge_recipes(recipe_groups):
    merged = []
    seen_source_urls = set()
    duplicate_source_urls = []
    skipped_missing_servings = []

    for recipes in recipe_groups:
        for recipe in recipes:
            source_url = recipe.get("source_url")
            if source_url and source_url in seen_source_urls:
                duplicate_source_urls.append(source_url)
                continue
            if source_url:
                seen_source_urls.add(source_url)
            try:
                merged.append(normalize_recipe(recipe))
            except ValueError:
                skipped_missing_servings.append(
                    {
                        "name": recipe.get("name"),
                        "source": recipe.get("source"),
                        "source_url": source_url,
                    }
                )

    return merged, duplicate_source_urls, skipped_missing_servings


def write_json(data, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.write("\n")
        temp_name = file.name
    Path(temp_name).replace(output_path)


def main():
    public_domain_data, public_domain_recipes = load_recipes(PUBLIC_DOMAIN_RECIPES_PATH)
    if PUBLIC_DOMAIN_DOTCOM_RECIPES_PATH.exists():
        public_domain_dotcom_data, public_domain_dotcom_recipes = load_recipes(PUBLIC_DOMAIN_DOTCOM_RECIPES_PATH)
    else:
        public_domain_dotcom_data, public_domain_dotcom_recipes = {"metadata": {}}, []
    usda_data, usda_recipes = load_recipes(USDA_RECIPES_PATH)
    merged_recipes, duplicate_source_urls, skipped_missing_servings = merge_recipes(
        [public_domain_recipes, public_domain_dotcom_recipes, usda_recipes]
    )

    database = {
        "metadata": {
            "source": "SNAPP combined recipe database",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "recipe_count": len(merged_recipes),
            "schema_fields": list(RECIPE_FIELDS),
            "inputs": [
                {
                    "path": str(PUBLIC_DOMAIN_RECIPES_PATH.relative_to(MODEL_DIR.parent)),
                    "source": public_domain_data.get("metadata", {}).get("source"),
                    "recipe_count": len(public_domain_recipes),
                },
                {
                    "path": str(PUBLIC_DOMAIN_DOTCOM_RECIPES_PATH.relative_to(MODEL_DIR.parent)),
                    "source": public_domain_dotcom_data.get("metadata", {}).get("source"),
                    "recipe_count": len(public_domain_dotcom_recipes),
                },
                {
                    "path": str(USDA_RECIPES_PATH.relative_to(MODEL_DIR.parent)),
                    "source": usda_data.get("metadata", {}).get("source"),
                    "recipe_count": len(usda_recipes),
                },
            ],
            "duplicate_source_urls_skipped": duplicate_source_urls,
            "missing_servings_skipped": skipped_missing_servings,
            "notes": [
                "This file is generated by merge_recipe_databases.py.",
                "Source recipe files are not modified by the merge.",
                "Every recipe is normalized to the same schema; unavailable source-specific fields use null, empty strings, empty lists, or empty objects.",
                "Every included recipe has a source-derived servings value as either a single number or a range string.",
            ],
        },
        "recipes": merged_recipes,
    }
    write_json(database, DEFAULT_OUTPUT_PATH)
    print(f"Wrote {len(merged_recipes)} recipes to {DEFAULT_OUTPUT_PATH}.")
    if duplicate_source_urls:
        print(f"Skipped {len(duplicate_source_urls)} duplicate source URLs.")
    if skipped_missing_servings:
        print(f"Skipped {len(skipped_missing_servings)} recipes without source serving data.")


if __name__ == "__main__":
    main()
