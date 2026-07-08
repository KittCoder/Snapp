
import os
import json
import hashlib
import math
import random
import re
import time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request
from openai import OpenAI

app = Flask(__name__)

SYSTEM_PROMPT = (
    "You are a helpful meal generating assistant who generates concise meal ideas initially, asks for feedback, iterates, then returns recipes upon confirmation of meals from user. "
)
DISH_SYSTEM_PROMPT = (
    "You generate real, recognizable dish ideas from available ingredients. "
    "Return only valid JSON. Do not include recipes or cooking steps."
)
OPENAI_DISH_MODEL = os.getenv("OPENAI_DISH_MODEL", "gpt-4.1-nano")
MAX_TURNS = 6
conversation_history = []
ZIP_CODE_PATTERN = re.compile(r"^\d{5}$")
MIN_HOUSEHOLD_SIZE = 1
MAX_HOUSEHOLD_SIZE = 12
MAX_STORE_RADIUS_MILES = 25
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ZIPPOPOTAM_URL = "https://api.zippopotam.us/us"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TRADER_JOES_LOCATIONS_BASE_URL = "https://locations.traderjoes.com"
ENABLE_SPOONACULAR = os.getenv("ENABLE_SPOONACULAR", "false").casefold() == "true"
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY", "") if ENABLE_SPOONACULAR else ""
SPOONACULAR_BASE_URL = os.getenv(
    "SPOONACULAR_BASE_URL", "https://api.spoonacular.com"
).rstrip("/")
SPOONACULAR_SEARCH_RESULT_COUNT = 24
SPOONACULAR_RANDOM_RESULT_COUNT = 24
RECIPE_IDEA_COUNT = 8
SPOONACULAR_IDEA_SEARCH_LIMIT = 4
THEMEALDB_BASE_URL = os.getenv(
    "THEMEALDB_BASE_URL", "https://www.themealdb.com/api/json/v1/1"
).rstrip("/")
THEMEALDB_SEARCH_LIMIT = 24
WEB_RECIPE_SEARCH_RESULT_COUNT = 8
WEB_RECIPE_FETCH_LIMIT = 5
HTTP_TIMEOUT_SECONDS = 20
HTTP_RETRY_ATTEMPTS = 2
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"
STORE_CACHE_TTL_SECONDS = 15 * 60
FOOD_CACHE_TTL_SECONDS = 60 * 60
TRADER_JOES_STORE_CACHE_TTL_SECONDS = 24 * 60 * 60
TRADER_JOES_PRODUCT_CACHE_TTL_SECONDS = 12 * 60 * 60
SCRAPED_GROCERY_DB_FILENAME = "data.json"
DEMO_GROCERY_DB_FILENAME = "snapp_demo_grocery_db.json"
store_search_cache = {}
trader_joes_store_cache = {}
trader_joes_product_cache = {}
food_search_cache = {}
spoonacular_search_cache = {}
spoonacular_lookup_cache = {}
mealdb_search_cache = {}
mealdb_lookup_cache = {}
robots_cache = {}
FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_API_KEY = os.getenv("FDC_API_KEY") or os.getenv("FOODDATA_CENTRAL_API_KEY") or "DEMO_KEY"
US_STATE_CODES = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}
NUTRIENT_ALIASES = {
    "calories": {"energy"},
    "protein_g": {"protein"},
    "carbohydrates_g": {"carbohydrate, by difference", "carbohydrate, by summation"},
    "fat_g": {"total lipid (fat)", "total fat (nlea)"},
    "fiber_g": {"fiber, total dietary", "total dietary fiber"},
    "sugars_g": {"total sugars", "sugars, total including nlea"},
    "sodium_mg": {"sodium, na"},
}
INGREDIENT_SPLIT_PATTERN = re.compile(r",|\n|;|\band\b", re.IGNORECASE)
FOOD_SEARCH_OVERRIDES = {
    "mint": "spearmint fresh",
    "fresh mint": "spearmint fresh",
    "potato": "potatoes raw",
    "potatoes": "potatoes raw",
}
FOOD_MATCH_PENALTY_TERMS = (
    "babyfood",
    "beverage",
    "cake",
    "candies",
    "candy",
    "chips",
    "chocolate",
    "cookies",
    "dessert",
    "flour",
    "french fried",
    "ice cream",
    "snack",
    "soup",
    "syrup",
)
RESTRICTION_RULES = (
    (
        re.compile(r"\b(lactose|dairy|milk|cheese|cream|yogurt|butter)\b", re.I),
        re.compile(r"\b(milk|cheese|cheddar|mozzarella|feta|parmesan|cream|yogurt|butter|whey|lactose|dairy)\b", re.I),
    ),
    (
        re.compile(r"\b(gluten|wheat|celiac|coeliac)\b", re.I),
        re.compile(r"\b(wheat|flour|bread|pasta|noodle|noodles|tortilla|breadcrumbs|gluten)\b", re.I),
    ),
    (
        re.compile(r"\b(peanut|peanuts)\b", re.I),
        re.compile(r"\b(peanut|peanuts|peanut butter)\b", re.I),
    ),
    (
        re.compile(r"\b(tree nuts?|nuts?|almond|cashew|walnut|pecan)\b", re.I),
        re.compile(r"\b(almond|cashew|walnut|pecan|pistachio|hazelnut|nut butter|nuts?)\b", re.I),
    ),
    (
        re.compile(r"\b(shellfish|shrimp|crab|lobster)\b", re.I),
        re.compile(r"\b(shellfish|shrimp|crab|lobster)\b", re.I),
    ),
    (
        re.compile(r"\b(egg|eggs)\b", re.I),
        re.compile(r"\b(egg|eggs|mayonnaise|mayo)\b", re.I),
    ),
    (
        re.compile(r"\b(soy|soya)\b", re.I),
        re.compile(r"\b(soy|soya|tofu|tempeh|edamame|soy sauce)\b", re.I),
    ),
)
RECIPE_SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "cheap",
    "dinner",
    "easy",
    "for",
    "healthy",
    "lunch",
    "meal",
    "meals",
    "quick",
    "recipe",
    "recipes",
    "the",
    "with",
}
RECIPE_GENERIC_PROMPT_WORDS = RECIPE_SEARCH_STOPWORDS | {
    "breakfast",
    "brunch",
    "dinner",
    "food",
    "lunch",
    "snack",
    "supper",
}
RECIPE_INGREDIENT_ALIASES = {
    "beef": {"beef", "brisket", "steak", "ground beef", "minced beef", "short ribs"},
    "chicken": {"chicken thighs"},
    "chicken breast": {"chicken thighs"},
    "fish": {"fish", "cod", "salmon", "tuna"},
    "pork": {"pork", "bacon", "ham", "sausage"},
    "shrimp": {"shrimp", "prawn", "prawns"},
    "tomato": {"canned tomatoes"},
    "tomatoes": {"canned tomatoes"},
    "pasta": {"pasta"},
    "spaghetti": {"pasta"},
    "noodles": {"pasta"},
    "noodle": {"pasta"},
    "potato": {"potatoes"},
    "beans": {"black beans"},
    "bean": {"black beans"},
    "sweetcorn": {"frozen corn"},
    "corn": {"frozen corn"},
    "broccoli": {"frozen broccoli"},
    "tortilla": {"tortillas"},
    "flour tortillas": {"tortillas"},
    "cheddar": {"cheese"},
    "mozzarella": {"cheese"},
    "parmesan": {"cheese"},
}
RECIPE_REQUEST_INGREDIENTS = {
    "beef": {"beef", "brisket", "steak", "ground beef", "minced beef", "short ribs"},
    "chicken": {"chicken"},
    "fish": {"fish", "cod", "salmon", "tuna"},
    "pork": {"pork", "bacon", "ham", "sausage"},
    "shrimp": {"shrimp", "prawn", "prawns"},
    "tuna": {"tuna"},
    "salmon": {"salmon"},
    "egg": {"egg", "eggs"},
    "eggs": {"egg", "eggs"},
    "beans": {"bean", "beans", "black beans", "kidney beans", "chickpeas"},
    "lentils": {"lentil", "lentils"},
    "tofu": {"tofu"},
    "rice": {"rice"},
    "pasta": {"pasta", "spaghetti", "penne", "linguine", "macaroni"},
    "potatoes": {"potato", "potatoes"},
    "potato": {"potato", "potatoes"},
}
RECIPE_MEAL_TYPE_HINTS = {
    "breakfast": {"breakfast", "pancake", "pancakes", "egg", "eggs", "omelette", "toast"},
    "lunch": {"sandwich", "salad", "soup", "wrap"},
    "dinner": {
        "beef",
        "brisket",
        "chicken",
        "casserole",
        "curry",
        "fish",
        "meat",
        "pork",
        "pot roast",
        "roast",
        "stew",
        "steak",
    },
}
RECIPE_NON_DINNER_TERMS = {
    "breakfast",
    "pancake",
    "pancakes",
    "cookie",
    "cookies",
    "cake",
    "dessert",
}
RECIPE_CUISINE_ALIASES = {
    "american": "United States",
    "chinese": "Chinese",
    "croatian": "Croatian",
    "dutch": "Dutch",
    "egyptian": "Egyptian",
    "filipino": "Filipino",
    "french": "French",
    "greek": "Greek",
    "indian": "Indian",
    "irish": "Irish",
    "italian": "Italian",
    "jamaican": "Jamaican",
    "japanese": "Japanese",
    "kenyan": "Kenyan",
    "malaysian": "Malaysian",
    "mexican": "Mexican",
    "moroccan": "Moroccan",
    "polish": "Polish",
    "portuguese": "Portuguese",
    "russian": "Russian",
    "spanish": "Spanish",
    "thai": "Thai",
    "tunisian": "Tunisian",
    "turkish": "Turkish",
    "ukrainian": "Ukrainian",
    "usa": "United States",
    "u s": "United States",
    "u s a": "United States",
    "us": "United States",
    "vietnamese": "Vietnamese",
    "uk": "British",
    "u k": "British",
    "united kingdom": "British",
}
WEB_RECIPE_SOURCES = (
    {
        "name": "Budget Bytes",
        "base_url": "https://www.budgetbytes.com",
        "search_path": "/",
        "query_param": "s",
    },
    {
        "name": "Simply Recipes",
        "base_url": "https://www.simplyrecipes.com",
        "search_path": "/search",
        "query_param": "q",
    },
    {
        "name": "Love and Lemons",
        "base_url": "https://www.loveandlemons.com",
        "search_path": "/",
        "query_param": "s",
    },
    {
        "name": "RecipeTin Eats",
        "base_url": "https://www.recipetineats.com",
        "search_path": "/",
        "query_param": "s",
    },
    {
        "name": "EatingWell",
        "base_url": "https://www.eatingwell.com",
        "search_path": "/search",
        "query_param": "q",
    },
)
DEFAULT_PRICE_PER_100G = 0.55
PRICE_PER_100G_RULES = (
    (r"\b(lamb)\b", 1.75),
    (r"\b(beef)\b", 1.25),
    (r"\b(salmon|fish)\b", 1.65),
    (r"\b(shrimp)\b", 1.45),
    (r"\b(chicken|turkey|pork)\b", 0.75),
    (r"\b(tofu|tempeh)\b", 0.65),
    (r"\b(beans|lentils|chickpeas|black beans|kidney beans|pinto beans)\b", 0.28),
    (r"\b(egg|eggs)\b", 0.45),
    (r"\b(cheese|cheddar|parmesan|feta|mozzarella)\b", 1.10),
    (r"\b(oil|olive oil|vegetable oil|canola oil|butter|ghee)\b", 0.85),
    (r"\b(peanut butter|almond butter|nut butter|nuts|almonds|walnuts|cashews|pecans|peanuts|seeds)\b", 0.95),
    (r"\b(rice|pasta|noodle|noodles|potato|potatoes|quinoa|couscous|grain|grains|oats)\b", 0.22),
    (r"\b(tortilla|bread)\b", 0.35),
    (r"\b(fruit|apple|banana|berries|strawberries|blueberries|orange|grapes|mango|pineapple|peach|pear)\b", 0.45),
    (r"\b(greens|spinach|lettuce|arugula|kale|spring mix|romaine)\b", 0.75),
    (r"\b(broccoli|pepper|peppers|tomato|tomatoes|zucchini|vegetable|vegetables)\b", 0.42),
    (r"\b(onion|carrot|celery|cabbage)\b", 0.24),
    (r"\b(mint|basil|cilantro|parsley|dill|thyme|rosemary|oregano|sage)\b", 2.80),
    (r"\b(garlic|ginger|jalapeno|chili|lemon juice|lime juice|spice|spices)\b", 0.85),
    (r"\b(sauce|salsa|dressing|yogurt|cream|broth|stock)\b", 0.55),
)
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "https://snapp-1d5j.vercel.app,"
    "https://snapp.vercel.app"
)
VERCEL_DEPLOYMENT_ORIGIN_PATTERN = re.compile(
    r"^https://snapp(?:-[a-z0-9-]+)?\.vercel\.app$"
)
CORS_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "").rstrip("/")
    is_allowed_vercel_deployment = bool(
        origin and VERCEL_DEPLOYMENT_ORIGIN_PATTERN.fullmatch(origin)
    )
    if "*" in CORS_ORIGINS or origin in CORS_ORIGINS or is_allowed_vercel_deployment:
        response.headers["Access-Control-Allow-Origin"] = (
            "*" if "*" in CORS_ORIGINS else origin
        )
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


