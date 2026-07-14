import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


MYPLATE_BASE_URL = os.getenv("MYPLATE_FOOD_BASE_URL", "https://myplate.food").rstrip("/")
RECIPES_INDEX_URL = f"{MYPLATE_BASE_URL}/recipes"
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("USDA recipes.json")
DEFAULT_MAX_RECIPES = int(os.getenv("USDA_MYPLATE_MAX_RECIPES", "1072"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("USDA_MYPLATE_TIMEOUT_SECONDS", "20"))
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"

SPACE_PATTERN = re.compile(r"\s+")
TAG_PATTERN = re.compile(r"<[^>]+>")

UNITS = {
    "bag",
    "bags",
    "bottle",
    "bottles",
    "box",
    "boxes",
    "bunch",
    "bunches",
    "can",
    "cans",
    "clove",
    "cloves",
    "cup",
    "cups",
    "dash",
    "dashes",
    "drop",
    "drops",
    "gallon",
    "gallons",
    "gram",
    "grams",
    "lb",
    "lbs",
    "ounce",
    "ounces",
    "oz",
    "package",
    "packages",
    "packet",
    "packets",
    "piece",
    "pieces",
    "pinch",
    "pint",
    "pints",
    "pound",
    "pounds",
    "quart",
    "quarts",
    "slice",
    "slices",
    "sprig",
    "sprigs",
    "stalk",
    "stalks",
    "tablespoon",
    "tablespoons",
    "tbsp",
    "teaspoon",
    "teaspoons",
    "tsp",
}


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.jsonld_scripts = []
        self.recipe_data = None
        self._active = None
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "script":
            return
        attr_map = {name.casefold(): value for name, value in attrs}
        script_type = (attr_map.get("type") or "").casefold()
        script_id = attr_map.get("id")
        if script_type == "application/ld+json":
            self._active = "jsonld"
            self._buffer = []
        elif script_id == "recipe-data" and script_type == "application/json":
            self._active = "recipe-data"
            self._buffer = []

    def handle_endtag(self, tag):
        if tag.casefold() != "script" or not self._active:
            return
        text = "".join(self._buffer).strip()
        if self._active == "jsonld":
            self.jsonld_scripts.append(text)
        elif self._active == "recipe-data":
            self.recipe_data = text
        self._active = None
        self._buffer = []

    def handle_data(self, data):
        if self._active:
            self._buffer.append(data)


def clean_text(value):
    return SPACE_PATTERN.sub(" ", unescape(TAG_PATTERN.sub("", str(value or "")))).strip()


def fetch_text(url):
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"MyPlate recipe request failed for {url}: {exc}") from exc


def load_scripts(html):
    parser = ScriptParser()
    parser.feed(html)
    jsonld = []
    for script in parser.jsonld_scripts:
        if not script:
            continue
        try:
            jsonld.append(json.loads(unescape(script)))
        except json.JSONDecodeError:
            continue
    recipe_data = None
    if parser.recipe_data:
        try:
            recipe_data = json.loads(unescape(parser.recipe_data))
        except json.JSONDecodeError:
            recipe_data = None
    return jsonld, recipe_data


def iter_jsonld(value):
    if isinstance(value, list):
        for item in value:
            yield from iter_jsonld(item)
    elif isinstance(value, dict):
        yield value
        for key in ("@graph", "mainEntity", "itemListElement"):
            yield from iter_jsonld(value.get(key))


def jsonld_type(value):
    item_type = value.get("@type") if isinstance(value, dict) else None
    return {str(item).casefold() for item in item_type} if isinstance(item_type, list) else {str(item_type).casefold()}


def discover_recipe_urls():
    html = fetch_text(RECIPES_INDEX_URL)
    jsonld, _recipe_data = load_scripts(html)
    urls = []
    seen = set()
    expected_count = None
    for document in jsonld:
        for item in iter_jsonld(document):
            if "itemlist" not in jsonld_type(item):
                continue
            expected_count = item.get("numberOfItems") or expected_count
            for list_item in item.get("itemListElement") or []:
                url = list_item.get("url") if isinstance(list_item, dict) else None
                if not url:
                    continue
                absolute = urljoin(f"{MYPLATE_BASE_URL}/", url)
                if absolute not in seen:
                    urls.append(absolute)
                    seen.add(absolute)
    if not urls:
        raise RuntimeError("No USDA MyPlate recipe URLs were found on the recipe index.")
    return urls, expected_count


