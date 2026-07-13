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
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


PUBLIC_DOMAIN_RECIPES_BASE_URL = os.getenv(
    "PUBLIC_DOMAIN_RECIPES_BASE_URL", "https://publicdomainrecipes.org"
).rstrip("/")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("recipes.json")
DEFAULT_MAX_PAGES = int(os.getenv("PUBLIC_DOMAIN_RECIPES_MAX_PAGES", "5"))
DEFAULT_MAX_RECIPES = int(os.getenv("PUBLIC_DOMAIN_RECIPES_MAX_RECIPES", "100"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("PUBLIC_DOMAIN_RECIPES_TIMEOUT_SECONDS", "15"))
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"

RECIPE_URL_PATTERN = re.compile(r"""href=["']([^"']*/recipes/[^"']+/)["']""", re.I)
PAGED_RECIPE_URL_PATTERN = re.compile(r"""href=["']([^"']*/recipes/page/\d+/?)["']""", re.I)
EQUIPMENT_LINK_PATTERN = re.compile(
    r"""<a\s+[^>]*href\s*=\s*["']\s*/equipment/[^"']+["'][^>]*>(.*?)</a>""",
    re.I | re.S,
)
CATEGORY_LINK_PATTERN = re.compile(
    r"""<a\s+[^>]*href\s*=\s*["']\s*/categories/[^"']+["'][^>]*>(.*?)</a>""",
    re.I | re.S,
)
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")

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


class JsonLdScriptParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self._in_jsonld = False
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "script":
            return
        attr_map = {name.casefold(): value for name, value in attrs}
        script_type = (attr_map.get("type") or "").casefold()
        if script_type == "application/ld+json":
            self._in_jsonld = True
            self._buffer = []

    def handle_endtag(self, tag):
        if tag.casefold() == "script" and self._in_jsonld:
            self.scripts.append("".join(self._buffer).strip())
            self._in_jsonld = False
            self._buffer = []

    def handle_data(self, data):
        if self._in_jsonld:
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
        raise RuntimeError(f"Public Domain Recipes request failed for {url}: {exc}") from exc


def absolute_url(url):
    return urljoin(f"{PUBLIC_DOMAIN_RECIPES_BASE_URL}/", url)


def discover_recipe_urls(max_pages, max_recipes, delay_seconds):
    urls = []
    seen = set()
    queue = [absolute_url("/recipes/")]
    visited_pages = set()

    while queue and len(visited_pages) < max_pages and len(urls) < max_recipes:
        page_url = queue.pop(0)
        if page_url in visited_pages:
            continue
        visited_pages.add(page_url)
        html = fetch_text(page_url)

        for match in RECIPE_URL_PATTERN.finditer(html):
            recipe_url = absolute_url(match.group(1))
            parsed_path = urlparse(recipe_url).path
            if "/recipes/page/" in parsed_path or parsed_path.rstrip("/") == "/recipes":
                continue
            if recipe_url not in seen:
                urls.append(recipe_url)
                seen.add(recipe_url)
                if len(urls) >= max_recipes:
                    break

        for match in PAGED_RECIPE_URL_PATTERN.finditer(html):
            next_url = absolute_url(match.group(1))
            if next_url not in visited_pages and next_url not in queue:
                queue.append(next_url)

        if delay_seconds and queue and len(urls) < max_recipes:
            time.sleep(delay_seconds)

    return urls


def load_jsonld_scripts(html):
    parser = JsonLdScriptParser()
    parser.feed(html)
    documents = []
    for script in parser.scripts:
        if not script:
            continue
        try:
            documents.append(json.loads(unescape(script)))
        except json.JSONDecodeError:
            continue
    return documents


def find_recipe_schema(value):
    if isinstance(value, list):
        for item in value:
            recipe = find_recipe_schema(item)
            if recipe:
                return recipe
    if isinstance(value, dict):
        value_type = value.get("@type")
        types = value_type if isinstance(value_type, list) else [value_type]
        if any(str(item).casefold() == "recipe" for item in types):
            return value
        for key in ("@graph", "mainEntity", "itemListElement"):
            recipe = find_recipe_schema(value.get(key))
            if recipe:
                return recipe
    return None


def list_from_schema_value(value):
    if value in (None, "", "null"):
        return []
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                return list_from_schema_value(json.loads(stripped))
            except json.JSONDecodeError:
                pass
        return [clean_text(part) for part in stripped.split(",") if clean_text(part)]
    return [clean_text(value)]


def image_from_schema(value):
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    if isinstance(value, list) and value:
        return image_from_schema(value[0])
    return None


def author_from_schema(value):
    authors = value if isinstance(value, list) else [value]
    names = []
    for author in authors:
        if isinstance(author, dict):
            name = clean_text(author.get("name"))
        else:
            name = clean_text(author)
        if name:
            names.append(name)
    return names


def instruction_text(step):
    if isinstance(step, str):
        return clean_text(step)
    if isinstance(step, dict):
        return clean_text(step.get("text") or step.get("name"))
    return ""


def instructions_from_schema(value):
    if isinstance(value, list):
        return [text for text in (instruction_text(step) for step in value) if text]
    text = instruction_text(value)
    return [text] if text else []


def parse_quantity_and_name(raw_ingredient):
    text = clean_text(raw_ingredient)
    note = None
    note_match = re.search(r"\(([^)]+)\)", text)
    if note_match:
        note = clean_text(note_match.group(1))

    normalized = SPACE_PATTERN.sub(" ", text.replace("\u00bc", "1/4").replace("\u00bd", "1/2").replace("\u00be", "3/4"))
    match = re.match(
        r"^(?P<quantity>\d+(?:\.\d+)?(?:/\d+)?(?:\s+\d+/\d+)?)\s*(?P<rest>.*)$",
        normalized,
    )
    if not match:
        return {
            "name": clean_text(re.split(r",", normalized, maxsplit=1)[0]),
            "quantity": None,
            "unit": None,
            "note": note or clean_text(re.split(r",", normalized, maxsplit=1)[1]) if "," in normalized else note,
            "raw": text,
        }

    quantity = match.group("quantity")
    rest = match.group("rest").strip()
    words = rest.split()
    unit = None
    if words and words[0].casefold().rstrip(".") in UNITS:
        unit = words.pop(0).rstrip(".")
    ingredient_name = clean_text(" ".join(words))
    if "," in ingredient_name:
        ingredient_name, trailing_note = ingredient_name.split(",", 1)
        note = note or clean_text(trailing_note)

    return {
        "name": clean_text(ingredient_name),
        "quantity": quantity,
        "unit": unit,
        "note": note,
        "raw": text,
    }


def links_for_taxonomy(html, pattern):
    values = []
    seen = set()
    for match in pattern.finditer(html):
        value = clean_text(match.group(1))
        key = value.casefold()
        if value and key not in seen:
            values.append(value)
            seen.add(key)
    return values


def primary_recipe_html(html):
    return re.split(
        r"<h3[^>]*>\s*(?:See Also|New:)\s*</h3>|<footer\b",
        html,
        maxsplit=1,
        flags=re.I,
    )[0]


def stable_recipe_id(url, name):
    key = url or name
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def parse_recipe_page(url):
    html = fetch_text(url)
    primary_html = primary_recipe_html(html)
    recipe_schema = None
    for document in load_jsonld_scripts(html):
        recipe_schema = find_recipe_schema(document)
        if recipe_schema:
            break
    if not recipe_schema:
        raise RuntimeError(f"No Recipe JSON-LD found for {url}")

    name = clean_text(recipe_schema.get("name"))
    raw_ingredients = list_from_schema_value(recipe_schema.get("recipeIngredient"))
    instructions = instructions_from_schema(recipe_schema.get("recipeInstructions"))
    categories = list_from_schema_value(recipe_schema.get("recipeCategory"))
    if not categories:
        categories = links_for_taxonomy(primary_html, CATEGORY_LINK_PATTERN)
    equipment = links_for_taxonomy(primary_html, EQUIPMENT_LINK_PATTERN)

    if not name or len(raw_ingredients) < 2:
        raise RuntimeError(f"Recipe page did not include enough recipe data: {url}")

    return {
        "id": stable_recipe_id(url, name),
        "name": name,
        "source_url": url,
        "source": "Public Domain Recipes",
        "public_domain": True,
        "author": author_from_schema(recipe_schema.get("author")),
        "category": categories,
        "yield": clean_text(recipe_schema.get("recipeYield")),
        "ingredients": [parse_quantity_and_name(ingredient) for ingredient in raw_ingredients],
        "equipment": equipment,
        "instructions": instructions,
        "image": image_from_schema(recipe_schema.get("image")),
        "date_published": clean_text(recipe_schema.get("datePublished")),
    }


def build_recipe_database(recipes, source_url):
    return {
        "metadata": {
            "source": "Public Domain Recipes",
            "source_url": source_url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "recipe_count": len(recipes),
            "notes": [
                "Recipes are historical public domain recipes from publicdomainrecipes.org.",
                "Ingredient quantity, unit, and name are parsed from each source ingredient line; raw preserves the original text.",
                "These recipes are historical and should be reviewed for modern food safety before use.",
            ],
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
        description="Scrape Public Domain Recipes into a structured recipes.json file."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--max-recipes", type=int, default=DEFAULT_MAX_RECIPES)
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between page requests in seconds.")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write successfully parsed recipes even if some recipe pages fail.",
    )
    args = parser.parse_args()

    recipe_urls = discover_recipe_urls(
        max(1, args.max_pages),
        max(1, args.max_recipes),
        max(0, args.delay),
    )
    recipes = []
    failures = []
    for index, url in enumerate(recipe_urls, start=1):
        try:
            recipes.append(parse_recipe_page(url))
        except RuntimeError as exc:
            failures.append(str(exc))
            if not args.allow_partial:
                raise SystemExit(str(exc)) from exc
        if args.delay and index < len(recipe_urls):
            time.sleep(max(0, args.delay))

    if not recipes:
        raise SystemExit("No Public Domain Recipes pages could be parsed; output left unchanged.")

    database = build_recipe_database(recipes, f"{PUBLIC_DOMAIN_RECIPES_BASE_URL}/recipes/")
    if failures:
        database["metadata"]["failures"] = failures
    write_json(database, args.output)
    print(f"Wrote {len(recipes)} Public Domain Recipes recipes to {args.output}.")
    if failures:
        print(f"Skipped {len(failures)} recipes that could not be parsed.")


if __name__ == "__main__":
    main()