def generate_reply(message):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    history = conversation_history[-MAX_TURNS * 2 :]
    prompt = [{"role": "system", "content": SYSTEM_PROMPT}]
    prompt.extend(history)
    prompt.append({"role": "user", "content": message})
    response = client.responses.create(
        model="gpt-4.1-nano",
        input=prompt,
        store=False,
    )
    reply = response.output_text
    conversation_history.append({"role": "user", "content": message})
    conversation_history.append({"role": "assistant", "content": reply})
    return reply, response.usage.total_tokens


def fetch_json(url, data=None, json_data=None, service_name="data service"):
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if json_data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_data).encode("utf-8")
    elif data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urlencode(data).encode("utf-8")

    last_error = None
    for attempt in range(HTTP_RETRY_ATTEMPTS):
        request_object = Request(url, data=data, headers=headers)
        try:
            with urlopen(request_object, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            print(
                f"{service_name} request failed on attempt {attempt + 1}: {exc}",
                flush=True,
            )
            if attempt + 1 < HTTP_RETRY_ATTEMPTS:
                time.sleep(1)

    raise RuntimeError("The grocery store data service is unavailable.") from last_error


def fetch_fooddata_json(url, json_data):
    try:
        return fetch_json(url, json_data=json_data, service_name="FoodData Central")
    except RuntimeError as exc:
        raise RuntimeError("The USDA FoodData Central service is unavailable.") from exc


def fetch_spoonacular_json(path, params=None):
    if not SPOONACULAR_API_KEY:
        raise RuntimeError("SPOONACULAR_API_KEY is not set.")

    query_params = dict(params or {})
    query_params["apiKey"] = SPOONACULAR_API_KEY
    query = f"?{urlencode(query_params)}"
    url = f"{SPOONACULAR_BASE_URL}/{path.lstrip('/')}{query}"
    try:
        return fetch_json(url, service_name="Spoonacular")
    except RuntimeError as exc:
        raise RuntimeError("Spoonacular recipe service is unavailable.") from exc


def fetch_mealdb_json(path, params=None):
    query = f"?{urlencode(params or {})}" if params else ""
    url = f"{THEMEALDB_BASE_URL}/{path.lstrip('/')}{query}"
    try:
        return fetch_json(url, service_name="TheMealDB")
    except RuntimeError as exc:
        raise RuntimeError("TheMealDB recipe service is unavailable.") from exc


def fetch_text(url, service_name="web page"):
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": USER_AGENT,
    }
    request_object = Request(url, headers=headers)
    try:
        with urlopen(request_object, timeout=HTTP_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return ""
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read(1_500_000).decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError) as exc:
        print(f"{service_name} fetch failed: {exc}", flush=True)
        return ""


class RecipeLinkParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if not href:
            return
        self.links.append(urljoin(self.base_url, href))


class AnchorTextParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if not href:
            return
        self.current_href = urljoin(self.base_url, href)
        self.current_text = []

    def handle_data(self, data):
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self.current_href:
            return
        text = re.sub(r"\s+", " ", " ".join(self.current_text)).strip()
        self.links.append({"url": self.current_href, "text": text})
        self.current_href = None
        self.current_text = []


class TraderJoesStorePageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
            return
        if tag != "meta":
            return
        attributes = dict(attrs)
        key = attributes.get("property") or attributes.get("name")
        content = attributes.get("content")
        if key and content:
            self.meta[key] = content

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    @property
    def title(self):
        return re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_json_ld = False
        self.current = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        attributes = {
            (key or "").casefold(): value or ""
            for key, value in attrs
        }
        if attributes.get("type", "").casefold() == "application/ld+json":
            self.in_json_ld = True
            self.current = []

    def handle_data(self, data):
        if self.in_json_ld:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json_ld:
            self.blocks.append("".join(self.current))
            self.in_json_ld = False
            self.current = []


def robots_allows(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}"
    cached = robots_cache.get(origin)
    if cached is None:
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            parser.read()
            cached = parser
        except Exception as exc:
            print(f"robots.txt check failed for {origin}: {exc}", flush=True)
            cached = False
        robots_cache[origin] = cached
    if cached is False:
        return False
    return cached.can_fetch(USER_AGENT, url)


def web_recipe_search_url(source, query):
    params = urlencode({source["query_param"]: f"{query} recipe"})
    return urljoin(source["base_url"], f"{source['search_path']}?{params}")


def recipe_link_score(url, query):
    parsed = urlparse(url)
    path = normalize_cuisine_text(parsed.path)
    query_words = normalized_food_words(query)
    score = len(query_words & set(path.split()))
    if re.search(r"\b(recipe|recipes|dinner|meal)\b", path):
        score += 2
    if re.search(r"\b(category|tag|author|about|privacy|search|shop|video|news)\b", path):
        score -= 4
    return score


def discover_recipe_urls(recipe_ideas):
    urls = []
    seen = set()
    for idea in recipe_ideas[:3]:
        query = idea.get("query") or idea.get("name") or ""
        if not query:
            continue
        for source in WEB_RECIPE_SOURCES:
            if len(urls) >= WEB_RECIPE_SEARCH_RESULT_COUNT:
                return urls
            search_url = web_recipe_search_url(source, query)
            if not robots_allows(search_url):
                continue
            html = fetch_text(search_url, service_name=f"{source['name']} search")
            if not html:
                continue
            parser = RecipeLinkParser(source["base_url"])
            parser.feed(html)
            source_netloc = urlparse(source["base_url"]).netloc
            ranked_links = sorted(
                {
                    link.split("#", 1)[0]
                    for link in parser.links
                    if urlparse(link).netloc == source_netloc
                    and recipe_link_score(link, query) > 0
                },
                key=lambda link: recipe_link_score(link, query),
                reverse=True,
            )
            for link in ranked_links[:3]:
                if link not in seen:
                    urls.append(link)
                    seen.add(link)
                if len(urls) >= WEB_RECIPE_SEARCH_RESULT_COUNT:
                    return urls
    return urls


def jsonld_items(value):
    if isinstance(value, list):
        for item in value:
            yield from jsonld_items(item)
    elif isinstance(value, dict):
        graph = value.get("@graph")
        if graph:
            yield from jsonld_items(graph)
        yield value


def jsonld_is_recipe(item):
    item_type = item.get("@type")
    if isinstance(item_type, list):
        types = {str(value).casefold() for value in item_type}
    else:
        types = {str(item_type).casefold()}
    return "recipe" in types


def text_from_schema_value(value):
    if isinstance(value, str):
        return spoonacular_recipe_text(value)
    if isinstance(value, dict):
        return spoonacular_recipe_text(
            value.get("text") or value.get("name") or value.get("url") or ""
        )
    return ""


def schema_image_url(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            image = schema_image_url(item)
            if image:
                return image
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    return None


def schema_list_values(value):
    if isinstance(value, list):
        return [text_from_schema_value(item) for item in value if text_from_schema_value(item)]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def schema_recipe_to_recipe(recipe_schema, source_url):
    name = spoonacular_recipe_text(
        recipe_schema.get("name") or recipe_schema.get("headline") or ""
    )
    ingredients = schema_list_values(recipe_schema.get("recipeIngredient"))
    if not name or len(ingredients) < 2:
        return None
    cuisines = schema_list_values(recipe_schema.get("recipeCuisine"))
    categories = schema_list_values(recipe_schema.get("recipeCategory"))
    source = recipe_schema.get("url") or source_url
    stable_id = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"web:{stable_id}",
        "title": name,
        "cuisines": cuisines,
        "dishTypes": categories or ["main course"],
        "extendedIngredients": [
            {
                "name": normalize_ingredient_name(ingredient),
                "original": ingredient,
            }
            for ingredient in ingredients
            if normalize_ingredient_name(ingredient)
        ],
        "instructions": "Open the source recipe for the full cooking method.",
        "image": schema_image_url(recipe_schema.get("image")),
        "sourceUrl": source_url,
        "_snapp_recipe_provider": "web",
    }


def extract_schema_recipe(html, source_url):
    parser = JsonLdParser()
    parser.feed(html)
    for block in parser.blocks:
        try:
            data = json.loads(unescape(block))
        except json.JSONDecodeError:
            continue
        for item in jsonld_items(data):
            if jsonld_is_recipe(item):
                recipe = schema_recipe_to_recipe(item, source_url)
                if recipe:
                    return recipe
    return None


def fetch_web_recipe_candidates(recipe_ideas):
    recipes = []
    seen_ids = set()
    for url in discover_recipe_urls(recipe_ideas):
        if len(recipes) >= WEB_RECIPE_FETCH_LIMIT:
            break
        if not robots_allows(url):
            continue
        html = fetch_text(url, service_name="recipe page")
        if not html:
            continue
        recipe = extract_schema_recipe(html, url)
        recipe_id = spoonacular_recipe_id(recipe or {})
        if recipe and recipe_id not in seen_ids:
            recipes.append(recipe)
            seen_ids.add(recipe_id)
    return recipes


def normalize_ingredient_name(value):
    cleaned = re.sub(r"\([^)]*\)", "", value or "")
    cleaned = re.sub(r"\b\d+([./]\d+)?\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(cups?|tbsp|tablespoons?|tsp|teaspoons?|oz|ounces?|lbs?|pounds?|grams?|g|kg|ml|l|liters?)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    return cleaned[:80]


def parse_ingredients(raw_ingredients):
    ingredients = []
    seen = set()
    for part in INGREDIENT_SPLIT_PATTERN.split(raw_ingredients or ""):
        ingredient = normalize_ingredient_name(part)
        if len(ingredient) < 2:
            continue
        identity = ingredient.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        ingredients.append(ingredient)
    return ingredients[:8]


def parse_household_size(value):
    try:
        household_size = int(value)
    except (TypeError, ValueError):
        return MIN_HOUSEHOLD_SIZE
    return max(MIN_HOUSEHOLD_SIZE, min(household_size, MAX_HOUSEHOLD_SIZE))


def parse_store_radius_miles(value):
    if value in (None, ""):
        return None
    try:
        radius_miles = float(value)
    except (TypeError, ValueError):
        return None
    if radius_miles <= 0:
        return None
    return min(radius_miles, MAX_STORE_RADIUS_MILES)


def parse_pantry_items(value):
    if not isinstance(value, list):
        return []

    pantry_items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"\s+", " ", str(item.get("name") or "")).strip()
        quantity = re.sub(r"\s+", " ", str(item.get("quantity") or "")).strip()
        if not name or not quantity:
            continue
        pantry_items.append(
            {
                "name": name[:80],
                "quantity": quantity[:60],
            }
        )
    return pantry_items[:25]


def parse_optional_float(value, minimum=None):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None and number < minimum:
        return None
    return number


def parse_optional_int(value, minimum=None, maximum=None):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def parse_filter_terms(value):
    if isinstance(value, list):
        raw_terms = value
    else:
        raw_terms = re.split(r",|\n|;", str(value or ""))
    terms = []
    seen = set()
    for term in raw_terms:
        cleaned = normalize_ingredient_name(str(term))
        if not cleaned:
            continue
        identity = cleaned.casefold()
        if identity in seen:
            continue
        terms.append(cleaned)
        seen.add(identity)
    return terms[:12]


def parse_recipe_filters(data, household_size, dietary_restrictions):
    return {
        "max_budget": parse_optional_float(data.get("max_budget"), minimum=0),
        "servings": parse_optional_int(
            data.get("servings"),
            minimum=MIN_HOUSEHOLD_SIZE,
            maximum=MAX_HOUSEHOLD_SIZE,
        )
        or household_size,
        "dietary_preference": re.sub(
            r"\s+", " ", str(data.get("dietary_preference") or "").strip()
        )[:80],
        "dietary_restrictions": dietary_restrictions,
        "include_ingredients": parse_filter_terms(data.get("include_ingredients")),
        "avoid_ingredients": parse_filter_terms(data.get("avoid_ingredients")),
        "max_cook_time": parse_optional_int(
            data.get("max_cook_time"),
            minimum=1,
            maximum=600,
        ),
    }


def pantry_items_text(pantry_items):
    if not pantry_items:
        return "none"
    return "; ".join(
        f"{item['name']} ({item['quantity']})" for item in pantry_items
    )


def distance_miles(lat1, lon1, lat2, lon2):
    earth_radius_miles = 3958.8
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_miles * 2 * math.atan2(
        math.sqrt(haversine), math.sqrt(1 - haversine)
    )


def load_demo_grocery_db():
    search_paths = (
        Path(__file__).with_name(SCRAPED_GROCERY_DB_FILENAME),
        Path(__file__).resolve().parent.parent / SCRAPED_GROCERY_DB_FILENAME,
        Path(__file__).with_name(DEMO_GROCERY_DB_FILENAME),
        Path(__file__).resolve().parent.parent / DEMO_GROCERY_DB_FILENAME,
    )
    for path in search_paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as file:
            grocery_db = json.load(file)
        if path.name == SCRAPED_GROCERY_DB_FILENAME and not grocery_db.get("products"):
            continue
        return grocery_db
    raise RuntimeError("The SNAPP demo grocery database is missing.")


def load_trader_joes_grocery_db(store_number):
    store_number = re.sub(r"\D+", "", str(store_number or ""))[:10]
    if not store_number:
        return None

    cached_result = trader_joes_product_cache.get(store_number)
    now = time.time()
    if (
        cached_result
        and now - cached_result["cached_at"] < TRADER_JOES_PRODUCT_CACHE_TTL_SECONDS
    ):
        return cached_result["grocery_db"]

    try:
        from scraper import (
            DEFAULT_MAX_PRODUCTS,
            build_database,
            fetch_apify_trader_joes_items,
            normalize_apify_products,
        )

        raw_items = fetch_apify_trader_joes_items(store_number)
        products = normalize_apify_products(
            raw_items,
            store_number,
            max_products=DEFAULT_MAX_PRODUCTS,
        )
    except Exception as exc:
        print(f"Trader Joe's product refresh failed: {exc}", flush=True)
        return None

    if not products:
        return None
    grocery_db = build_database(products, store_number)
    trader_joes_product_cache[store_number] = {
        "cached_at": now,
        "grocery_db": grocery_db,
    }
    return grocery_db