def recipe_schema_from_jsonld(documents):
    for document in documents:
        for item in iter_jsonld(document):
            if "recipe" in jsonld_type(item):
                return item
    return {}


def normalize_quantity_text(value):
    return (
        str(value or "")
        .replace("\u00bc", "1/4")
        .replace("\u00bd", "1/2")
        .replace("\u00be", "3/4")
    )


def parse_quantity_and_name(raw_ingredient, explicit_note=None):
    text = clean_text(raw_ingredient)
    note = clean_text(explicit_note) or None
    note_match = re.search(r"\(([^)]+)\)", text)
    if note_match:
        note = note or clean_text(note_match.group(1))

    normalized = SPACE_PATTERN.sub(" ", normalize_quantity_text(text))
    match = re.match(
        r"^(?P<quantity>\d+(?:\.\d+)?(?:/\d+)?(?:\s+\d+/\d+)?)\s*(?P<rest>.*)$",
        normalized,
    )
    if not match:
        name, trailing_note = split_ingredient_note(normalized)
        return {
            "name": name,
            "quantity": None,
            "unit": None,
            "note": note or trailing_note,
            "raw": text,
        }

    quantity = match.group("quantity")
    rest = match.group("rest").strip()
    words = rest.split()
    unit = None
    if words and words[0].casefold().rstrip(".") in UNITS:
        unit = words.pop(0).rstrip(".")
    name, trailing_note = split_ingredient_note(" ".join(words))
    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "note": note or trailing_note,
        "raw": text,
    }


def split_ingredient_note(value):
    value = clean_text(value)
    if "," not in value:
        return value, None
    name, note = value.split(",", 1)
    return clean_text(name), clean_text(note) or None


def parse_ingredients(recipe_data, recipe_schema):
    ingredients = []
    source_ingredients = recipe_data.get("ingredients") if isinstance(recipe_data, dict) else None
    if source_ingredients:
        for ingredient in source_ingredients:
            if isinstance(ingredient, dict):
                text = ingredient.get("text")
                note = ingredient.get("note")
            else:
                text = ingredient
                note = None
            if clean_text(text):
                ingredients.append(parse_quantity_and_name(text, note))
        return ingredients

    for ingredient in recipe_schema.get("recipeIngredient") or []:
        if clean_text(ingredient):
            ingredients.append(parse_quantity_and_name(ingredient))
    return ingredients