def grocery_db_for_store(store_number=None):
    trader_joes_db = load_trader_joes_grocery_db(store_number)
    if trader_joes_db:
        return trader_joes_db
    return load_demo_grocery_db()


def product_effective_price(product):
    price = product.get("sale_price")
    if price is None:
        price = product.get("price")
    try:
        return round(float(price), 2)
    except (TypeError, ValueError):
        return 0


def available_demo_products(grocery_db):
    return [
        product
        for product in grocery_db.get("products", [])
        if product.get("in_stock") and product.get("snap_eligible")
    ]


def demo_store_lookup(grocery_db):
    return {
        store["id"]: store
        for store in grocery_db.get("stores", [])
        if store.get("id")
    }


def demo_catalog_for_prompt(products, stores):
    catalog = []
    for product in products:
        store = stores.get(product.get("store_id"), {})
        catalog.append(
            {
                "id": product.get("id"),
                "ingredient": product.get("ingredient"),
                "product_name": product.get("product_name"),
                "food_group": product.get("food_group"),
                "store": store.get("name", product.get("store_id")),
                "package_size": product.get("package_size"),
                "package_grams": product.get("package_grams"),
                "price": product_effective_price(product),
                "calories_per_100g": product.get("calories_per_100g"),
            }
        )
    return catalog


def nutrition_from_calories(calories, grams, food_group):
    group = (food_group or "").casefold()
    if group == "protein":
        protein_share, carb_share, fat_share, fiber_per_100g = 0.42, 0.18, 0.40, 1.0
    elif group == "grains":
        protein_share, carb_share, fat_share, fiber_per_100g = 0.12, 0.80, 0.08, 3.0
    elif group == "vegetables":
        protein_share, carb_share, fat_share, fiber_per_100g = 0.18, 0.74, 0.08, 3.2
    elif group == "fruits":
        protein_share, carb_share, fat_share, fiber_per_100g = 0.04, 0.94, 0.02, 2.4
    elif group == "dairy":
        protein_share, carb_share, fat_share, fiber_per_100g = 0.28, 0.38, 0.34, 0
    else:
        protein_share, carb_share, fat_share, fiber_per_100g = 0.18, 0.62, 0.20, 1.0

    return {
        "protein_g": calories * protein_share / 4,
        "carbohydrates_g": calories * carb_share / 4,
        "fat_g": calories * fat_share / 9,
        "fiber_g": grams * fiber_per_100g / 100,
        "sugars_g": 0,
        "sodium_mg": 0,
    }


def add_nutrients(total_nutrients, nutrients):
    for key in total_nutrients:
        total_nutrients[key] += nutrients.get(key, 0)


def is_fruit_appropriate_for_dish(product, dish_name, portion_note):
    if (product.get("food_group") or "").casefold() != "fruits":
        return True

    dish_text = f"{dish_name} {portion_note}".casefold()
    fruit_context_patterns = (
        r"\bfruit\b",
        r"\bapple\b",
        r"\bbanana\b",
        r"\bberry\b",
        r"\bberries\b",
        r"\bsmoothie\b",
        r"\byogurt\b",
        r"\boatmeal\b",
        r"\boats\b",
        r"\bparfait\b",
        r"\bpancake\b",
        r"\btoast\b",
        r"\bsalad\b",
    )
    return any(re.search(pattern, dish_text) for pattern in fruit_context_patterns)


def nutrient_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_nutrients(food):
    nutrients = {key: 0 for key in NUTRIENT_ALIASES}
    nutrient_units = {}
    for nutrient in food.get("foodNutrients", []):
        name = (nutrient.get("nutrientName") or nutrient.get("name") or "").casefold()
        value = nutrient_number(nutrient.get("value") or nutrient.get("amount"))
        if value is None:
            continue
        for key, aliases in NUTRIENT_ALIASES.items():
            if name in aliases:
                unit = (nutrient.get("unitName") or nutrient.get("unit") or "").casefold()
                if key == "calories" and unit == "kj":
                    value = value / 4.184
                nutrients[key] = value
                nutrient_units[key] = nutrient.get("unitName") or nutrient.get("unit")
                break

    macro_calories = (
        nutrients["protein_g"] * 4
        + nutrients["carbohydrates_g"] * 4
        + nutrients["fat_g"] * 9
    )
    if macro_calories and nutrients["calories"] < macro_calories * 0.6:
        nutrients["calories"] = macro_calories
        nutrient_units["calories"] = "KCAL_CALCULATED_FROM_MACROS"

    return {
        key: round(value, 1) if value else 0
        for key, value in nutrients.items()
    }, nutrient_units


def tokenize_food_query(value):
    return {
        token
        for token in re.findall(r"[a-z]+", (value or "").casefold())
        if len(token) > 1
    }


def score_food_match(food, ingredient):
    query_tokens = tokenize_food_query(ingredient)
    description = (food.get("description") or "").casefold()
    category = (food.get("foodCategory") or "").casefold()
    searchable_text = f"{description} {category}"
    score = 0

    data_type = food.get("dataType")
    if data_type == "Foundation":
        score += 30
    elif data_type == "SR Legacy":
        score += 24
    elif data_type == "Survey (FNDDS)":
        score += 12

    if ingredient.casefold() in description:
        score += 60
    if query_tokens and all(token in searchable_text for token in query_tokens):
        score += 45
    score += 12 * sum(token in description for token in query_tokens)
    score += 6 * sum(token in category for token in query_tokens)

    for penalty_term in FOOD_MATCH_PENALTY_TERMS:
        if penalty_term in description and penalty_term not in query_tokens:
            score -= 90

    if "raw" in description or "fresh" in description:
        score += 12
    if "unprepared" in description:
        score += 8
    return score


def choose_food_match(foods, ingredient):
    if not foods:
        return None
    return max(foods, key=lambda food: score_food_match(food, ingredient))


def search_food_nutrition(ingredient):
    cached_result = food_search_cache.get(ingredient.casefold())
    now = time.time()
    if cached_result and now - cached_result["cached_at"] < FOOD_CACHE_TTL_SECONDS:
        return cached_result["food"]

    search_query = FOOD_SEARCH_OVERRIDES.get(ingredient.casefold(), ingredient)
    data = fetch_fooddata_json(
        f"{FDC_SEARCH_URL}?{urlencode({'api_key': FDC_API_KEY})}",
        {
            "query": search_query,
            "pageSize": 25,
            "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
        },
    )
    food = choose_food_match(data.get("foods", []), search_query)
    if not food:
        return None

    nutrients, nutrient_units = extract_nutrients(food)
    result = {
        "ingredient": ingredient,
        "description": food.get("description", ingredient).title(),
        "fdc_id": food.get("fdcId"),
        "data_type": food.get("dataType"),
        "nutrients_per_100g": nutrients,
        "nutrient_units": nutrient_units,
    }
    food_search_cache[ingredient.casefold()] = {
        "cached_at": now,
        "food": result,
    }
    return result