def parse_instructions(recipe_data, recipe_schema):
    directions = recipe_data.get("directions") if isinstance(recipe_data, dict) else None
    if directions:
        return [clean_text(part) for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", directions) if clean_text(part)]

    instructions = []
    for step in recipe_schema.get("recipeInstructions") or []:
        if isinstance(step, dict):
            text = clean_text(step.get("text") or step.get("name"))
        else:
            text = clean_text(step)
        if text:
            instructions.append(text)
    return instructions


def image_from_schema(value):
    if isinstance(value, str):
        return value or None
    if isinstance(value, list) and value:
        return image_from_schema(value[0])
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    return None


def author_name(value):
    if isinstance(value, dict):
        return clean_text(value.get("name"))
    return clean_text(value)


def stable_recipe_id(url, name):
    return hashlib.sha256((url or name).encode("utf-8")).hexdigest()[:16]


def normalize_recipe(url, recipe_data, recipe_schema):
    name = clean_text((recipe_data or {}).get("name") or recipe_schema.get("name"))
    source_url = url
    usda_url = clean_text((recipe_data or {}).get("url") or recipe_schema.get("isBasedOn"))
    ingredients = parse_ingredients(recipe_data or {}, recipe_schema)
    instructions = parse_instructions(recipe_data or {}, recipe_schema)
    food_groups = (recipe_data or {}).get("food_groups") or []
    category = clean_text(recipe_schema.get("recipeCategory"))
    if not category and food_groups:
        category = ", ".join(clean_text(group.get("label")) for group in food_groups if group.get("label"))

    if not name or not ingredients or not instructions:
        raise RuntimeError(f"Recipe page did not include enough recipe data: {url}")

    return {
        "id": stable_recipe_id(source_url, name),
        "usda_recipe_id": (recipe_data or {}).get("usda_recipe_id"),
        "slug": (recipe_data or {}).get("slug"),
        "name": name,
        "description": clean_text((recipe_data or {}).get("description") or recipe_schema.get("description")),
        "source": "USDA MyPlate Kitchen",
        "source_url": source_url,
        "original_usda_url": usda_url or None,
        "public_domain": True,
        "license": recipe_schema.get("license") or "https://creativecommons.org/publicdomain/mark/1.0/",
        "author": [author_name(recipe_schema.get("author")) or "USDA Center for Nutrition Policy and Promotion"],
        "recipe_by": clean_text((recipe_data or {}).get("source") or author_name(recipe_schema.get("sourceOrganization"))),
        "category": [category] if category else [],
        "food_groups": food_groups,
        "yield": clean_text((recipe_data or {}).get("yield") or recipe_schema.get("recipeYield")),
        "serving_size": clean_text((recipe_data or {}).get("serving_size") or (recipe_schema.get("nutrition") or {}).get("servingSize")),
        "ingredients": ingredients,
        "equipment": [],
        "instructions": instructions,
        "notes": clean_text((recipe_data or {}).get("notes")),
        "nutrition": (recipe_data or {}).get("nutrition") or recipe_schema.get("nutrition") or {},
        "image": (recipe_data or {}).get("image_url") or image_from_schema(recipe_schema.get("image")),
        "date_published": clean_text((recipe_data or {}).get("date_published") or recipe_schema.get("datePublished")),
        "rating": {
            "value": (recipe_data or {}).get("rating_value") or (recipe_schema.get("aggregateRating") or {}).get("ratingValue"),
            "count": (recipe_data or {}).get("rating_count") or (recipe_schema.get("aggregateRating") or {}).get("ratingCount"),
        },
    }


def parse_recipe_page(url):
    html = fetch_text(url)
    jsonld, recipe_data = load_scripts(html)
    recipe_schema = recipe_schema_from_jsonld(jsonld)
    return normalize_recipe(url, recipe_data, recipe_schema)


def build_database(recipes, expected_count=None, failures=None):
    return {
        "metadata": {
            "source": "USDA MyPlate Kitchen",
            "source_url": RECIPES_INDEX_URL,
            "preserved_by": "MyPlate.food",
            "expected_recipe_count": expected_count,
            "recipe_count": len(recipes),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "notes": [
                "Recipes were originally published by USDA MyPlate Kitchen and are preserved by MyPlate.food.",
                "Federal USDA works are public domain in the United States; each recipe keeps its MyPlate.food source URL and original USDA URL when available.",
                "Ingredient quantity, unit, and name are parsed from each source ingredient line; raw preserves the original text.",
            ],
            "failures": failures or [],
        },
        "recipes": recipes,
    }


def write_json(data, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.write("\n")
        temp_name = file.name
    os.replace(temp_name, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape preserved USDA MyPlate Kitchen recipes from myplate.food."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--max-recipes", type=int, default=DEFAULT_MAX_RECIPES)
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between recipe page requests in seconds.")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write successfully parsed recipes even if some recipe pages fail.",
    )
    args = parser.parse_args()

    recipe_urls, expected_count = discover_recipe_urls()
    recipe_urls = recipe_urls[: max(1, args.max_recipes)]

    recipes = []
    failures = []
    for index, url in enumerate(recipe_urls, start=1):
        try:
            recipes.append(parse_recipe_page(url))
        except RuntimeError as exc:
            failures.append(str(exc))
            if not args.allow_partial:
                raise SystemExit(str(exc)) from exc
        if index % 100 == 0:
            print(f"Parsed {index}/{len(recipe_urls)} recipe pages...")
        if args.delay and index < len(recipe_urls):
            time.sleep(max(0, args.delay))

    if not recipes:
        raise SystemExit("No USDA MyPlate recipes could be parsed; output left unchanged.")

    database = build_database(recipes, expected_count=expected_count, failures=failures)
    write_json(database, args.output)
    print(f"Wrote {len(recipes)} USDA MyPlate recipes to {args.output}.")
    if failures:
        print(f"Skipped {len(failures)} recipes that could not be parsed.")


if __name__ == "__main__":
    main()