def extract_json_object(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def clean_dish_name(value):
    name = re.sub(r"\s+", " ", value or "").strip()
    if not name:
        return None
    generic_words = ("skillet", "bowl", "plate")
    if name.casefold() in generic_words:
        return None
    return name[:90]


def ingredient_portion_bounds(ingredient_name):
    name = (ingredient_name or "").casefold()
    if re.search(r"\b(oil|olive oil|vegetable oil|canola oil|butter|ghee)\b", name):
        return 3, 15
    if re.search(r"\b(peanut butter|almond butter|nut butter)\b", name):
        return 8, 32
    if re.search(r"\b(nuts|almonds|walnuts|cashews|pecans|peanuts|seeds|sunflower seeds|pumpkin seeds|chia|flax)\b", name):
        return 5, 30
    if re.search(r"\b(mint|basil|cilantro|parsley|dill|thyme|rosemary|oregano|sage|spice|spices|cumin|paprika|pepper|salt)\b", name):
        return 0.5, 12
    if re.search(r"\b(garlic|ginger|jalapeno|chili|lemon juice|lime juice)\b", name):
        return 2, 20
    if re.search(r"\b(cheese|cheddar|parmesan|feta|mozzarella)\b", name):
        return 10, 50
    if re.search(r"\b(egg|eggs)\b", name):
        return 45, 150
    if re.search(r"\b(beans|lentils|chickpeas|black beans|kidney beans|pinto beans)\b", name):
        return 50, 150
    if re.search(r"\b(lamb|beef|chicken|turkey|pork|fish|salmon|shrimp|tofu|tempeh)\b", name):
        return 45, 170
    if re.search(r"\b(rice|pasta|noodle|noodles|potato|potatoes|tortilla|bread|quinoa|couscous|grain|grains|oats)\b", name):
        return 40, 180
    if re.search(r"\b(fruit|apple|banana|berries|strawberries|blueberries|orange|grapes|mango|pineapple|peach|pear)\b", name):
        return 30, 180
    if re.search(r"\b(greens|spinach|lettuce|arugula|kale|spring mix|romaine)\b", name):
        return 15, 120
    if re.search(r"\b(onion|carrot|celery|broccoli|pepper|peppers|tomato|tomatoes|cabbage|zucchini|vegetable|vegetables)\b", name):
        return 20, 200
    if re.search(r"\b(sauce|salsa|dressing|yogurt|cream|broth|stock)\b", name):
        return 20, 160
    return 10, 250


def clean_grams_total(value, ingredient_name, servings):
    try:
        grams = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if grams < 1 or grams > 5000:
        return None
    min_per_serving, max_per_serving = ingredient_portion_bounds(ingredient_name)
    grams_per_serving = grams / servings
    if grams_per_serving > 250:
        return None
    if grams_per_serving < min_per_serving or grams_per_serving > max_per_serving:
        return None
    return grams


def has_valid_dish_weight(dish_name, ingredients, servings):
    total_per_serving = sum(
        ingredient["grams_total"] for ingredient in ingredients
    ) / servings
    is_soup_or_stew = bool(
        re.search(r"\b(soup|stew|chili|tagine|curry)\b", dish_name or "", re.IGNORECASE)
    )
    if is_soup_or_stew:
        return total_per_serving <= 500
    return total_per_serving <= 750


def estimate_price_per_100g(ingredient_name):
    name = (ingredient_name or "").casefold()
    for pattern, price_per_100g in PRICE_PER_100G_RULES:
        if re.search(pattern, name):
            return price_per_100g
    return DEFAULT_PRICE_PER_100G


def generate_dish_candidates(ingredients, household_size, dietary_restrictions=""):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    ingredient_text = ", ".join(ingredients)
    user_prompt = f"""
Available ingredients: {ingredient_text}
Household size: {household_size} people
Dietary restrictions: {dietary_restrictions or "none"}

Generate exactly 3 traditional, normal dishes a person would recognize by name. Prefer familiar
restaurant, home-cooking, or cookbook-style foods that naturally include at least one listed ingredient.
Do not use generic names like "skillet", "rice bowl", "warm grain bowl", or "sheet-pan plate" as
the dish name.

Rules:
- Treat the available ingredients as inspiration and anchors, not a strict pantry limit.
- Each dish must use at least one available ingredient, but you should freely add the normal ingredients
  needed for that dish, including produce, protein, starches, dairy, oil, broth, spices, sauces,
  aromatics, garnishes, or other common grocery ingredients.
- Do not invent unusual fusion dishes just to include every listed ingredient. It is better to recommend
  a normal dish that uses one or two listed ingredients well.
- Return no recipes and no steps.
- Portions must be realistic for a full dish and must be in grams for the whole recipe, not per person.
- Set servings to exactly {household_size} so the dish feeds everyone in the household.
- Use cooked-food portions when the ingredient is normally eaten cooked.
- Do not force ingredients into neat 100g, 50g, or 25g increments. Use natural portion sizes.
- Hard per-serving limits:
  no single ingredient over 250g; meat/fish up to 170g cooked; cooked grains/rice/pasta/potatoes up to 180g;
  vegetables up to 200g; salad greens up to 120g raw; fruit up to 180g; beans/lentils up to 150g cooked;
  cheese up to 50g; oils up to 15g; peanut butter up to 32g; nuts/seeds up to 30g; eggs up to 3 eggs.
- Soup/stew can be up to 500g total per serving, but no single ingredient may exceed 200g per serving.
- Multiply those per-serving amounts by servings when returning grams_total.
- Aim for main-dish portions that would usually calculate to about 500-650 calories per serving.
  Include realistic calorie-bearing staples such as oil, pasta, rice, tortillas, cheese, or sauce when the dish needs them.
- Calories will be calculated separately from USDA data, so do not estimate calories.
- Respect every dietary restriction. Do not include restricted ingredients, allergens,
  or food categories in dish names, ingredients, toppings, sauces, or garnishes.

Return this JSON shape only:
{{
  "dishes": [
    {{
      "name": "real dish name",
      "servings": {household_size},
      "portion_note": "short note with no recipe steps",
      "ingredients": [
        {{"name": "ingredient name", "grams_total": 300}}
      ]
    }}
  ]
}}
""".strip()
    response = client.responses.create(
        model=OPENAI_DISH_MODEL,
        input=[
            {"role": "system", "content": DISH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        store=False,
    )
    data = extract_json_object(response.output_text)
    dishes = []
    for dish in data.get("dishes", []):
        name = clean_dish_name(dish.get("name"))
        try:
            servings = int(dish.get("servings"))
        except (TypeError, ValueError):
            servings = household_size
        if not name or servings < MIN_HOUSEHOLD_SIZE or servings > MAX_HOUSEHOLD_SIZE:
            continue

        dish_ingredients = []
        scale_factor = household_size / servings
        seen = set()
        for ingredient in dish.get("ingredients", []):
            ingredient_name = normalize_ingredient_name(ingredient.get("name"))
            try:
                scaled_grams_total = float(ingredient.get("grams_total")) * scale_factor
            except (TypeError, ValueError):
                continue
            grams_total = clean_grams_total(
                scaled_grams_total, ingredient_name, household_size
            )
            if not ingredient_name or grams_total is None:
                continue
            identity = ingredient_name.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            dish_ingredients.append(
                {"name": ingredient_name, "grams_total": grams_total}
            )

        if (
            not dish_ingredients
            or not has_valid_dish_weight(name, dish_ingredients, household_size)
        ):
            continue
        dishes.append(
            {
                "name": name,
                "servings": household_size,
                "portion_note": re.sub(
                    r"\s+", " ", dish.get("portion_note") or ""
                ).strip()[:140],
                "ingredients": dish_ingredients[:10],
            }
        )

    if len(dishes) != 3:
        raise RuntimeError("The dish generator returned an invalid response.")
    return dishes


def generate_demo_grocery_dish_candidates(
    meal_prompt, household_size, catalog, dietary_restrictions="", pantry_items=None
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    user_prompt = f"""
User meal request: {meal_prompt}
Household size: {household_size} people
Dietary restrictions: {dietary_restrictions or "none"}
User pantry items: {pantry_items_text(pantry_items or [])}
Available grocery products JSON:
{json.dumps(catalog, separators=(",", ":"))}

Generate exactly 3 normal meal ideas that satisfy the user's request. Use only product IDs from the
available grocery products JSON. Optimize across:
- price: prefer sale prices, lower total package cost, and overlapping inexpensive staples
- taste: choose familiar, coherent meals people would actually want to eat
- health: include balanced food groups when possible and avoid meals that are only starch or only dairy

Rules:
- The user is describing the kind of meal they want, not listing pantry ingredients.
- Prefer meals that can use pantry items when compatible, but only return product IDs
  from the available grocery products JSON for items the user still needs to buy.
- Choose 3 to 6 grocery products per dish.
- Use product_id values exactly as provided.
- Every selected product must be an actual ingredient or direct topping/filling in the named dish.
- Do not add unrelated sides, snacks, drinks, desserts, or fruit just to improve health or calories.
- Fruit products are only allowed when the dish name or user request is a fruit-forward meal, such as
  oatmeal, yogurt, smoothie, fruit bowl, peanut butter toast, pancakes, or a salad that names fruit.
- If the user requests a food that is unavailable in the catalog, choose the closest normal substitute
  available in the catalog and mention the substitution in portion_note.
- grams_total is the amount used by the whole household meal, not the full package unless needed.
- grams_total may be less than package_grams because the shopper buys the package and uses part of it.
- Keep portions realistic for {household_size} people.
- Return short notes only, with no recipes and no cooking steps.
- Respect every dietary restriction. Do not choose restricted ingredients, allergens,
  or food categories even if they appear in the available grocery products JSON.

Return this JSON shape only:
{{
  "dishes": [
    {{
      "name": "normal recognizable meal name",
      "portion_note": "why this balances price, taste, and health",
      "products": [
        {{"product_id": "p001", "grams_total": 300}}
      ]
    }}
  ]
}}
""".strip()
    response = client.responses.create(
        model=OPENAI_DISH_MODEL,
        input=[
            {"role": "system", "content": DISH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        store=False,
    )
    data = extract_json_object(response.output_text)
    dishes = []
    valid_product_ids = {product["id"] for product in catalog if product.get("id")}

    for dish in data.get("dishes", []):
        name = clean_dish_name(dish.get("name"))
        if not name:
            continue

        selected_products = []
        seen = set()
        for product in dish.get("products", []):
            product_id = str(product.get("product_id") or "").strip()
            if product_id not in valid_product_ids or product_id in seen:
                continue
            try:
                grams_total = int(round(float(product.get("grams_total"))))
            except (TypeError, ValueError):
                continue
            if grams_total < 1 or grams_total > 5000:
                continue
            seen.add(product_id)
            selected_products.append(
                {"product_id": product_id, "grams_total": grams_total}
            )

        if len(selected_products) < 2:
            continue
        dishes.append(
            {
                "name": name,
                "servings": household_size,
                "portion_note": re.sub(
                    r"\s+", " ", dish.get("portion_note") or ""
                ).strip()[:180],
                "products": selected_products[:6],
            }
        )

    if len(dishes) != 3:
        raise RuntimeError("The meal generator could not build 3 grocery-backed dishes.")
    return dishes


def generate_recipe_search_ideas(
    meal_prompt, household_size, dietary_restrictions="", pantry_items=None
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    requested_cuisine = detect_requested_spoonacular_cuisine(meal_prompt)
    client = OpenAI(api_key=api_key)
    user_prompt = f"""
User meal request: {meal_prompt}
Household size: {household_size} people
Dietary restrictions: {dietary_restrictions or "none"}
User pantry items: {pantry_items_text(pantry_items or [])}
Detected cuisine, if any: {requested_cuisine or "none"}

Generate {RECIPE_IDEA_COUNT} normal, recognizable recipe ideas that a real recipe site is likely to have.
These are search targets, not recipes.

Rules:
- Make each idea a specific dish name, not a vague category.
- Keep ideas realistic, familiar, and searchable.
- If a cuisine was detected, every idea must strictly belong to that cuisine.
- If no cuisine was detected, make the ideas intentionally diverse across cuisines and formats.
- Respect dietary restrictions; do not include restricted ingredients or allergens.
- Prefer ideas compatible with pantry items when that feels natural.
- Return no ingredients, no cooking steps, and no prose outside JSON.

Return this JSON shape only:
{{
  "ideas": [
    {{"name": "specific dish name", "query": "specific recipe search query", "cuisine": "Cuisine or empty string"}}
  ]
}}
""".strip()
    response = client.responses.create(
        model=OPENAI_DISH_MODEL,
        input=[
            {"role": "system", "content": DISH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        store=False,
    )
    data = extract_json_object(response.output_text)
    ideas = []
    seen = set()
    for idea in data.get("ideas", []):
        name = clean_dish_name(idea.get("name"))
        query = re.sub(r"\s+", " ", idea.get("query") or name or "").strip()
        cuisine = re.sub(r"\s+", " ", idea.get("cuisine") or "").strip()
        if not query:
            continue
        identity = query.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        ideas.append(
            {
                "name": name or query,
                "query": query,
                "cuisine": cuisine,
            }
        )

    if not ideas:
        raise RuntimeError("The recipe idea generator returned an invalid response.")
    return ideas[:RECIPE_IDEA_COUNT]


def build_dishes(dish_candidates):
    dishes = []
    missing_ingredients = []
    for candidate in dish_candidates:
        ingredient_lines = []
        candidate_missing_ingredients = []
        total_calories = 0
        total_price = 0
        total_nutrients = {
            "protein_g": 0,
            "carbohydrates_g": 0,
            "fat_g": 0,
            "fiber_g": 0,
            "sugars_g": 0,
            "sodium_mg": 0,
        }
        servings = candidate["servings"]
        for ingredient in candidate["ingredients"]:
            food = search_food_nutrition(ingredient["name"])
            if not food:
                candidate_missing_ingredients.append(ingredient["name"])
                continue
            grams_total = ingredient["grams_total"]
            grams_per_person = round(grams_total / servings)
            nutrients = food["nutrients_per_100g"]
            recipe_multiplier = grams_total / 100
            ingredient_total_calories = nutrients["calories"] * recipe_multiplier
            ingredient_total_price = estimate_price_per_100g(ingredient["name"]) * recipe_multiplier
            total_calories += ingredient_total_calories
            total_price += ingredient_total_price
            for key in total_nutrients:
                total_nutrients[key] += nutrients[key] * recipe_multiplier
            ingredient_lines.append(
                {
                    "name": ingredient["name"],
                    "matched_food": food["description"],
                    "grams_per_person": grams_per_person,
                    "grams_total": grams_total,
                    "fdc_id": food["fdc_id"],
                    "calories_per_person": round(ingredient_total_calories / servings),
                    "calories_total": round(ingredient_total_calories),
                    "estimated_price_per_serving": round(ingredient_total_price / servings, 2),
                    "estimated_price_total": round(ingredient_total_price, 2),
                }
            )
        if candidate_missing_ingredients:
            missing_ingredients.extend(candidate_missing_ingredients)
            continue
        if not ingredient_lines:
            continue

        dishes.append(
            {
                "name": candidate["name"],
                "servings": servings,
                "calories_total": round(total_calories),
                "calories_per_person": round(total_calories / servings),
                "estimated_price_total": round(total_price, 2),
                "estimated_price_per_serving": round(total_price / servings, 2),
                "nutrition_total": {
                    key: round(value, 1)
                    for key, value in total_nutrients.items()
                },
                "nutrition_per_person": {
                    key: round(value / servings, 1)
                    for key, value in total_nutrients.items()
                },
                "ingredients": ingredient_lines,
                "ingredients_to_buy": ingredient_lines,
                "portion_note": candidate["portion_note"],
                "method": candidate["portion_note"],
            }
        )
    if len(dishes) != 3:
        raise RuntimeError("USDA nutrition data could not be matched for all generated dishes.")
    return dishes, sorted(set(missing_ingredients), key=str.casefold)


def build_demo_grocery_dishes(dish_candidates, products_by_id, stores):
    dishes = []
    for candidate in dish_candidates:
        ingredient_lines = []
        total_calories = 0
        total_price = 0
        total_nutrients = {
            "protein_g": 0,
            "carbohydrates_g": 0,
            "fat_g": 0,
            "fiber_g": 0,
            "sugars_g": 0,
            "sodium_mg": 0,
        }
        servings = candidate["servings"]
        seen_product_ids = set()

        for selected in candidate["products"]:
            product = products_by_id.get(selected["product_id"])
            if not product or selected["product_id"] in seen_product_ids:
                continue
            if not is_fruit_appropriate_for_dish(
                product, candidate["name"], candidate["portion_note"]
            ):
                continue
            seen_product_ids.add(selected["product_id"])
            grams_total = min(selected["grams_total"], int(product.get("package_grams") or 0))
            if grams_total < 1:
                continue

            package_price = product_effective_price(product)
            calories_total = (float(product.get("calories_per_100g") or 0) * grams_total) / 100
            total_calories += calories_total
            total_price += package_price
            add_nutrients(
                total_nutrients,
                nutrition_from_calories(
                    calories_total, grams_total, product.get("food_group")
                ),
            )
            store = stores.get(product.get("store_id"), {})
            ingredient_lines.append(
                {
                    "product_id": product.get("id"),
                    "name": product.get("ingredient"),
                    "product_name": product.get("product_name"),
                    "matched_food": product.get("product_name"),
                    "food_group": product.get("food_group"),
                    "store_name": store.get("name", product.get("store_id")),
                    "package_size": product.get("package_size"),
                    "package_grams": product.get("package_grams"),
                    "grams_total": grams_total,
                    "grams_per_person": round(grams_total / servings),
                    "calories_total": round(calories_total),
                    "calories_per_person": round(calories_total / servings),
                    "estimated_price_total": package_price,
                    "estimated_price_per_serving": round(package_price / servings, 2),
                }
            )

        if len(ingredient_lines) < 2:
            continue

        dishes.append(
            {
                "name": candidate["name"],
                "servings": servings,
                "calories_total": round(total_calories),
                "calories_per_person": round(total_calories / servings),
                "estimated_price_total": round(total_price, 2),
                "estimated_price_per_serving": round(total_price / servings, 2),
                "nutrition_total": {
                    key: round(value, 1)
                    for key, value in total_nutrients.items()
                },
                "nutrition_per_person": {
                    key: round(value / servings, 1)
                    for key, value in total_nutrients.items()
                },
                "ingredients": ingredient_lines,
                "ingredients_to_buy": ingredient_lines,
                "portion_note": candidate["portion_note"],
                "method": candidate["portion_note"],
            }
        )

    if len(dishes) != 3:
        raise RuntimeError("The grocery database could not support 3 complete dish ideas.")
    return dishes


def spoonacular_ingredients(recipe):
    ingredients = []
    seen = set()
    for ingredient in recipe.get("extendedIngredients") or []:
        name = re.sub(
            r"\s+",
            " ",
            ingredient.get("nameClean")
            or ingredient.get("name")
            or ingredient.get("originalName")
            or "",
        ).strip()
        if not name:
            continue
        measure = re.sub(r"\s+", " ", ingredient.get("original") or "").strip()
        display = measure or name
        identity = name.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        ingredients.append(
            {
                "name": name,
                "measure": measure,
                "display": display,
            }
        )
    return ingredients


def mealdb_recipe_ingredients(meal):
    ingredients = []
    seen = set()
    for index in range(1, 21):
        raw_name = meal.get(f"strIngredient{index}") or ""
        raw_measure = meal.get(f"strMeasure{index}") or ""
        name = normalize_ingredient_name(raw_name)
        measure = re.sub(r"\s+", " ", raw_measure).strip()
        if not name:
            continue
        identity = name.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        display = f"{measure} {name}".strip() if measure else name
        ingredients.append(
            {
                "name": name,
                "measure": display,
                "display": display,
            }
        )
    return ingredients


def mealdb_recipe_id(meal):
    meal_id = str((meal or {}).get("idMeal") or "").strip()
    return f"mealdb:{meal_id}" if meal_id else ""


def mealdb_recipe_to_recipe(meal):
    meal_id = str((meal or {}).get("idMeal") or "").strip()
    name = re.sub(r"\s+", " ", (meal or {}).get("strMeal") or "").strip()
    if not meal_id or not name:
        return None
    source = (
        meal.get("strSource")
        or f"https://www.themealdb.com/meal/{meal_id}"
    )
    return {
        "id": mealdb_recipe_id(meal),
        "title": name,
        "cuisines": [meal.get("strArea")] if meal.get("strArea") else [],
        "dishTypes": [meal.get("strCategory")] if meal.get("strCategory") else ["main course"],
        "extendedIngredients": mealdb_recipe_ingredients(meal),
        "instructions": spoonacular_recipe_text(meal.get("strInstructions") or ""),
        "image": meal.get("strMealThumb"),
        "sourceUrl": source,
        "spoonacularSourceUrl": source,
        "_snapp_recipe_provider": "TheMealDB",
        "_snapp_youtube": meal.get("strYoutube"),
    }


def search_mealdb_meals(query):
    normalized_query = re.sub(r"\s+", " ", query or "").strip()
    if not normalized_query:
        return []
    cache_key = normalized_query.casefold()
    cached = mealdb_search_cache.get(cache_key)
    if cached is not None:
        return cached
    data = fetch_mealdb_json("search.php", {"s": normalized_query})
    meals = data.get("meals") or []
    mealdb_search_cache[cache_key] = meals
    return meals


def lookup_mealdb_meal(meal_id):
    meal_id = str(meal_id or "").strip()
    if not meal_id:
        return None
    cached = mealdb_lookup_cache.get(meal_id)
    if cached is not None:
        return cached
    data = fetch_mealdb_json("lookup.php", {"i": meal_id})
    meals = data.get("meals") or []
    meal = meals[0] if meals else None
    mealdb_lookup_cache[meal_id] = meal
    return meal


def mealdb_filter_meals(filter_key, value):
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return []
    data = fetch_mealdb_json("filter.php", {filter_key: value})
    summaries = data.get("meals") or []
    meals = []
    for summary in summaries[:THEMEALDB_SEARCH_LIMIT]:
        meal = lookup_mealdb_meal(summary.get("idMeal"))
        if meal:
            meals.append(meal)
    return meals


def mealdb_categories_for_text(value):
    text = f" {normalize_cuisine_text(value)} "
    categories = []
    category_rules = (
        (r"\b(breakfast|brunch|morning|egg|eggs)\b", "Breakfast"),
        (r"\b(vegetarian|veggie|meatless|plant based)\b", "Vegetarian"),
        (r"\b(vegan)\b", "Vegan"),
        (r"\b(chicken|poultry|high protein|protein)\b", "Chicken"),
        (r"\b(beef|steak|burger|high protein|protein)\b", "Beef"),
        (r"\b(pork|ham|bacon|sausage)\b", "Pork"),
        (r"\b(fish|seafood|salmon|tuna|shrimp|prawn|high protein|protein)\b", "Seafood"),
        (r"\b(pasta|spaghetti|noodle|noodles)\b", "Pasta"),
        (r"\b(dessert|sweet|cake|cookie|cookies)\b", "Dessert"),
    )
    for pattern, category in category_rules:
        if re.search(pattern, text) and category not in categories:
            categories.append(category)
    if not categories and re.search(r"\b(dinner|lunch|meal|cheap|healthy|easy|quick)\b", text):
        categories.extend(["Chicken", "Vegetarian", "Pasta", "Seafood"])
    return categories


def mealdb_candidates_for_ideas(recipe_ideas, meal_prompt):
    candidates = []
    seen_ids = set()
    search_terms = []
    for idea in recipe_ideas:
        search_terms.extend(
            value
            for value in (idea.get("query"), idea.get("name"))
            if value
        )
    search_terms.append(meal_prompt)

    for query in search_terms:
        for meal in search_mealdb_meals(query):
            recipe = mealdb_recipe_to_recipe(meal)
            recipe_id = spoonacular_recipe_id(recipe or {})
            if recipe and recipe_id not in seen_ids:
                candidates.append(recipe)
                seen_ids.add(recipe_id)
            if len(candidates) >= THEMEALDB_SEARCH_LIMIT:
                return candidates

    requested_area = detect_requested_spoonacular_cuisine(meal_prompt)
    idea_areas = [
        idea.get("cuisine")
        for idea in recipe_ideas
        if idea.get("cuisine")
    ]
    for area in [requested_area, *idea_areas]:
        for meal in mealdb_filter_meals("a", "American" if area == "United States" else area):
            recipe = mealdb_recipe_to_recipe(meal)
            recipe_id = spoonacular_recipe_id(recipe or {})
            if recipe and recipe_id not in seen_ids:
                candidates.append(recipe)
                seen_ids.add(recipe_id)
            if len(candidates) >= THEMEALDB_SEARCH_LIMIT:
                return candidates

    requested_ingredients = requested_spoonacular_ingredient_groups(meal_prompt)
    for ingredient, _aliases in requested_ingredients:
        for meal in mealdb_filter_meals("i", ingredient):
            recipe = mealdb_recipe_to_recipe(meal)
            recipe_id = spoonacular_recipe_id(recipe or {})
            if recipe and recipe_id not in seen_ids:
                candidates.append(recipe)
                seen_ids.add(recipe_id)
            if len(candidates) >= THEMEALDB_SEARCH_LIMIT:
                return candidates

    category_text = " ".join(
        [meal_prompt]
        + [
            " ".join([idea.get("name") or "", idea.get("query") or ""])
            for idea in recipe_ideas
        ]
    )
    for category in mealdb_categories_for_text(category_text):
        for meal in mealdb_filter_meals("c", category):
            recipe = mealdb_recipe_to_recipe(meal)
            recipe_id = spoonacular_recipe_id(recipe or {})
            if recipe and recipe_id not in seen_ids:
                candidates.append(recipe)
                seen_ids.add(recipe_id)
            if len(candidates) >= THEMEALDB_SEARCH_LIMIT:
                return candidates

    return candidates


def spoonacular_recipe_text(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()


def spoonacular_cuisines(recipe):
    cuisines = recipe.get("cuisines") or []
    if isinstance(cuisines, str):
        cuisines = [cuisines]
    return [cuisine for cuisine in cuisines if cuisine]


def spoonacular_cuisine_label(recipe):
    return (spoonacular_cuisines(recipe) or [recipe.get("_snapp_requested_cuisine") or ""])[0]


def normalized_spoonacular_cuisine(value):
    normalized = normalize_cuisine_text(value)
    return "american" if normalized == "united states" else normalized


def spoonacular_matches_requested_cuisine(recipe, requested_cuisine):
    if not requested_cuisine:
        return True

    requested = normalized_spoonacular_cuisine(requested_cuisine)
    return any(
        normalized_spoonacular_cuisine(cuisine) == requested
        for cuisine in spoonacular_cuisines(recipe)
    )


def spoonacular_recipe_id(recipe):
    recipe_id = recipe.get("id")
    return str(recipe_id) if recipe_id else ""


def spoonacular_text_for_restrictions(recipe):
    return " ".join(
        [
            recipe.get("title") or "",
            " ".join(recipe.get("dishTypes") or []),
            " ".join(spoonacular_cuisines(recipe)),
            " ".join(ingredient["display"] for ingredient in spoonacular_ingredients(recipe)),
        ]
    )


def spoonacular_respects_restrictions(recipe, dietary_restrictions):
    if not dietary_restrictions:
        return True
    meal_text = spoonacular_text_for_restrictions(recipe)
    return not any(
        restriction_pattern.search(dietary_restrictions)
        and ingredient_pattern.search(meal_text)
        for restriction_pattern, ingredient_pattern in RESTRICTION_RULES
    )


def search_spoonacular_recipes(
    query,
    cuisine=None,
    dietary_restrictions="",
    number=SPOONACULAR_SEARCH_RESULT_COUNT,
    sort=None,
):
    normalized_query = re.sub(r"\s+", " ", query or "").strip()
    if not normalized_query and not cuisine:
        return []

    cache_key = (
        normalized_query.casefold(),
        (cuisine or "").casefold(),
        normalize_cuisine_text(dietary_restrictions),
        int(number),
        sort or "",
    )
    cached = spoonacular_search_cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "query": normalized_query,
        "number": number,
        "addRecipeInformation": "true",
        "fillIngredients": "true",
        "instructionsRequired": "true",
    }
    if cuisine:
        params["cuisine"] = cuisine
    if sort:
        params["sort"] = sort
    intolerances = spoonacular_intolerances_from_restrictions(dietary_restrictions)
    if intolerances:
        params["intolerances"] = intolerances

    data = fetch_spoonacular_json("recipes/complexSearch", params)
    recipes = data.get("results") or []
    if cuisine:
        for recipe in recipes:
            recipe.setdefault("_snapp_requested_cuisine", cuisine)
    spoonacular_search_cache[cache_key] = recipes
    return recipes


def lookup_spoonacular_recipe(recipe_id):
    recipe_id = str(recipe_id or "")
    if not recipe_id:
        return None
    cached = spoonacular_lookup_cache.get(recipe_id)
    if cached is not None:
        return cached

    recipe = fetch_spoonacular_json(
        f"recipes/{recipe_id}/information",
        {"includeNutrition": "false"},
    )
    spoonacular_lookup_cache[recipe_id] = recipe
    return recipe


def fetch_random_spoonacular_recipes(
    dietary_restrictions,
    used_ids=None,
    cuisine=None,
    number=SPOONACULAR_RANDOM_RESULT_COUNT,
):
    include_tags = ["main course"]
    if cuisine:
        include_tags.append(cuisine)
    params = {"number": number, "include-tags": ",".join(include_tags)}
    intolerances = spoonacular_intolerances_from_restrictions(dietary_restrictions)
    if intolerances:
        params["intolerances"] = intolerances
    data = fetch_spoonacular_json("recipes/random", params)
    recipes = data.get("recipes") or []
    filtered_recipes = []
    seen_ids = set(used_ids or set())
    for recipe in recipes:
        recipe_id = spoonacular_recipe_id(recipe)
        if cuisine:
            recipe.setdefault("_snapp_requested_cuisine", cuisine)
        if (
            recipe_id
            and recipe_id not in seen_ids
            and spoonacular_ingredients(recipe)
            and spoonacular_respects_restrictions(recipe, dietary_restrictions)
        ):
            filtered_recipes.append(recipe)
            seen_ids.add(recipe_id)
    return filtered_recipes


def normalize_cuisine_text(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def detect_requested_spoonacular_cuisine(meal_prompt):
    prompt_text = f" {normalize_cuisine_text(meal_prompt)} "
    for alias, area in sorted(
        RECIPE_CUISINE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if re.search(rf"\b{re.escape(alias)}\b", prompt_text):
            return "American" if area == "United States" else area
    return None


def spoonacular_prompt_score(recipe, meal_prompt):
    recipe_words = normalized_food_words(recipe.get("title"))
    prompt_words = {
        word
        for word in normalized_food_words(meal_prompt)
        if word not in RECIPE_SEARCH_STOPWORDS
    }
    score = len(recipe_words & prompt_words)
    meal_text = spoonacular_normalized_search_text(recipe)
    for meal_type, terms in RECIPE_MEAL_TYPE_HINTS.items():
        if re.search(rf"\b{meal_type}\b", meal_prompt, re.I):
            score += sum(2 for term in terms if term in meal_text)
    if re.search(r"\bdinner\b", meal_prompt, re.I):
        score -= sum(3 for term in RECIPE_NON_DINNER_TERMS if term in meal_text)
    return score


def requested_spoonacular_ingredient_groups(meal_prompt):
    prompt_words = normalized_food_words(meal_prompt)
    requested = []
    for ingredient, aliases in RECIPE_REQUEST_INGREDIENTS.items():
        ingredient_words = normalized_food_words(ingredient)
        if prompt_words & ingredient_words:
            requested.append((ingredient, aliases))
    return requested


def is_generic_spoonacular_prompt(meal_prompt):
    prompt_words = normalized_food_words(meal_prompt)
    return bool(prompt_words) and prompt_words <= RECIPE_GENERIC_PROMPT_WORDS


def spoonacular_normalized_search_text(recipe):
    return normalize_cuisine_text(
        " ".join(
            [
                recipe.get("title") or "",
                " ".join(recipe.get("dishTypes") or []),
                " ".join(spoonacular_cuisines(recipe)),
                " ".join(ingredient["name"] for ingredient in spoonacular_ingredients(recipe)),
            ]
        )
    )


def spoonacular_matches_requested_ingredients(recipe, requested_ingredient_groups):
    if not requested_ingredient_groups:
        return True
    meal_text = f" {spoonacular_normalized_search_text(recipe)} "
    return all(
        spoonacular_matches_requested_ingredient(recipe, ingredient, aliases, meal_text)
        for ingredient, aliases in requested_ingredient_groups
    )


def spoonacular_matches_requested_ingredient(recipe, ingredient, aliases, meal_text):
    if ingredient in {"beef", "chicken", "fish", "pork", "shrimp", "tuna", "salmon"}:
        primary_text = (
            f" {normalize_cuisine_text(recipe.get('title'))} "
            f"{normalize_cuisine_text(' '.join(recipe.get('dishTypes') or []))} "
        )
        if any(
            re.search(rf"\b{re.escape(normalize_cuisine_text(alias))}\b", primary_text)
            for alias in aliases
        ):
            return True
        for recipe_ingredient in spoonacular_ingredients(recipe)[:5]:
            ingredient_name = normalize_cuisine_text(recipe_ingredient["name"])
            if re.search(r"\b(stock|broth|bouillon|extract|flavouring|flavoring)\b", ingredient_name):
                continue
            if any(
                re.search(rf"\b{re.escape(normalize_cuisine_text(alias))}\b", ingredient_name)
                for alias in aliases
            ):
                return True
        return False

    return any(
        re.search(rf"\b{re.escape(normalize_cuisine_text(alias))}\b", meal_text)
        for alias in aliases
    )


def spoonacular_matches_meal_type(recipe, meal_prompt):
    if not re.search(r"\bdinner\b", meal_prompt or "", re.I):
        return True
    meal_text = spoonacular_normalized_search_text(recipe)
    dish_types = {normalize_cuisine_text(value) for value in recipe.get("dishTypes") or []}
    if dish_types & {"breakfast", "dessert", "side dish", "starter", "appetizer"}:
        return False
    return not any(
        re.search(rf"\b{re.escape(term)}\b", meal_text)
        for term in RECIPE_NON_DINNER_TERMS
    )


def spoonacular_diversity_key(recipe):
    cuisine = spoonacular_cuisine_label(recipe)
    if cuisine:
        return f"cuisine:{normalized_spoonacular_cuisine(cuisine)}"

    title = normalize_cuisine_text(recipe.get("title"))
    for term in (
        "bowl",
        "soup",
        "stew",
        "salad",
        "sandwich",
        "wrap",
        "taco",
        "tacos",
        "pasta",
        "curry",
        "casserole",
        "stir fry",
        "skillet",
        "roast",
        "burger",
        "pizza",
    ):
        if re.search(rf"\b{re.escape(term)}\b", title):
            return f"style:{term}"

    dish_types = [
        normalize_cuisine_text(value)
        for value in recipe.get("dishTypes") or []
        if normalize_cuisine_text(value)
    ]
    if dish_types:
        return f"type:{dish_types[0]}"

    title_words = [
        word
        for word in title.split()
        if word not in RECIPE_SEARCH_STOPWORDS
    ]
    return f"title:{' '.join(title_words[:2])}" if title_words else ""


def spoonacular_candidates_for_prompt(meal_prompt, dietary_restrictions):
    candidates = []
    seen_ids = set()
    for recipe in search_spoonacular_recipes(
        meal_prompt,
        dietary_restrictions=dietary_restrictions,
    ):
        recipe_id = spoonacular_recipe_id(recipe)
        if recipe_id and recipe_id not in seen_ids:
            candidates.append(recipe)
            seen_ids.add(recipe_id)
    return candidates


def spoonacular_candidates_for_ideas(recipe_ideas, dietary_restrictions, cuisine=None):
    candidates = []
    seen_ids = set()
    for idea in recipe_ideas[:SPOONACULAR_IDEA_SEARCH_LIMIT]:
        idea_cuisine = cuisine or idea.get("cuisine") or None
        for recipe in search_spoonacular_recipes(
            idea["query"],
            cuisine=idea_cuisine,
            dietary_restrictions=dietary_restrictions,
            number=max(6, SPOONACULAR_SEARCH_RESULT_COUNT // 2),
        ):
            recipe_id = spoonacular_recipe_id(recipe)
            if recipe_id and recipe_id not in seen_ids:
                candidates.append(recipe)
                seen_ids.add(recipe_id)
    return sorted(
        candidates,
        key=lambda recipe: max(
            spoonacular_prompt_score(recipe, idea["query"])
            for idea in recipe_ideas
        ),
        reverse=True,
    )


def spoonacular_candidates_for_cuisine(cuisine, meal_prompt, dietary_restrictions):
    candidates = search_spoonacular_recipes(
        meal_prompt,
        cuisine=cuisine,
        dietary_restrictions=dietary_restrictions,
    )
    for recipe in candidates:
        recipe.setdefault("_snapp_requested_cuisine", cuisine)
    random.shuffle(candidates)
    return sorted(
        candidates,
        key=lambda recipe: spoonacular_prompt_score(recipe, meal_prompt),
        reverse=True,
    )


def spoonacular_diverse_cuisine_candidates(meal_prompt, source_candidates, already_seen_ids, max_candidates=8):
    candidates = []
    recipes_by_cuisine = {}
    uncategorized = []
    for recipe in source_candidates:
        recipe_id = spoonacular_recipe_id(recipe)
        if not recipe_id or recipe_id in already_seen_ids:
            continue
        cuisine = spoonacular_cuisine_label(recipe)
        if cuisine:
            recipes_by_cuisine.setdefault(cuisine, []).append(recipe)
        else:
            uncategorized.append(recipe)

    cuisine_order = list(recipes_by_cuisine)
    random.shuffle(cuisine_order)
    for cuisine in cuisine_order:
        if len(candidates) >= max_candidates:
            break
        viable_recipes = list(recipes_by_cuisine[cuisine])
        viable_recipes = [
            recipe
            for recipe in viable_recipes
            if spoonacular_matches_meal_type(recipe, meal_prompt)
        ] or viable_recipes
        if viable_recipes:
            random.shuffle(viable_recipes)
            candidates.append(
                sorted(
                    viable_recipes[:8],
                    key=lambda recipe: spoonacular_prompt_score(recipe, meal_prompt),
                    reverse=True,
                )[0]
            )

    if len(candidates) < max_candidates and uncategorized:
        random.shuffle(uncategorized)
        candidates.extend(uncategorized[: max_candidates - len(candidates)])
    return candidates


def normalized_food_words(value):
    text = re.sub(r"[^a-z0-9\s]", " ", value or "").casefold()
    words = {
        word[:-1] if word.endswith("s") and len(word) > 3 else word
        for word in text.split()
        if len(word) > 2
    }
    return words


def normalized_recipe_name(value):
    return re.sub(r"[^a-z0-9]+", " ", value or "").strip().casefold()


def product_matches_recipe_ingredient(product, recipe_ingredient):
    product_ingredient = product.get("ingredient") or ""
    product_terms = {product_ingredient.casefold()}
    product_terms.update(RECIPE_INGREDIENT_ALIASES.get(product_ingredient.casefold(), set()))

    recipe_text = recipe_ingredient.casefold()
    recipe_terms = {recipe_text}
    recipe_terms.update(RECIPE_INGREDIENT_ALIASES.get(recipe_text, set()))

    if any(
        product_term in recipe_text or recipe_term in product_ingredient.casefold()
        for product_term in product_terms
        for recipe_term in recipe_terms
    ):
        return True

    return bool(
        normalized_food_words(product_ingredient)
        & normalized_food_words(recipe_ingredient)
    )


def match_recipe_ingredients_to_products(recipe, products):
    matches = []
    used_product_ids = set()
    for ingredient in spoonacular_ingredients(recipe):
        eligible_products = [
            product
            for product in products
            if product.get("id") not in used_product_ids
            and product_matches_recipe_ingredient(product, ingredient["name"])
        ]
        if not eligible_products:
            continue
        product = sorted(eligible_products, key=product_effective_price)[0]
        used_product_ids.add(product["id"])
        matches.append((ingredient, product))
    return matches


def spoonacular_recipe_to_demo_dish(recipe, matched_products, stores, household_size):
    ingredient_lines = []
    total_calories = 0
    total_price = 0
    total_nutrients = {
        "protein_g": 0,
        "carbohydrates_g": 0,
        "fat_g": 0,
        "fiber_g": 0,
        "sugars_g": 0,
        "sodium_mg": 0,
    }

    for recipe_ingredient, product in matched_products[:6]:
        package_grams = int(product.get("package_grams") or 0)
        grams_total = min(package_grams, max(80, household_size * 125))
        if grams_total < 1:
            continue

        package_price = product_effective_price(product)
        calories_total = (float(product.get("calories_per_100g") or 0) * grams_total) / 100
        total_calories += calories_total
        total_price += package_price
        add_nutrients(
            total_nutrients,
            nutrition_from_calories(
                calories_total, grams_total, product.get("food_group")
            ),
        )
        store = stores.get(product.get("store_id"), {})
        ingredient_lines.append(
            {
                "product_id": product.get("id"),
                "name": product.get("ingredient"),
                "recipe_ingredient": recipe_ingredient["name"],
                "recipe_measure": recipe_ingredient["measure"],
                "product_name": product.get("product_name"),
                "matched_food": product.get("product_name"),
                "food_group": product.get("food_group"),
                "store_name": store.get("name", product.get("store_id")),
                "package_size": product.get("package_size"),
                "package_grams": product.get("package_grams"),
                "grams_total": grams_total,
                "grams_per_person": round(grams_total / household_size),
                "calories_total": round(calories_total),
                "calories_per_person": round(calories_total / household_size),
                "estimated_price_total": package_price,
                "estimated_price_per_serving": round(package_price / household_size, 2),
            }
        )

    provider = recipe.get("_snapp_recipe_provider") or "web"
    provider_name = provider if provider == "TheMealDB" else (
        "web recipe source" if provider == "web" else "recipe database"
    )
    recipe = spoonacular_recipe_from_recipe(recipe)
    return {
        "name": recipe["name"],
        "servings": household_size,
        "calories_total": round(total_calories),
        "calories_per_person": round(total_calories / household_size),
        "estimated_price_total": round(total_price, 2),
        "estimated_price_per_serving": round(total_price / household_size, 2),
        "nutrition_total": {
            key: round(value, 1)
            for key, value in total_nutrients.items()
        },
        "nutrition_per_person": {
            key: round(value / household_size, 1)
            for key, value in total_nutrients.items()
        },
        "ingredients": ingredient_lines,
        "ingredients_to_buy": ingredient_lines,
        "portion_note": f"Recipe from {provider_name}. Grocery matches are from the SNAPP grocery pricing database.",
        "method": recipe["instructions"],
        "recipe": recipe,
        "recipe_id": recipe["id"],
        "recipe_source": recipe["source"],
        "spoonacular_id": recipe["id"],
        "spoonacular_source": recipe["source"],
        "recipe_provider": provider,
    }


def build_spoonacular_demo_grocery_dishes(
    meal_prompt,
    household_size,
    dietary_restrictions,
    products,
    stores,
    recipe_ideas=None,
):
    dishes = []
    used_ids = set()
    used_areas = set()
    used_diversity_keys = set()
    used_recipe_names = set()
    requested_area = detect_requested_spoonacular_cuisine(meal_prompt)
    requested_ingredient_groups = requested_spoonacular_ingredient_groups(meal_prompt)
    is_generic_prompt = (
        not requested_area
        and not requested_ingredient_groups
        and is_generic_spoonacular_prompt(meal_prompt)
    )
    effective_recipe_ideas = recipe_ideas or [
        {"name": meal_prompt, "query": meal_prompt, "cuisine": requested_area or ""}
    ]

    def try_add_recipe(recipe, minimum_matches, require_new_area=False):
        recipe_id = spoonacular_recipe_id(recipe)
        meal_area = spoonacular_cuisine_label(recipe)
        diversity_key = spoonacular_diversity_key(recipe)
        recipe_name = normalized_recipe_name(recipe.get("title"))
        if not recipe_id or recipe_id in used_ids:
            return False
        if recipe_name in used_recipe_names:
            return False
        if requested_area and not spoonacular_matches_requested_cuisine(
            recipe, requested_area
        ):
            return False
        if require_new_area and not meal_area:
            if not diversity_key:
                return False
        if require_new_area and meal_area in used_areas:
            return False
        if require_new_area and diversity_key in used_diversity_keys:
            return False
        if not spoonacular_ingredients(recipe):
            return False
        if not spoonacular_matches_requested_ingredients(
            recipe, requested_ingredient_groups
        ):
            return False
        if not spoonacular_matches_meal_type(recipe, meal_prompt):
            return False
        if not spoonacular_respects_restrictions(recipe, dietary_restrictions):
            return False
        matches = match_recipe_ingredients_to_products(recipe, products)
        if len(matches) < minimum_matches:
            return False
        dishes.append(spoonacular_recipe_to_demo_dish(recipe, matches, stores, household_size))
        used_ids.add(recipe_id)
        used_recipe_names.add(recipe_name)
        if meal_area:
            used_areas.add(meal_area)
        if diversity_key:
            used_diversity_keys.add(diversity_key)
        return True

    web_candidates = fetch_web_recipe_candidates(effective_recipe_ideas)
    candidates = []
    fallback_candidates = []

    web_passes = (
        [(2, False), (1, False), (0, False)]
        if requested_area
        else [(2, True), (1, True), (0, True), (1, False), (0, False)]
    )
    for minimum_matches, require_new_area in web_passes:
        for recipe in web_candidates:
            if len(dishes) == 3:
                return dishes
            try_add_recipe(recipe, minimum_matches, require_new_area)

    if not SPOONACULAR_API_KEY:
        if len(dishes) != 3:
            raise RuntimeError("Recipe sources could not provide 3 recipe-backed dishes.")
        return dishes

    if recipe_ideas:
        candidates = spoonacular_candidates_for_ideas(
            effective_recipe_ideas,
            dietary_restrictions,
            cuisine=requested_area,
        )
    else:
        candidates = (
            spoonacular_candidates_for_cuisine(requested_area, meal_prompt, dietary_restrictions)
            if requested_area
            else [] if is_generic_prompt else spoonacular_candidates_for_prompt(meal_prompt, dietary_restrictions)
        )

    candidate_passes = (
        [(2, False), (1, False), (0, False)]
        if requested_area
        else [(2, True), (1, True), (0, True), (1, False), (0, False)]
    )
    for minimum_matches, require_new_area in candidate_passes:
        for recipe in candidates:
            if len(dishes) == 3:
                return dishes
            try_add_recipe(recipe, minimum_matches, require_new_area)

    if requested_area:
        if len(dishes) != 3:
            fallback_candidates = fetch_random_spoonacular_recipes(
                dietary_restrictions,
                used_ids,
                cuisine=requested_area,
            )
            for minimum_matches in (1, 0):
                for recipe in fallback_candidates:
                    if len(dishes) == 3:
                        return dishes
                    try_add_recipe(recipe, minimum_matches, False)
        if len(dishes) != 3:
            raise RuntimeError(
                f"Recipe sources could not provide 3 {requested_area} recipe-backed dishes."
            )
        return dishes

    if is_generic_prompt:
        if recipe_ideas:
            diverse_candidates = spoonacular_diverse_cuisine_candidates(
                meal_prompt,
                candidates,
                used_ids,
            )
            for minimum_matches in (2, 1, 0):
                for recipe in diverse_candidates:
                    if len(dishes) == 3:
                        return dishes
                    try_add_recipe(recipe, minimum_matches, True)
        if len(dishes) != 3:
            fallback_candidates = fetch_random_spoonacular_recipes(
                dietary_restrictions,
                used_ids,
            )
            for minimum_matches, require_new_area in (
                (2, True),
                (1, True),
                (0, True),
                (1, False),
                (0, False),
            ):
                for recipe in fallback_candidates:
                    if len(dishes) == 3:
                        return dishes
                    try_add_recipe(recipe, minimum_matches, require_new_area)

    diverse_candidates = spoonacular_diverse_cuisine_candidates(
        meal_prompt,
        candidates + fallback_candidates,
        used_ids,
    )
    for minimum_matches in (2, 1, 0):
        for recipe in diverse_candidates:
            if len(dishes) == 3:
                return dishes
            try_add_recipe(recipe, minimum_matches, True)

    if not fallback_candidates:
        fallback_candidates = fetch_random_spoonacular_recipes(
            dietary_restrictions,
            used_ids,
        )

    for minimum_matches, require_new_area in (
        (2, True),
        (1, True),
        (0, True),
        (1, False),
        (0, False),
    ):
        for recipe in fallback_candidates:
            if len(dishes) == 3:
                return dishes
            try_add_recipe(recipe, minimum_matches, require_new_area)

    if len(dishes) != 3:
        raise RuntimeError("Recipe sources could not provide 3 recipe-backed dishes.")
    return dishes


def spoonacular_intolerances_from_restrictions(dietary_restrictions):
    restriction_text = dietary_restrictions or ""
    intolerances = []
    if re.search(r"\b(dairy|milk|lactose)\b", restriction_text, re.I):
        intolerances.append("dairy")
    if re.search(r"\b(gluten|wheat|celiac|coeliac)\b", restriction_text, re.I):
        intolerances.append("gluten")
    if re.search(r"\b(peanut|peanuts)\b", restriction_text, re.I):
        intolerances.append("peanut")
    if re.search(r"\b(tree nuts?|nuts?|almond|cashew|walnut|pecan)\b", restriction_text, re.I):
        intolerances.append("tree nut")
    if re.search(r"\b(shellfish|shrimp|crab|lobster)\b", restriction_text, re.I):
        intolerances.append("shellfish")
    if re.search(r"\b(egg|eggs)\b", restriction_text, re.I):
        intolerances.append("egg")
    if re.search(r"\b(soy|soya)\b", restriction_text, re.I):
        intolerances.append("soy")
    return ",".join(dict.fromkeys(intolerances))


def spoonacular_instructions(recipe):
    steps = []
    for instruction_group in recipe.get("analyzedInstructions") or []:
        for step in instruction_group.get("steps") or []:
            text = spoonacular_recipe_text(step.get("step"))
            if text:
                steps.append(text)
    if steps:
        return " ".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    return spoonacular_recipe_text(recipe.get("instructions") or recipe.get("summary"))


def spoonacular_recipe_from_recipe(recipe):
    return {
        "id": spoonacular_recipe_id(recipe),
        "name": recipe.get("title"),
        "category": (recipe.get("dishTypes") or [None])[0],
        "area": spoonacular_cuisine_label(recipe) or None,
        "instructions": spoonacular_instructions(recipe),
        "ingredients": spoonacular_ingredients(recipe),
        "thumbnail": recipe.get("image"),
        "youtube": recipe.get("_snapp_youtube"),
        "source": recipe.get("sourceUrl") or recipe.get("spoonacularSourceUrl"),
    }


def recipe_ready_minutes(recipe):
    for key in ("readyInMinutes", "cookingMinutes", "preparationMinutes"):
        try:
            minutes = int(recipe.get(key))
        except (TypeError, ValueError):
            continue
        if minutes > 0:
            return minutes
    return None


def recipe_servings(recipe, fallback_servings):
    try:
        servings = int(recipe.get("servings"))
    except (TypeError, ValueError):
        servings = fallback_servings
    return max(MIN_HOUSEHOLD_SIZE, min(servings, MAX_HOUSEHOLD_SIZE))


def recipe_dietary_tags(recipe):
    tags = []
    for key, label in (
        ("vegetarian", "vegetarian"),
        ("vegan", "vegan"),
        ("glutenFree", "gluten-free"),
        ("dairyFree", "dairy-free"),
        ("veryHealthy", "healthy"),
        ("cheap", "cheap"),
        ("sustainable", "sustainable"),
    ):
        if recipe.get(key):
            tags.append(label)
    existing = {tag.casefold() for tag in tags}
    for value in (recipe.get("diets") or []) + (recipe.get("dishTypes") or []):
        normalized = re.sub(r"\s+", " ", str(value or "").strip())
        if normalized and normalized.casefold() not in existing:
            tags.append(normalized)
            existing.add(normalized.casefold())
    return tags[:10]


def recipe_filter_text(recipe):
    return normalize_cuisine_text(
        " ".join(
            [
                recipe.get("title") or "",
                " ".join(recipe.get("dishTypes") or []),
                " ".join(spoonacular_cuisines(recipe)),
                " ".join(recipe_dietary_tags(recipe)),
                " ".join(ingredient["name"] for ingredient in spoonacular_ingredients(recipe)),
            ]
        )
    )


def recipe_matches_filter_terms(recipe, terms, require_all=True):
    if not terms:
        return True
    text = f" {recipe_filter_text(recipe)} "
    matches = [
        bool(re.search(rf"\b{re.escape(normalize_cuisine_text(term))}\b", text))
        for term in terms
    ]
    return all(matches) if require_all else any(matches)


def recipe_violates_avoid_terms(recipe, terms):
    return bool(terms and recipe_matches_filter_terms(recipe, terms, require_all=False))


def recipe_matches_dietary_preference(recipe, dietary_preference):
    preference = normalize_cuisine_text(dietary_preference)
    if not preference or preference in {"balanced", "none", "any"}:
        return True
    text = f" {recipe_filter_text(recipe)} "
    if preference == "vegetarian":
        return bool(recipe.get("vegetarian") or re.search(r"\bvegetarian\b", text))
    if preference == "vegan":
        return bool(recipe.get("vegan") or re.search(r"\bvegan\b", text))
    if preference in {"gluten free", "glutenfree"}:
        return bool(recipe.get("glutenFree") or re.search(r"\bgluten free\b", text))
    if preference in {"dairy free", "dairyfree"}:
        return bool(recipe.get("dairyFree") or re.search(r"\bdairy free\b", text))
    return preference in text


def recipe_passes_hard_filters(recipe, filters):
    if not spoonacular_respects_restrictions(recipe, filters["dietary_restrictions"]):
        return False
    if recipe_violates_avoid_terms(recipe, filters["avoid_ingredients"]):
        return False
    if not recipe_matches_filter_terms(recipe, filters["include_ingredients"], require_all=True):
        return False
    if not recipe_matches_dietary_preference(recipe, filters["dietary_preference"]):
        return False
    minutes = recipe_ready_minutes(recipe)
    if filters["max_cook_time"] and minutes and minutes > filters["max_cook_time"]:
        return False
    return True


def recipe_constraint_score(recipe, meal_prompt, filters):
    score = spoonacular_prompt_score(recipe, meal_prompt) * 10
    if recipe_matches_filter_terms(recipe, filters["include_ingredients"], require_all=True):
        score += 20 * len(filters["include_ingredients"])
    if recipe_matches_dietary_preference(recipe, filters["dietary_preference"]):
        score += 20
    minutes = recipe_ready_minutes(recipe)
    if filters["max_cook_time"] and minutes and minutes <= filters["max_cook_time"]:
        score += 10
    return score


def collect_recipe_candidates(meal_prompt, dietary_restrictions, recipe_ideas=None):
    del dietary_restrictions
    effective_ideas = recipe_ideas or [
        {"name": meal_prompt, "query": meal_prompt, "cuisine": ""}
    ]
    return mealdb_candidates_for_ideas(effective_ideas, meal_prompt)


def recipe_result_from_recipe(recipe, matched_products, stores, filters, relevance_score, exact_match):
    servings = filters["servings"]
    dish = spoonacular_recipe_to_demo_dish(recipe, matched_products, stores, servings)
    recipe_details = dish.get("recipe") or {}
    recipe_details["servings"] = recipe_servings(recipe, servings)
    recipe_details["cook_time_minutes"] = recipe_ready_minutes(recipe)
    recipe_details["dietary_tags"] = recipe_dietary_tags(recipe)
    recipe_details["source_link"] = recipe_details.get("source")
    dish["servings"] = recipe_details["servings"]
    dish["estimated_price_per_serving"] = round(
        dish["estimated_price_total"] / max(1, dish["servings"]), 2
    )
    dish["calories_per_person"] = (
        round(dish["calories_total"] / max(1, dish["servings"]))
        if dish.get("calories_total")
        else 0
    )
    dish["recipe"] = recipe_details
    dish["cook_time_minutes"] = recipe_details["cook_time_minutes"]
    dish["dietary_tags"] = recipe_details["dietary_tags"]
    dish["relevance_score"] = relevance_score
    dish["exact_match"] = exact_match
    dish["portion_note"] = (
        "Real recipe result matched against current Trader Joe's grocery prices."
        if exact_match
        else "Closest affordable real recipe match; at least one requested filter was relaxed."
    )
    return dish


def build_real_recipe_results(meal_prompt, filters, products, stores, result_limit=3, recipe_ideas=None):
    candidates = collect_recipe_candidates(
        meal_prompt,
        filters["dietary_restrictions"],
        recipe_ideas=recipe_ideas,
    )
    exact_results = []
    closest_results = []
    for recipe in candidates:
        if not spoonacular_ingredients(recipe):
            continue
        matches = match_recipe_ingredients_to_products(recipe, products)
        if not matches:
            continue
        relevance_score = recipe_constraint_score(recipe, meal_prompt, filters)
        exact_match = recipe_passes_hard_filters(recipe, filters)
        result = recipe_result_from_recipe(
            recipe,
            matches,
            stores,
            filters,
            relevance_score,
            exact_match,
        )
        if filters["max_budget"] is not None and result["estimated_price_total"] > filters["max_budget"]:
            closest_results.append(result)
            continue
        if exact_match:
            exact_results.append(result)
        else:
            closest_results.append(result)

    exact_results.sort(
        key=lambda result: (
            -result["relevance_score"],
            result["estimated_price_total"],
            result["name"].casefold(),
        )
    )
    if len(exact_results) >= result_limit:
        return exact_results[:result_limit], False

    target_budget = filters["max_budget"]
    closest_results.sort(
        key=lambda result: (
            0 if target_budget is None or result["estimated_price_total"] <= target_budget else 1,
            -result["relevance_score"],
            result["estimated_price_total"],
            result["name"].casefold(),
        )
    )
    seen = {result["recipe_id"] for result in exact_results}
    combined = list(exact_results)
    for result in closest_results:
        if result["recipe_id"] in seen:
            continue
        combined.append(result)
        seen.add(result["recipe_id"])
        if len(combined) >= result_limit:
            break
    if not combined:
        raise RuntimeError("Recipe sources could not provide real recipe matches.")
    return combined, not exact_results


def normalize_website(value):
    if not value:
        return None

    website = value.strip().split(";", 1)[0]
    if website.casefold().startswith(("javascript:", "data:", "vbscript:")):
        return None
    if "://" not in website:
        website = f"https://{website}"
    parsed = urlparse(website)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return website


def format_store(element):
    tags = element.get("tags", {})
    name = tags.get("name") or tags.get("brand")
    if not name:
        return None

    street = " ".join(
        value
        for value in (tags.get("addr:housenumber"), tags.get("addr:street"))
        if value
    )
    locality = tags.get("addr:city") or tags.get("addr:place")
    state = tags.get("addr:state")
    postal_code = tags.get("addr:postcode")
    city_line = ", ".join(value for value in (locality, state) if value)
    if postal_code:
        city_line = f"{city_line} {postal_code}".strip()
    address = ", ".join(value for value in (street, city_line) if value)

    center = element.get("center", {})
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    return {
        "name": name,
        "address": address or "Address not available",
        "latitude": latitude,
        "longitude": longitude,
        "website": normalize_website(
            tags.get("website")
            or tags.get("contact:website")
            or tags.get("brand:website")
        ),
    }


def format_nominatim_store(place):
    name = place.get("name")
    if not name:
        display_name = place.get("display_name", "")
        name = display_name.split(",", 1)[0].strip()
    if not name:
        return None

    return {
        "name": name,
        "address": place.get("display_name") or "Address not available",
        "latitude": place.get("lat"),
        "longitude": place.get("lon"),
        "website": None,
    }


def find_stores_with_nominatim(zip_code, boundingbox):
    south, north, west, east = boundingbox
    stores = []
    seen = set()

    for query in ("supermarket", "grocery"):
        params = urlencode(
            {
                "q": query,
                "countrycodes": "us",
                "format": "jsonv2",
                "limit": 20,
                "viewbox": f"{west},{north},{east},{south}",
                "bounded": 1,
            }
        )
        places = fetch_json(
            f"{NOMINATIM_URL}?{params}",
            service_name="Nominatim store fallback",
        )
        for place in places:
            if place.get("category") != "shop":
                continue
            if place.get("type") not in ("supermarket", "grocery"):
                continue
            store = format_nominatim_store(place)
            if not store:
                continue
            identity = (store["name"].casefold(), store["address"].casefold())
            if identity in seen:
                continue
            seen.add(identity)
            stores.append(store)

    stores.sort(key=lambda store: store["name"].casefold())
    return stores[:30]


def normalized_location_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def state_code_from_location(location):
    address = location.get("address") or {}
    state_code = address.get("state_code")
    if state_code:
        return state_code.casefold()
    state_name = normalized_location_text(address.get("state"))
    if state_name in US_STATE_CODES:
        return US_STATE_CODES[state_name]
    display_name = location.get("display_name", "")
    match = re.search(r"\b([A-Z]{2})\b(?:\s+\d{5})?", display_name)
    if match:
        return match.group(1).casefold()
    normalized_display = normalized_location_text(display_name)
    for name, code in US_STATE_CODES.items():
        if re.search(rf"\b{re.escape(name)}\b", normalized_display):
            return code
    return None


def parse_directory_links(url, html):
    parser = AnchorTextParser(url)
    parser.feed(html)
    return parser.links


def trader_joes_state_city_urls(state_code):
    state_url = f"{TRADER_JOES_LOCATIONS_BASE_URL}/{state_code}/"
    html = fetch_text(state_url, service_name="Trader Joe's state directory")
    if not html:
        return []
    urls = []
    seen = set()
    pattern = re.compile(
        rf"^https://locations\.traderjoes\.com/{re.escape(state_code)}/[^/]+/$"
    )
    for link in parse_directory_links(state_url, html):
        url = link["url"]
        if not pattern.match(url) or url in seen:
            continue
        urls.append(url)
        seen.add(url)
    return urls


def trader_joes_store_urls_for_city(city_url, state_code):
    html = fetch_text(city_url, service_name="Trader Joe's city directory")
    if not html:
        return []
    urls = []
    seen = set()
    pattern = re.compile(
        rf"^https://locations\.traderjoes\.com/{re.escape(state_code)}/[^/]+/\d+/$"
    )
    for link in parse_directory_links(city_url, html):
        url = link["url"]
        if not pattern.match(url) or url in seen:
            continue
        urls.append(url)
        seen.add(url)
    return urls


def parse_trader_joes_store_page(url):
    html = fetch_text(url, service_name="Trader Joe's store page")
    if not html:
        return None
    parser = TraderJoesStorePageParser()
    parser.feed(html)
    store_number_match = re.search(r"/(\d+)/?$", urlparse(url).path)
    title_match = re.search(r"^(.+?)\s*\((\d+)\)", parser.title)
    store_number = store_number_match.group(1) if store_number_match else None
    if not store_number and title_match:
        store_number = title_match.group(2)
    if not store_number:
        return None

    meta = parser.meta
    try:
        latitude = float(meta["place:location:latitude"])
        longitude = float(meta["place:location:longitude"])
    except (KeyError, TypeError, ValueError):
        return None

    city = meta.get("business:contact_data:locality")
    region = meta.get("business:contact_data:region")
    postal_code = meta.get("business:contact_data:postal_code")
    street = meta.get("business:contact_data:street_address")
    name = title_match.group(1).strip() if title_match else f"Trader Joe's Store {store_number}"
    return {
        "store_number": store_number,
        "name": f"Trader Joe's {name}",
        "address": ", ".join(
            value for value in (street, city, region, postal_code) if value
        ),
        "latitude": latitude,
        "longitude": longitude,
        "website": url,
    }


def find_trader_joes_store(zip_code):
    cached_result = trader_joes_store_cache.get(zip_code)
    now = time.time()
    if cached_result and now - cached_result["cached_at"] < TRADER_JOES_STORE_CACHE_TTL_SECONDS:
        return cached_result["result"]

    location = find_zip_location(zip_code)
    if not location:
        return None
    state_code = state_code_from_location(location)
    if not state_code:
        raise RuntimeError("Could not identify the state for that ZIP code.")
    try:
        center = {
            "latitude": float(location["lat"]),
            "longitude": float(location["lon"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("The location data service returned invalid coordinates.") from exc

    stores = []
    for city_url in trader_joes_state_city_urls(state_code):
        for store_url in trader_joes_store_urls_for_city(city_url, state_code):
            store = parse_trader_joes_store_page(store_url)
            if store:
                stores.append(
                    store_with_distance(
                        store,
                        center["latitude"],
                        center["longitude"],
                    )
                )

    stores.sort(
        key=lambda store: (
            store.get("distance_miles", float("inf")),
            store["name"].casefold(),
        )
    )
    result = {
        "zip_code": zip_code,
        "location": location.get("display_name", zip_code),
        "center": center,
        "store": stores[0] if stores else None,
        "source": "Trader Joe's official store directory",
    }
    trader_joes_store_cache[zip_code] = {"cached_at": now, "result": result}
    return result


def find_zip_location(zip_code):
    location_params = urlencode(
        {
            "postalcode": zip_code,
            "country": "USA",
            "countrycodes": "us",
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
        }
    )
    try:
        locations = fetch_json(
            f"{NOMINATIM_URL}?{location_params}",
            service_name="Nominatim",
        )
        if locations:
            return locations[0]
    except RuntimeError:
        print("Nominatim ZIP lookup unavailable; trying Zippopotam.", flush=True)

    zip_data = fetch_json(
        f"{ZIPPOPOTAM_URL}/{zip_code}",
        service_name="Zippopotam",
    )
    places = zip_data.get("places") or []
    if not places:
        return None

    place = places[0]
    try:
        latitude = float(place["latitude"])
        longitude = float(place["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("The ZIP code data service returned invalid location data.") from exc

    radius_degrees = 0.14
    place_name = place.get("place name") or zip_code
    state = place.get("state abbreviation") or place.get("state")
    return {
        "display_name": ", ".join(value for value in (place_name, state, zip_code) if value),
        "lat": latitude,
        "lon": longitude,
        "address": {"state_code": place.get("state abbreviation")},
        "boundingbox": [
            str(latitude - radius_degrees),
            str(latitude + radius_degrees),
            str(longitude - radius_degrees),
            str(longitude + radius_degrees),
        ],
    }


def find_stores_with_overpass(zip_code, boundingbox, require_postcode=True):
    south, north, west, east = boundingbox
    postcode_filter = (
        f'["addr:postcode"~"^{zip_code}(-[0-9]{{4}})?$"]'
        if require_postcode
        else ""
    )
    overpass_query = f"""
        [out:json][timeout:20];
        (
          nwr["shop"~"^(supermarket|grocery)$"]
             {postcode_filter}
             ({south},{west},{north},{east});
        );
        out center tags;
    """
    store_data = fetch_json(
        OVERPASS_URL,
        {"data": overpass_query},
        service_name="Overpass",
    )
    stores = []
    seen = set()
    for element in store_data.get("elements", []):
        store = format_store(element)
        if not store:
            continue
        element_postcode = element.get("tags", {}).get("addr:postcode")
        if element_postcode and element_postcode[:5] != zip_code:
            continue
        identity = (store["name"].casefold(), store["address"].casefold())
        if identity in seen:
            continue
        seen.add(identity)
        stores.append(store)
    return stores


def store_with_distance(store, latitude, longitude):
    try:
        store_latitude = float(store["latitude"])
        store_longitude = float(store["longitude"])
    except (KeyError, TypeError, ValueError):
        return store

    store = {**store}
    store["distance_miles"] = round(
        distance_miles(latitude, longitude, store_latitude, store_longitude), 2
    )
    return store


def find_grocery_stores(zip_code, radius_miles=None):
    cached_result = store_search_cache.get(zip_code)
    now = time.time()
    if cached_result and now - cached_result["cached_at"] < STORE_CACHE_TTL_SECONDS:
        location_name = cached_result["location"]
        stores = cached_result["stores"]
        center = cached_result.get("center")
    else:
        location = find_zip_location(zip_code)
        if not location:
            return None, [], None
        try:
            boundingbox = location["boundingbox"]
            center = {
                "latitude": float(location["lat"]),
                "longitude": float(location["lon"]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("The grocery store data service returned invalid location data.") from exc

        try:
            stores = find_stores_with_overpass(zip_code, boundingbox, require_postcode=True)
            if not stores:
                stores = find_stores_with_overpass(zip_code, boundingbox, require_postcode=False)
        except RuntimeError:
            print("Overpass unavailable; using Nominatim store fallback.", flush=True)
            stores = find_stores_with_nominatim(zip_code, boundingbox)

        stores = [
            store_with_distance(store, center["latitude"], center["longitude"])
            for store in stores
        ]
        stores.sort(
            key=lambda store: (
                store.get("distance_miles", float("inf")),
                store["name"].casefold(),
            )
        )
        location_name = location.get("display_name", zip_code)
        stores = stores[:30]
        store_search_cache[zip_code] = {
            "cached_at": now,
            "location": location_name,
            "center": center,
            "stores": stores,
        }

    if radius_miles is not None:
        stores = [
            store
            for store in stores
            if store.get("distance_miles") is not None
            and store["distance_miles"] <= radius_miles
        ]

    return location_name, stores, center


@app.get("/")
def index():
    return jsonify({"name": "SNAPP API", "status": "ok"})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400
    try:
        reply, total_tokens = generate_reply(message)
    except Exception as exc:
        return jsonify({"error": "Model request failed.", "details": str(exc)}), 500
    return jsonify({"reply": reply, "usage": {"total_tokens": total_tokens}})


@app.route("/chat", methods=["OPTIONS"])
def chat_options():
    return ("", 204)


@app.get("/grocery-stores")
def grocery_stores():
    zip_code = request.args.get("zip", "").strip()
    radius_miles = parse_store_radius_miles(request.args.get("radius_miles"))
    if not ZIP_CODE_PATTERN.fullmatch(zip_code):
        return jsonify({"error": "Enter a valid 5-digit US ZIP code."}), 400

    try:
        location, stores, center = find_grocery_stores(zip_code, radius_miles)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if location is None:
        return jsonify({"error": "ZIP code not found."}), 404

    return jsonify(
        {
            "zip_code": zip_code,
            "location": location,
            "center": center,
            "radius_miles": radius_miles,
            "stores": stores,
            "source": "OpenStreetMap contributors",
        }
    )


@app.route("/grocery-stores", methods=["OPTIONS"])
def grocery_stores_options():
    return ("", 204)


@app.get("/trader-joes-store")
def trader_joes_store():
    zip_code = request.args.get("zip", "").strip()
    if not ZIP_CODE_PATTERN.fullmatch(zip_code):
        return jsonify({"error": "Enter a valid 5-digit US ZIP code."}), 400

    try:
        result = find_trader_joes_store(zip_code)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if not result:
        return jsonify({"error": "ZIP code not found."}), 404
    if not result.get("store"):
        return jsonify({"error": "No Trader Joe's store found for that location."}), 404
    return jsonify(result)


@app.route("/trader-joes-store", methods=["OPTIONS"])
def trader_joes_store_options():
    return ("", 204)


@app.post("/dishes")
def dishes():
    data = request.get_json(silent=True) or {}
    meal_prompt = (data.get("meal_prompt") or data.get("ingredients") or data.get("message") or "").strip()
    household_size = parse_household_size(data.get("household_size"))
    store_number = re.sub(r"\D+", "", str(data.get("store_number") or ""))[:10] or None
    dietary_restrictions = re.sub(
        r"\s+", " ", (data.get("dietary_restrictions") or "").strip()
    )[:500]
    pantry_items = parse_pantry_items(data.get("pantry_items"))
    filters = parse_recipe_filters(data, household_size, dietary_restrictions)
    if not meal_prompt:
        return jsonify({"error": "Describe the meal you want."}), 400

    try:
        grocery_db = grocery_db_for_store(store_number)
        stores = demo_store_lookup(grocery_db)
        products = available_demo_products(grocery_db)
        recipe_ideas = generate_recipe_search_ideas(
            meal_prompt,
            filters["servings"],
            dietary_restrictions,
            pantry_items,
        )
        dishes, used_relaxed_matches = build_real_recipe_results(
            meal_prompt,
            filters,
            products,
            stores,
            recipe_ideas=recipe_ideas,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": "Dish generation failed.", "details": str(exc)}), 503

    return jsonify(
        {
            "meal_prompt": meal_prompt,
            "household_size": household_size,
            "dietary_restrictions": dietary_restrictions,
            "pantry_items": pantry_items,
            "filters": filters,
            "matched_ingredients": [
                ingredient
                for dish in dishes
                for ingredient in dish["ingredients"]
            ],
            "missing_ingredients": [],
            "dishes": dishes,
            "recipe_ideas": recipe_ideas,
            "used_relaxed_matches": used_relaxed_matches,
            "store_number": store_number,
            "source": "TheMealDB recipes selected from AI-generated meal ideas and current grocery pricing database",
        }
    )


@app.route("/dishes", methods=["OPTIONS"])
def dishes_options():
    return ("", 204)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
