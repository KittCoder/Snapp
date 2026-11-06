
import os
import json
import hashlib
import math
import random
import re
import sqlite3
import time
from difflib import get_close_matches
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request
from openai import OpenAI
from artifact_manifest import validate_runtime_artifacts
import matcher_warmup
from ops_metrics import log_event, metrics, request_id
from review_workflow import mutate_override, override_summary, require_admin

app = Flask(__name__)
from request_security import install_security, apply_route_limits
security_limiter = install_security(app)

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
MAX_JSON_PAYLOAD_BYTES = int(os.getenv("SNAPP_MAX_JSON_PAYLOAD_BYTES", "524288"))
MAX_DISH_PROMPT_CHARS = int(os.getenv("SNAPP_MAX_DISH_PROMPT_CHARS", "500"))
MAX_PANTRY_ITEMS_PER_REQUEST = int(os.getenv("SNAPP_MAX_PANTRY_ITEMS_PER_REQUEST", "200"))
MAX_REVIEW_REPORT_ITEMS = int(os.getenv("SNAPP_MAX_REVIEW_REPORT_ITEMS", "200"))
ZIP_CODE_PATTERN = re.compile(r"^\d{5}$")
MIN_HOUSEHOLD_SIZE = 1
MAX_HOUSEHOLD_SIZE = 12
MAX_STORE_RADIUS_MILES = 25
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ZIPPOPOTAM_URL = "https://api.zippopotam.us/us"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TRADER_JOES_LOCATIONS_BASE_URL = "https://locations.traderjoes.com"
DEFAULT_TRADER_JOES_STORE_NUMBER = os.getenv("DEFAULT_TRADER_JOES_STORE_NUMBER", "544")
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
THEMEALDB_SEARCH_LIMIT = 12
THEMEALDB_FILTER_LOOKUP_LIMIT = 6
WEB_RECIPE_SEARCH_RESULT_COUNT = 8
WEB_RECIPE_FETCH_LIMIT = 5
HTTP_TIMEOUT_SECONDS = 10
HTTP_RETRY_ATTEMPTS = 2
STORE_LOOKUP_TIMEOUT_SECONDS = float(os.getenv("STORE_LOOKUP_TIMEOUT_SECONDS", "4"))
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"
STORE_CACHE_TTL_SECONDS = 15 * 60
FOOD_CACHE_TTL_SECONDS = 60 * 60
TRADER_JOES_STORE_CACHE_TTL_SECONDS = 24 * 60 * 60
TRADER_JOES_PRODUCT_CACHE_TTL_SECONDS = 12 * 60 * 60
SCRAPED_GROCERY_DB_FILENAME = os.getenv(
    "SNAPP_GROCERY_DB_FILENAME",
    "database.scrape-20260721-143928.json",
)
REFERENCE_GROCERY_DB_FILENAME = "snapp_reference_grocery_db.json"
ALL_RECIPES_DB_FILENAME = "all_recipes.json"
ALL_RECIPES_SEARCH_INDEX_FILENAME = "all_recipes_search_index.json"
ALL_RECIPES_SEARCH_DB_FILENAME = "all_recipes_search.sqlite"
SALE_INGREDIENT_CANDIDATES_FILENAME = os.getenv(
    "SNAPP_SALE_INGREDIENT_CANDIDATES_FILENAME",
    "sale_ingredient_candidates.json",
)
SALE_CANDIDATE_POOL_SIZE = 10
SALE_HOME_SAMPLE_SIZE = 3
MIN_SALE_RECIPE_COUNT = 3
REAL_RECIPE_MATCH_MULTIPLIER = int(os.getenv("SNAPP_REAL_RECIPE_MATCH_MULTIPLIER", "1"))
SALE_RECIPE_MATCH_MULTIPLIER = int(os.getenv("SNAPP_SALE_RECIPE_MATCH_MULTIPLIER", "3"))
MAX_TRUSTED_DISCOUNT_PERCENT = 0.85
SALE_DESIRABILITY_WEIGHTS = {
    "discount_percent": 46,
    "absolute_savings": 14,
    "ingredient_usefulness": 20,
    "recipe_availability": 12,
    "data_confidence": 8,
}
store_search_cache = {}
trader_joes_store_cache = {}
trader_joes_product_cache = {}
food_search_cache = {}
spoonacular_search_cache = {}
spoonacular_lookup_cache = {}
mealdb_search_cache = {}
mealdb_lookup_cache = {}
all_recipes_cache = None
all_recipes_search_cache = None
all_recipes_by_id_cache = None
all_recipes_sqlite_connection = None
all_recipes_sqlite_vocab_cache = None
sale_ingredient_pool_cache = None
sale_candidate_artifact_cache = None
sale_recipe_index_cache = None
ingredient_generalization_cache = {}
robots_cache = {}
FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_API_KEY = os.getenv("FDC_API_KEY") or os.getenv("FOODDATA_CENTRAL_API_KEY") or "DEMO_KEY"
SNAP_ACCEPTING_CHAIN_PATTERNS = (
    r"\baldi\b",
    r"\bbravo\b",
    r"\bcostco\b",
    r"\bcvs\b",
    r"\bdollar general\b",
    r"\bfairway\b",
    r"\bfood bazaar\b",
    r"\bfoodtown\b",
    r"\bkey food\b",
    r"\bkroger\b",
    r"\bmarket basket\b",
    r"\bmorton williams\b",
    r"\bshoprite\b",
    r"\bstop\s*&\s*shop\b",
    r"\btarget\b",
    r"\btrader joe'?s\b",
    r"\bwalmart\b",
    r"\bwegmans\b",
    r"\bwhole foods\b",
)
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
OFFAL_RECIPE_PATTERN = re.compile(
    r"\b("
    r"brains?|kidneys?|livers?|feet|foot|tongues?|tripe|hearts?|gizzards?|"
    r"sweetbreads?|oxtails?|ox\s+joints?|neck\s+bones?|marrow\s+bones?|giblets?"
    r")\b",
    re.I,
)
OFFAL_FALSE_POSITIVE_PATTERN = re.compile(
    r"\b(kidney beans?|heart(?:y|s?\s+of\s+(?:palm|romaine|lettuce|artichoke)))\b",
    re.I,
)
RECIPE_GENERIC_PROMPT_WORDS = RECIPE_SEARCH_STOPWORDS | {
    "breakfast",
    "brunch",
    "dinner",
    "food",
    "lunch",
    "snack",
    "supper",
}
ALL_RECIPE_SEARCH_STOPWORDS = RECIPE_SEARCH_STOPWORDS - {"breakfast", "brunch", "dinner", "lunch", "snack", "supper"}
ALL_RECIPE_QUERY_EXPANSIONS = {
    "breakfast": ("egg", "oatmeal", "pancake", "muffin", "smoothie", "toast"),
    "brunch": ("egg", "pancake", "muffin", "salad", "sandwich"),
    "lunch": ("salad", "sandwich", "soup", "wrap", "bowl"),
    "dinner": ("stew", "casserole", "pasta", "chicken", "beef", "rice"),
    "snack": ("dip", "popcorn", "smoothie", "muffin", "bar"),
    "supper": ("stew", "casserole", "pasta", "chicken", "rice"),
}
RECIPE_INGREDIENT_ALIASES = {
    "beef": {"beef", "brisket", "steak", "ground beef", "minced beef", "short ribs", "sirloin", "sirloin steak", "ribeye", "rib eye", "flank steak", "stewing beef"},
    "chicken": {"chicken", "chicken thighs", "chicken breast", "poultry"},
    "chicken breast": {"chicken", "chicken thighs", "poultry"},
    "fish": {"fish", "cod", "salmon", "tuna", "white fish"},
    "pork": {"pork", "bacon", "ham", "sausage"},
    "shrimp": {"shrimp", "prawn", "prawns"},
    "tomato": {"tomato", "tomatoes", "canned tomatoes", "diced tomatoes", "crushed tomatoes", "tomato sauce", "tomato paste"},
    "tomatoes": {"tomato", "canned tomatoes", "diced tomatoes", "crushed tomatoes", "tomato sauce", "tomato paste"},
    "pasta": {"pasta", "spaghetti", "penne", "linguine", "macaroni", "noodles", "noodle"},
    "spaghetti": {"pasta", "noodles"},
    "noodles": {"pasta", "noodle", "rice noodles", "flat rice noodles", "egg noodles"},
    "noodle": {"pasta", "noodles", "rice noodles", "flat rice noodles", "egg noodles"},
    "rice": {"rice", "rice noodles", "flat rice noodles", "jasmine rice", "basmati rice", "brown rice", "white rice"},
    "potato": {"potatoes"},
    "beans": {"black beans"},
    "bean": {"black beans"},
    "sweetcorn": {"frozen corn"},
    "corn": {"frozen corn"},
    "broccoli": {"broccoli", "frozen broccoli"},
    "tortilla": {"tortillas"},
    "flour tortillas": {"tortillas"},
    "cheddar": {"cheese"},
    "mozzarella": {"cheese"},
    "parmesan": {"cheese"},
    "chilli": {"chile", "chili", "pepper", "peppers", "jalapeno", "serrano", "thai chile", "birds eye chilli", "birds-eye chillies"},
    "chillies": {"chile", "chili", "pepper", "peppers", "jalapeno", "serrano", "thai chile", "birds eye chilli", "birds-eye chillies"},
    "chiles": {"chile", "chili", "pepper", "peppers", "jalapeno", "serrano", "thai chile"},
    "garlic": {"garlic", "garlic cloves", "minced garlic"},
    "basil": {"basil", "basil leaves", "fresh basil"},
    "soy sauce": {"soy sauce", "tamari"},
    "fish sauce": {"fish sauce"},
    "oyster sauce": {"oyster sauce"},
    "vegetable oil": {"oil", "vegetable oil", "canola oil", "olive oil"},
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
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "https://snapp-1d5j.vercel.app,"
    "https://snapp.vercel.app"
)
VERCEL_DEPLOYMENT_ORIGIN_PATTERN = re.compile(
    r"^https://snapp(?:-[a-z0-9-]+)?\.vercel\.app$"
)
LOCAL_DEVELOPMENT_ORIGIN_PATTERN = re.compile(
    r"^http://(?:localhost|127\.0\.0\.1):\d+$"
)
CORS_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
}
MATCHER_WARMUP_EXEMPT_ENDPOINTS = {
    "store_comparison.stores",
    "store_comparison.compare",
    "store_comparison.recipe_prices",
    "store_comparison.warm_store",
    "health",
    "static",
    "recipe_search",
    "recipe_search_options",
    "recipe_chat",
    "recipe_chat_options",
    "sale_ingredients",
    "sale_ingredients_options",
    "dishes",
    "dishes_options",
}


@app.before_request
def attach_request_context():
    request.snapp_request_id = getattr(request, "snapp_request_id", request_id())
    if (
        request.endpoint not in MATCHER_WARMUP_EXEMPT_ENDPOINTS
        and os.getenv("SNAPP_DISABLE_MATCHER_WARMUP", "").lower() not in {"1", "true", "yes"}
        and matcher_warmup.get_warmup_status().status == "not_started"
    ):
        matcher_warmup.start_background_warmup()


def json_error(message, status_code=400, **extra):
    return jsonify({"error": message, "request_id": getattr(request, "snapp_request_id", None), **extra}), status_code


def validated_json_payload(max_bytes: int = MAX_JSON_PAYLOAD_BYTES):
    if request.content_length and request.content_length > max_bytes:
        return None, json_error("Request payload is too large.", 413)
    data = request.get_json(silent=True)
    if data is None:
        return None, json_error("Request body must be valid JSON.", 400)
    if not isinstance(data, dict):
        return None, json_error("Request body must be a JSON object.", 400)
    return data, None


def admin_required():
    ok, message = require_admin(request.headers)
    if ok:
        return None
    return json_error(message, 401)


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin and origin in CORS_ORIGINS and origin != "*":
        response.headers["Access-Control-Allow-Origin"] = origin
        response.vary.add("Origin")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-SNAPP-Admin-Token,X-Request-ID"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    log_event("unhandled_backend_error", error_type=type(exc).__name__)
    return jsonify({"error": "Backend request failed.", "request_id": getattr(request, "snapp_request_id", None)}), 500


def generate_reply(message):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key, timeout=8, max_retries=0)
    history = []  # Legacy route must never share conversation data across users.
    prompt = [{"role": "system", "content": SYSTEM_PROMPT}]
    prompt.extend(history)
    prompt.append({"role": "user", "content": message})
    response = client.responses.create(
        model="gpt-4.1-nano",
        input=prompt,
        store=False,
    )
    reply = response.output_text
    return reply, response.usage.total_tokens


def fetch_json(url, data=None, json_data=None, service_name="data service", timeout_seconds=None, retry_attempts=None):
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

    timeout_seconds = timeout_seconds if timeout_seconds is not None else HTTP_TIMEOUT_SECONDS
    retry_attempts = retry_attempts if retry_attempts is not None else HTTP_RETRY_ATTEMPTS
    last_error = None
    for attempt in range(retry_attempts):
        request_object = Request(url, data=data, headers=headers)
        try:
            with urlopen(request_object, timeout=timeout_seconds) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            print(
                f"{service_name} request failed on attempt {attempt + 1}: {exc}",
                flush=True,
            )
            if attempt + 1 < retry_attempts:
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


def load_grocery_db():
    search_paths = (
        Path(__file__).with_name(SCRAPED_GROCERY_DB_FILENAME),
        Path(__file__).resolve().parent.parent / SCRAPED_GROCERY_DB_FILENAME,
        Path(__file__).with_name(REFERENCE_GROCERY_DB_FILENAME),
        Path(__file__).resolve().parent.parent / REFERENCE_GROCERY_DB_FILENAME,
    )
    for path in search_paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as file:
            grocery_db = json.load(file)
        if path.name == SCRAPED_GROCERY_DB_FILENAME and not grocery_db.get("products"):
            continue
        return grocery_db
    raise RuntimeError("The SNAPP reference grocery database is missing.")


def load_snapp_reference_grocery_db():
    search_paths = (
        Path(__file__).with_name(REFERENCE_GROCERY_DB_FILENAME),
        Path(__file__).resolve().parent.parent / REFERENCE_GROCERY_DB_FILENAME,
    )
    for path in search_paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as file:
            grocery_db = json.load(file)
        grocery_db["pricing_source"] = "reference"
        return grocery_db
    raise RuntimeError("The SNAPP reference grocery database is missing.")


def parse_sale_price_amount(value):
    from basket_quantity import parse_price_info

    price = parse_price_info(value)
    if price.checkout_price is not None:
        return round(float(price.checkout_price), 2)
    if price.unit_price is not None and not price.price_unit:
        return round(float(price.unit_price), 2)
    return None


def trusted_discount(original_price, sale_price):
    original = parse_sale_price_amount(original_price)
    sale = parse_sale_price_amount(sale_price)
    if original is None or sale is None:
        return None
    if original <= 0 or sale <= 0 or sale >= original:
        return None
    discount_percent = (original - sale) / original
    if discount_percent <= 0 or discount_percent > MAX_TRUSTED_DISCOUNT_PERCENT:
        return None
    return {
        "original_price": round(original, 2),
        "sale_price": round(sale, 2),
        "discount_percent": round(discount_percent, 4),
        "absolute_savings": round(original - sale, 2),
    }


NON_INGREDIENT_SALE_PATTERNS = re.compile(
    r"\b("
    r"ale|beer|beverage|candy|chips|chocolate|cookie|cookies|cracker|crackers|"
    r"cake|coffee|dessert|detergent|dressing|drink|fries|ginger ale|ice cream|"
    r"juice|lager|laundry|marshmallow|paper|pickle|pickles|platter|pretzel|"
    r"soda|snack|soap|tissue|water"
    r")\b",
    re.I,
)
USEFUL_INGREDIENT_PATTERNS = re.compile(
    r"\b("
    r"avocado|bean|beef|broccoli|butter|carrot|cheese|chicken|cream|egg|fish|"
    r"flour|fruit|garlic|lettuce|mushroom|oil|onion|pasta|pepper|pork|potato|"
    r"rice|salmon|shrimp|spinach|tomato|turkey|yogurt"
    r")s?\b",
    re.I,
)
CATEGORY_USEFULNESS = {
    "meat": 1.0,
    "produce": 0.95,
    "dairy": 0.88,
    "pantry": 0.82,
}


def sale_ingredient_id_for_feature(feature):
    from ingredient_normalization import canonical_for_product, normalize_text

    normalized_name = feature.get("normalized_name") or ""
    if re.search(r"\bolive oil\b", normalized_name):
        return "olive oil"
    if re.search(r"\bcottage cheese\b", normalized_name):
        return "cottage cheese"
    if re.search(r"\bmozzarella\b", normalized_name):
        return "mozzarella cheese"
    if re.search(r"\bcheese\b", normalized_name):
        return "cheese"
    if re.search(r"\balmond milk\b", normalized_name):
        return "almond milk"
    if re.search(r"\boat milk\b", normalized_name):
        return "oat milk"
    if re.search(r"\byogurt\b", normalized_name):
        return "yogurt"
    if re.search(r"\b(?:french fries|steak fries|fries)\b", normalized_name):
        return "potatoes"
    canonical = feature.get("canonical_name") or canonical_for_product(normalized_name)
    if not canonical:
        return ""
    return normalize_text(canonical)


def ingredient_usefulness_score(feature):
    text = " ".join(
        str(feature.get(key) or "")
        for key in ("normalized_name", "canonical_name", "category", "subcategory")
    )
    if NON_INGREDIENT_SALE_PATTERNS.search(text):
        return 0.0
    category = feature.get("category")
    score = CATEGORY_USEFULNESS.get(category, 0.45 if category else 0.35)
    if USEFUL_INGREDIENT_PATTERNS.search(text):
        score = max(score, 0.82)
    if feature.get("record_status") == "probably_valid_grocery_product":
        score -= 0.18
    return max(0.0, min(score, 1.0))


def sale_data_confidence_score(feature, product, discount):
    score = 0.0
    if feature.get("record_status") == "valid_grocery_product":
        score += 0.28
    elif feature.get("record_status") == "probably_valid_grocery_product":
        score += 0.14
    if feature.get("canonical_name"):
        score += 0.22
    if feature.get("source_quality_score"):
        score += min(0.2, float(feature.get("source_quality_score") or 0) / 500)
    if product.get("is_on_sale") is True:
        score += 0.12
    if discount:
        score += 0.18
    if feature.get("uncertainty_reasons"):
        score -= min(0.24, len(feature.get("uncertainty_reasons") or []) * 0.06)
    return max(0.0, min(score, 1.0))


def sale_recipe_index():
    global sale_recipe_index_cache
    if sale_recipe_index_cache is not None:
        return sale_recipe_index_cache
    index = {}
    for database_recipe in load_all_recipes_db():
        if recipe_contains_offal(database_recipe):
            continue
        recipe = all_recipe_to_spoonacular_recipe(database_recipe)
        recipe_id = spoonacular_recipe_id(recipe)
        if not recipe_id:
            continue
        keys = set()
        for ingredient in spoonacular_ingredients(recipe):
            for value in (
                ingredient.get("display"),
                ingredient.get("measure"),
                ingredient.get("name"),
            ):
                key = ingredient_identity_key(value or "")
                if key:
                    keys.add(key)
        for key in keys:
            index.setdefault(key, []).append(recipe_id)
    sale_recipe_index_cache = index
    return sale_recipe_index_cache


def sale_candidate_artifact_path():
    return Path(__file__).with_name(SALE_INGREDIENT_CANDIDATES_FILENAME)


def load_sale_candidate_artifact(path=None):
    global sale_candidate_artifact_cache
    if path is None and sale_candidate_artifact_cache is not None:
        return sale_candidate_artifact_cache
    path = Path(path) if path else sale_candidate_artifact_path()
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load {path.name}: {exc}", flush=True)
        return None
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list):
        return None
    if path == sale_candidate_artifact_path():
        sale_candidate_artifact_cache = payload
    return payload


def public_sale_candidate(candidate):
    return {
        key: value
        for key, value in candidate.items()
        if key not in {"recipe_ids"}
    }


def artifact_recipe_ids_for_sale_ingredient(ingredient_id):
    artifact = load_sale_candidate_artifact()
    if not artifact:
        return []
    for candidate in artifact.get("candidates") or []:
        if candidate.get("ingredient_id") == ingredient_id:
            return list(candidate.get("recipe_ids") or [])
    return []


def write_sale_candidate_artifact(path=None, *, source_path=None):
    path = Path(path) if path else sale_candidate_artifact_path()
    source_path = Path(source_path) if source_path else Path(__file__).with_name(SCRAPED_GROCERY_DB_FILENAME)
    with source_path.open(encoding="utf-8") as file:
        grocery_db = json.load(file)
    audit = build_sale_ingredient_pool(grocery_db, include_diagnostics=True)
    payload = {
        "metadata": {
            "source": "SNAPP sale ingredient candidate artifact",
            "source_database": source_path.name,
            "source_last_updated": grocery_db.get("last_updated") if isinstance(grocery_db, dict) else None,
            "candidate_count": len(audit["candidates"]),
            "exclusion_sample_count": len(audit["exclusions"]),
            "weights": SALE_DESIRABILITY_WEIGHTS,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "candidates": audit["candidates"],
        "exclusions": audit["exclusions"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")
    os.replace(temp_path, path)
    return payload


def recipe_ids_for_sale_ingredient(ingredient_id, *, use_artifact=True):
    if use_artifact:
        artifact_recipe_ids = artifact_recipe_ids_for_sale_ingredient(ingredient_id)
        if artifact_recipe_ids:
            return artifact_recipe_ids
    index = sale_recipe_index()
    recipe_ids = list(index.get(ingredient_id, []))
    if recipe_ids:
        return recipe_ids
    tokens = set(ingredient_id.split())
    if not tokens:
        return []
    if len(tokens) > 1:
        return []
    matched = []
    for key, ids in index.items():
        key_tokens = set(key.split())
        if tokens <= key_tokens or key_tokens <= tokens:
            matched.extend(ids)
    return list(dict.fromkeys(matched))


def recipe_uses_sale_ingredient(recipe, ingredient_id):
    if not ingredient_id:
        return False
    target_tokens = set(ingredient_id.split())
    for ingredient in spoonacular_ingredients(recipe):
        keys = {
            ingredient_identity_key(value or "")
            for value in (
                ingredient.get("display"),
                ingredient.get("measure"),
                ingredient.get("name"),
            )
        }
        keys.discard("")
        if ingredient_id in keys:
            return True
        if len(target_tokens) > 1:
            continue
        for key in keys:
            key_tokens = set(key.split())
            if target_tokens and (target_tokens <= key_tokens or key_tokens <= target_tokens):
                return True
    return False


def sale_candidate_score_components(feature, product, recipe_count, discount):
    usefulness = ingredient_usefulness_score(feature)
    confidence = sale_data_confidence_score(feature, product, discount)
    discount_component = discount["discount_percent"] if discount else 0.08 if product.get("is_on_sale") is True else 0.0
    savings_component = min(1.0, math.log1p(discount["absolute_savings"]) / math.log1p(12)) if discount else 0.0
    recipe_component = min(1.0, recipe_count / 12)
    score = (
        SALE_DESIRABILITY_WEIGHTS["discount_percent"] * discount_component
        + SALE_DESIRABILITY_WEIGHTS["absolute_savings"] * savings_component
        + SALE_DESIRABILITY_WEIGHTS["ingredient_usefulness"] * usefulness
        + SALE_DESIRABILITY_WEIGHTS["recipe_availability"] * recipe_component
        + SALE_DESIRABILITY_WEIGHTS["data_confidence"] * confidence
    )
    return {
        "discount_component": round(discount_component, 4),
        "savings_component": round(savings_component, 4),
        "ingredient_usefulness": round(usefulness, 4),
        "recipe_availability": round(recipe_component, 4),
        "data_confidence": round(confidence, 4),
        "final_score": round(score, 4),
    }


def build_sale_ingredient_pool(grocery_db=None, *, include_diagnostics=False):
    from ingredient_normalization import extract_product_features

    grocery_db = grocery_db or load_grocery_db()
    products = grocery_db.get("products") if isinstance(grocery_db, dict) else []
    by_ingredient = {}
    exclusions = []
    seen_fingerprints = set()
    for index, product in enumerate(products or []):
        if not isinstance(product, dict):
            continue
        if product.get("is_on_sale") is not True and not product.get("sale_price"):
            continue
        feature = extract_product_features(product, index, seen_fingerprints)
        product_name = feature.get("original_product_name") or product.get("name") or ""
        ingredient_id = sale_ingredient_id_for_feature(feature)
        discount = trusted_discount(product.get("original_price"), product.get("sale_price") or product.get("price"))
        recipe_ids = recipe_ids_for_sale_ingredient(ingredient_id, use_artifact=False) if ingredient_id else []
        recipe_count = len(recipe_ids)
        reasons = []
        if not feature.get("eligible_for_retrieval"):
            reasons.append("product is not eligible for ingredient retrieval")
        if not ingredient_id:
            reasons.append("normalized ingredient type unavailable")
        usefulness = ingredient_usefulness_score(feature)
        if usefulness <= 0:
            reasons.append("not a useful recipe ingredient")
        if recipe_count < MIN_SALE_RECIPE_COUNT:
            reasons.append("fewer than three matching recipes")
        if not discount and not product.get("is_on_sale"):
            reasons.append("sale status is not verifiable")
        if reasons:
            if include_diagnostics:
                exclusions.append(
                    {
                        "product_name": product_name,
                        "ingredient_id": ingredient_id,
                        "reasons": reasons,
                        "raw_price": product.get("price"),
                        "raw_original_price": product.get("original_price"),
                    }
                )
            continue
        components = sale_candidate_score_components(feature, product, recipe_count, discount)
        sale_price = parse_sale_price_amount(product.get("sale_price") or product.get("price"))
        candidate = {
            "ingredient_id": ingredient_id,
            "ingredient_name": ingredient_id,
            "product_name": product_name,
            "category": feature.get("category") or "grocery",
            "original_price": discount["original_price"] if discount else None,
            "sale_price": discount["sale_price"] if discount else sale_price,
            "price_display": str(product.get("sale_price") or product.get("price") or "").strip(),
            "unit": str(product.get("unit") or "").strip(),
            "discount_percent": discount["discount_percent"] if discount else None,
            "absolute_savings": discount["absolute_savings"] if discount else None,
            "recipe_count": recipe_count,
            "score": components["final_score"],
            "score_components": components,
            "recipe_ids": recipe_ids,
            "source": product.get("source"),
        }
        existing = by_ingredient.get(ingredient_id)
        if not existing or candidate["score"] > existing["score"]:
            by_ingredient[ingredient_id] = candidate
    candidates = sorted(
        by_ingredient.values(),
        key=lambda item: (-item["score"], item["ingredient_name"].casefold(), item["product_name"].casefold()),
    )
    pool = candidates[:SALE_CANDIDATE_POOL_SIZE]
    if include_diagnostics:
        return {"candidates": pool, "exclusions": exclusions[:200], "weights": SALE_DESIRABILITY_WEIGHTS}
    return pool


def sale_ingredient_pool():
    global sale_ingredient_pool_cache
    if sale_ingredient_pool_cache is None:
        artifact = load_sale_candidate_artifact()
        if artifact:
            sale_ingredient_pool_cache = artifact.get("candidates") or []
        else:
            sale_ingredient_pool_cache = build_sale_ingredient_pool()
    return sale_ingredient_pool_cache


def weighted_sale_sample(candidates, sample_size=SALE_HOME_SAMPLE_SIZE, rng=None):
    rng = rng or random
    pool = list(candidates[:SALE_CANDIDATE_POOL_SIZE])
    selected = []
    seen = set()
    while pool and len(selected) < sample_size:
        weights = [max(0.01, len(pool) - index) * max(1.0, item.get("score", 0)) for index, item in enumerate(pool)]
        choice = rng.choices(pool, weights=weights, k=1)[0]
        pool.remove(choice)
        if choice["ingredient_id"] in seen:
            continue
        selected.append(choice)
        seen.add(choice["ingredient_id"])
    return selected


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
    if store_number:
        trader_joes_db = load_trader_joes_grocery_db(store_number)
        if trader_joes_db:
            trader_joes_db["pricing_source"] = "trader_joes"
            return trader_joes_db
        return {
            "stores": [
                {
                    "id": f"trader-joes-{store_number}",
                    "name": f"Trader Joe's #{store_number}",
                }
            ],
            "products": [],
            "pricing_source": "trader_joes",
            "pricing_unavailable": True,
        }
    grocery_db = load_grocery_db()
    grocery_db["pricing_source"] = "reference"
    return grocery_db


def product_effective_price(product):
    price = product.get("sale_price")
    if price is None:
        price = product.get("price")
    try:
        return round(float(price), 2)
    except (TypeError, ValueError):
        return 0


def available_grocery_products(grocery_db):
    return [
        product
        for product in grocery_db.get("products", [])
        if product.get("in_stock") and product.get("snap_eligible")
    ]


def grocery_store_lookup(grocery_db):
    return {
        store["id"]: store
        for store in grocery_db.get("stores", [])
        if store.get("id")
    }


def grocery_catalog_for_prompt(products, stores):
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


def generate_grocery_dish_candidates(
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
        return fallback_recipe_search_ideas(meal_prompt)

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
    try:
        response = client.responses.create(
            model=OPENAI_DISH_MODEL,
            input=[
                {"role": "system", "content": DISH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            store=False,
        )
        data = extract_json_object(response.output_text)
    except Exception as exc:
        print(f"Recipe idea generation failed: {exc}", flush=True)
        return fallback_recipe_search_ideas(meal_prompt)
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
        return fallback_recipe_search_ideas(meal_prompt)
    return ideas[:RECIPE_IDEA_COUNT]


def fallback_recipe_search_ideas(meal_prompt):
    prompt = re.sub(r"\s+", " ", meal_prompt or "").strip()
    requested_area = detect_requested_spoonacular_cuisine(prompt)
    requested_ingredients = [
        ingredient
        for ingredient, _aliases in requested_spoonacular_ingredient_groups(prompt)
    ]
    category_names = mealdb_categories_for_text(prompt)
    base_terms = [prompt, *requested_ingredients, *category_names]
    generic_terms = [
        "Chicken",
        "Pasta",
        "Vegetarian",
        "Seafood",
        "Beef",
        "Rice",
    ]
    ideas = []
    seen = set()
    for term in [*base_terms, *generic_terms]:
        term = re.sub(r"\s+", " ", term or "").strip()
        if not term:
            continue
        identity = term.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        ideas.append(
            {
                "name": term,
                "query": term,
                "cuisine": requested_area or "",
            }
        )
        if len(ideas) >= RECIPE_IDEA_COUNT:
            break
    return ideas


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


def build_grocery_dishes(dish_candidates, products_by_id, stores):
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
    from recipe_ingredient_adapter import canonical_recipe_ingredients

    ingredients = []
    seen = set()
    for canonical in canonical_recipe_ingredients(recipe):
        name = re.sub(r"\s+", " ", canonical.ingredient_name or "").strip()
        if not name:
            continue
        measure = canonical.matcher_text
        display = canonical.raw_text or measure or name
        identity = f"{name}|{measure}".casefold()
        if identity in seen:
            continue
        seen.add(identity)
        ingredients.append(
            {
                "name": name,
                "measure": measure,
                "display": display,
                "canonical_ingredient": canonical.to_dict(),
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


def load_all_recipes_db():
    global all_recipes_cache
    if all_recipes_cache is not None:
        return all_recipes_cache
    path = Path(__file__).with_name(ALL_RECIPES_DB_FILENAME)
    if not path.exists():
        all_recipes_cache = []
        return all_recipes_cache
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load {ALL_RECIPES_DB_FILENAME}: {exc}", flush=True)
        all_recipes_cache = []
        return all_recipes_cache
    recipes = data.get("recipes") if isinstance(data, dict) else []
    all_recipes_cache = [
        recipe for recipe in recipes
        if isinstance(recipe, dict) and recipe.get("name") and recipe.get("ingredients")
    ]
    return all_recipes_cache


def load_all_recipes_by_id():
    global all_recipes_by_id_cache
    if all_recipes_by_id_cache is not None:
        return all_recipes_by_id_cache
    all_recipes_by_id_cache = {
        str(recipe.get("id")): recipe
        for recipe in load_all_recipes_db()
        if recipe.get("id")
    }
    return all_recipes_by_id_cache


def all_recipe_ingredient_display(ingredient):
    raw = re.sub(r"\s+", " ", str(ingredient.get("raw") or "")).strip()
    if raw:
        return raw
    quantity = re.sub(r"\s+", " ", str(ingredient.get("quantity") or "")).strip()
    unit = re.sub(r"\s+", " ", str(ingredient.get("unit") or "")).strip()
    name = re.sub(r"\s+", " ", str(ingredient.get("name") or "")).strip()
    note = re.sub(r"\s+", " ", str(ingredient.get("note") or "")).strip()
    display = " ".join(part for part in (quantity, unit, name) if part).strip()
    if note:
        display = f"{display} ({note})" if display else note
    return display or name


def all_recipe_ingredient_name(ingredient):
    name = normalize_ingredient_name(ingredient.get("name"))
    raw = normalize_ingredient_name(ingredient.get("raw"))
    if not name:
        return raw
    generic_names = {
        "boneless",
        "skinless",
        "low sodium",
        "reduced sodium",
        "fresh",
        "frozen",
        "canned",
    }
    if name.casefold() in generic_names and raw:
        return raw
    return name


def recipe_offal_filter_text(recipe):
    database_recipe = recipe.get("_snapp_database_recipe") or recipe
    ingredient_texts = []
    for ingredient in database_recipe.get("ingredients") or []:
        if isinstance(ingredient, dict):
            ingredient_texts.extend(
                str(ingredient.get(key) or "")
                for key in ("raw", "name", "note")
            )
        else:
            ingredient_texts.append(str(ingredient or ""))
    return " ".join(
        [
            str(recipe.get("title") or recipe.get("name") or database_recipe.get("name") or ""),
            str(database_recipe.get("description") or ""),
            " ".join(str(category or "") for category in database_recipe.get("category") or []),
            " ".join(ingredient_texts),
        ]
    )


def recipe_contains_offal(recipe):
    text = recipe_offal_filter_text(recipe)
    if not OFFAL_RECIPE_PATTERN.search(text):
        return False
    cleaned = OFFAL_FALSE_POSITIVE_PATTERN.sub(" ", text)
    return bool(OFFAL_RECIPE_PATTERN.search(cleaned))


def all_recipe_to_spoonacular_recipe(recipe):
    source_url = recipe.get("source_url") or recipe.get("original_usda_url")
    recipe_id = str(recipe.get("id") or source_url or recipe.get("name") or "").strip()
    categories = [
        re.sub(r"\s+", " ", str(category or "")).strip()
        for category in (recipe.get("category") or [])
        if re.sub(r"\s+", " ", str(category or "")).strip()
    ]
    food_groups = [
        re.sub(r"\s+", " ", str(group.get("label") or "")).strip()
        for group in (recipe.get("food_groups") or [])
        if isinstance(group, dict) and group.get("label")
    ]
    extended_ingredients = []
    seen = set()
    for ingredient in recipe.get("ingredients") or []:
        if not isinstance(ingredient, dict):
            continue
        name = all_recipe_ingredient_name(ingredient)
        display = all_recipe_ingredient_display(ingredient)
        if not name and not display:
            continue
        identity = (name or display).casefold()
        if identity in seen:
            continue
        seen.add(identity)
        extended_ingredients.append(
            {
                "name": name or display,
                "nameClean": name or display,
                "original": display or name,
                "originalName": display or name,
            }
        )

    instructions = recipe.get("instructions") or []
    if isinstance(instructions, list):
        instruction_text = " ".join(
            f"{index}. {spoonacular_recipe_text(step)}"
            for index, step in enumerate(instructions, start=1)
            if spoonacular_recipe_text(step)
        )
    else:
        instruction_text = spoonacular_recipe_text(instructions)

    provider = recipe.get("source") or "SNAPP recipe database"
    return {
        "id": recipe_id,
        "title": recipe.get("name"),
        "cuisines": [],
        "dishTypes": categories or food_groups or ["main course"],
        "extendedIngredients": extended_ingredients,
        "instructions": instruction_text,
        "image": recipe.get("image"),
        "sourceUrl": source_url,
        "spoonacularSourceUrl": source_url,
        "servings": recipe.get("servings"),
        "_snapp_recipe_provider": provider,
        "_snapp_database_recipe": recipe,
        "_snapp_original_usda_url": recipe.get("original_usda_url"),
    }


def all_recipe_query_terms(recipe):
    database_recipe = recipe.get("_snapp_database_recipe") or {}
    return normalize_cuisine_text(
        " ".join(
            [
                recipe.get("title") or "",
                database_recipe.get("description") or "",
                " ".join(database_recipe.get("category") or []),
                " ".join(
                    group.get("label", "")
                    for group in database_recipe.get("food_groups") or []
                    if isinstance(group, dict)
                ),
                " ".join(
                    ingredient.get("raw") or ingredient.get("name") or ""
                    for ingredient in database_recipe.get("ingredients") or []
                    if isinstance(ingredient, dict)
                ),
            ]
        )
    )


def all_recipes_search_index():
    global all_recipes_search_cache
    if all_recipes_search_cache is not None:
        return all_recipes_search_cache
    path = Path(__file__).with_name(ALL_RECIPES_SEARCH_INDEX_FILENAME)
    if path.exists():
        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data.get("recipes"), dict) and isinstance(data.get("postings"), dict):
                all_recipes_search_cache = data
                return all_recipes_search_cache
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Failed to load {ALL_RECIPES_SEARCH_INDEX_FILENAME}: {exc}", flush=True)

    recipes = {}
    postings = {}
    for database_recipe in load_all_recipes_db():
        recipe = all_recipe_to_spoonacular_recipe(database_recipe)
        recipe_id = spoonacular_recipe_id(recipe)
        if not recipe_id or not spoonacular_ingredients(recipe):
            continue
        search_text = all_recipe_query_terms(recipe)
        recipes[recipe_id] = {
            "id": recipe_id,
            "name": recipe.get("title"),
            "title_text": normalize_cuisine_text(recipe.get("title")),
            "search_text": search_text,
            "meal_text": spoonacular_normalized_search_text(recipe),
        }
        for token in all_recipe_search_tokens(search_text):
            postings.setdefault(token, []).append([recipe_id, 1])
    all_recipes_search_cache = {"recipes": recipes, "postings": postings}
    return all_recipes_search_cache


def all_recipe_search_tokens(value):
    return [
        word[:-1] if word.endswith("s") and len(word) > 3 else word
        for word in re.sub(r"[^a-z0-9\s]", " ", value or "").casefold().split()
        if len(word) > 2 and word not in ALL_RECIPE_SEARCH_STOPWORDS
    ]


def all_recipes_sqlite():
    global all_recipes_sqlite_connection
    if all_recipes_sqlite_connection is not None:
        return all_recipes_sqlite_connection
    path = Path(__file__).with_name(ALL_RECIPES_SEARCH_DB_FILENAME)
    if not path.exists():
        return None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        all_recipes_sqlite_connection = connection
    except sqlite3.Error as exc:
        print(f"Failed to open {ALL_RECIPES_SEARCH_DB_FILENAME}: {exc}", flush=True)
        all_recipes_sqlite_connection = None
    return all_recipes_sqlite_connection


def all_recipes_sqlite_vocab():
    global all_recipes_sqlite_vocab_cache
    if all_recipes_sqlite_vocab_cache is not None:
        return all_recipes_sqlite_vocab_cache
    connection = all_recipes_sqlite()
    if connection is None:
        all_recipes_sqlite_vocab_cache = set()
        return all_recipes_sqlite_vocab_cache
    try:
        all_recipes_sqlite_vocab_cache = {
            row["token"] for row in connection.execute("select token from tokens")
        }
    except sqlite3.Error as exc:
        print(f"Failed to load recipe search vocabulary: {exc}", flush=True)
        all_recipes_sqlite_vocab_cache = set()
    return all_recipes_sqlite_vocab_cache


def all_recipe_fts_query(tokens):
    vocab = all_recipes_sqlite_vocab()
    terms = []
    for token in dict.fromkeys(tokens):
        if token in vocab:
            terms.append(token)
            continue
        terms.extend(get_close_matches(token, vocab, n=3, cutoff=0.82))
    return " OR ".join(dict.fromkeys(terms))


def all_recipe_sqlite_candidate_summaries(meal_prompt, recipe_ideas=None, limit=40):
    connection = all_recipes_sqlite()
    if connection is None:
        return None
    query_tokens = []
    raw_queries = [meal_prompt] + [
        value
        for idea in recipe_ideas or []
        for value in (idea.get("name"), idea.get("query"))
    ]
    for query in raw_queries:
        query_tokens.extend(all_recipe_search_tokens(str(query or "")))
    for token in list(dict.fromkeys(query_tokens)):
        query_tokens.extend(ALL_RECIPE_QUERY_EXPANSIONS.get(token, ()))
    fts_query = all_recipe_fts_query(query_tokens)
    if not fts_query:
        return []
    try:
        rows = connection.execute(
            """
            select
              recipes.id,
              recipes.name,
              recipes.payload,
              recipe_fts.name as title_text,
              recipe_fts.category || ' ' || recipe_fts.ingredients || ' ' || recipe_fts.description as search_text,
              recipe_fts.name || ' ' || recipe_fts.category || ' ' || recipe_fts.ingredients as meal_text,
              bm25(recipe_fts, 9.0, 4.0, 6.0, 1.5, 0.5) as rank
            from recipe_fts
            join recipes on recipes.id = recipe_fts.recipe_id
            where recipe_fts match ?
            order by rank
            limit ?
            """,
            (fts_query, limit),
        ).fetchall()
    except sqlite3.Error as exc:
        print(f"SQLite recipe search failed: {exc}", flush=True)
        return []
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "title_text": normalize_cuisine_text(row["title_text"]),
            "search_text": normalize_cuisine_text(row["search_text"]),
            "meal_text": normalize_cuisine_text(row["meal_text"]),
            "database_recipe": json.loads(row["payload"]),
        }
        for row in rows
    ]


def all_recipe_candidate_summaries(meal_prompt, recipe_ideas=None, limit=40):
    sqlite_summaries = all_recipe_sqlite_candidate_summaries(
        meal_prompt,
        recipe_ideas=recipe_ideas,
        limit=limit,
    )
    if sqlite_summaries is not None:
        return sqlite_summaries

    index = all_recipes_search_index()
    recipe_summaries = index.get("recipes") or {}
    postings = index.get("postings") or {}
    query_tokens = []
    raw_queries = [meal_prompt] + [
        value
        for idea in recipe_ideas or []
        for value in (idea.get("name"), idea.get("query"))
    ]
    for query in raw_queries:
        query_tokens.extend(all_recipe_search_tokens(str(query or "")))
    for token in list(dict.fromkeys(query_tokens)):
        query_tokens.extend(ALL_RECIPE_QUERY_EXPANSIONS.get(token, ()))

    scores = {}
    for token in dict.fromkeys(query_tokens):
        matching_tokens = [token] if token in postings else get_close_matches(token, postings.keys(), n=3, cutoff=0.82)
        for matching_token in matching_tokens:
            token_weight_multiplier = 1 if matching_token == token else 0.75
            for recipe_id, weight in postings.get(matching_token, []):
                scores[recipe_id] = scores.get(recipe_id, 0) + max(1, round(weight * token_weight_multiplier))

    if not scores and query_tokens:
        joined_query = normalize_cuisine_text(" ".join(query_tokens))
        for recipe_id, summary in recipe_summaries.items():
            if joined_query and joined_query in summary.get("search_text", ""):
                scores[recipe_id] = 1

    ranked_ids = sorted(
        scores,
        key=lambda recipe_id: (
            -scores[recipe_id],
            recipe_summaries.get(recipe_id, {}).get("name", "").casefold(),
        ),
    )
    return [
        recipe_summaries[recipe_id]
        for recipe_id in ranked_ids[:limit]
        if recipe_id in recipe_summaries
    ]


def all_recipe_search_score(recipe, meal_prompt, recipe_ideas=None, indexed_recipe=None):
    prompt_queries = [meal_prompt]
    for idea in recipe_ideas or []:
        prompt_queries.extend([idea.get("name"), idea.get("query")])
    prompt_queries = [
        re.sub(r"\s+", " ", str(query or "")).strip()
        for query in prompt_queries
        if re.sub(r"\s+", " ", str(query or "")).strip()
    ]
    title_text = (
        indexed_recipe.get("title_text")
        if indexed_recipe
        else normalize_cuisine_text(recipe.get("title"))
    )
    search_text = (
        indexed_recipe.get("search_text")
        if indexed_recipe
        else all_recipe_query_terms(recipe)
    )
    best_score = 0
    for query in prompt_queries:
        query_words = [
            word[:-1] if word.endswith("s") and len(word) > 3 else word
            for word in re.sub(r"[^a-z0-9\s]", " ", query or "").casefold().split()
            if len(word) > 2 and word not in ALL_RECIPE_SEARCH_STOPWORDS
        ]
        if not query_words:
            continue
        query_text = normalize_cuisine_text(" ".join(query_words))
        score = 0
        if query_text and query_text == title_text:
            score += 140
        elif query_text and title_text.startswith(query_text):
            score += 110
        elif query_text and query_text in title_text:
            score += 80
        elif query_text and query_text in search_text:
            score += 35
        for word in query_words:
            if re.search(rf"\b{re.escape(word)}\b", title_text):
                score += 18
            elif re.search(rf"\b{re.escape(word)}\b", search_text):
                score += 8
        best_score = max(best_score, score)

    best_score += all_recipe_prompt_score(recipe, meal_prompt, indexed_recipe) * 10
    requested_groups = requested_spoonacular_ingredient_groups(meal_prompt)
    if requested_groups and spoonacular_matches_requested_ingredients(recipe, requested_groups):
        best_score += 35 * len(requested_groups)
    if spoonacular_matches_meal_type(recipe, meal_prompt):
        best_score += 10
    return best_score


def all_recipe_prompt_score(recipe, meal_prompt, indexed_recipe=None):
    recipe_words = normalized_food_words(recipe.get("title"))
    prompt_words = {
        word
        for word in normalized_food_words(meal_prompt)
        if word not in RECIPE_SEARCH_STOPWORDS
    }
    score = len(recipe_words & prompt_words)
    meal_text = indexed_recipe.get("meal_text") if indexed_recipe else spoonacular_normalized_search_text(recipe)
    for meal_type, terms in RECIPE_MEAL_TYPE_HINTS.items():
        if re.search(rf"\b{meal_type}\b", meal_prompt, re.I):
            score += sum(2 for term in terms if term in meal_text)
    if re.search(r"\bdinner\b", meal_prompt, re.I):
        score -= sum(3 for term in RECIPE_NON_DINNER_TERMS if term in meal_text)
    return score


def all_recipe_candidates_for_prompt(meal_prompt, dietary_restrictions="", recipe_ideas=None):
    requested_groups = requested_spoonacular_ingredient_groups(meal_prompt)
    candidates = []
    for indexed_recipe in all_recipe_candidate_summaries(meal_prompt, recipe_ideas, limit=20):
        database_recipe = indexed_recipe.get("database_recipe")
        if not database_recipe:
            database_recipe = load_all_recipes_by_id().get(indexed_recipe["id"])
        if not database_recipe:
            continue
        if recipe_contains_offal(database_recipe):
            continue
        recipe = all_recipe_to_spoonacular_recipe(database_recipe)
        if not spoonacular_ingredients(recipe):
            continue
        if not spoonacular_respects_restrictions(recipe, dietary_restrictions):
            continue
        hard_ingredient_match = spoonacular_matches_requested_ingredients(recipe, requested_groups)
        score = all_recipe_search_score(recipe, meal_prompt, recipe_ideas, indexed_recipe)
        if requested_groups and not hard_ingredient_match:
            score -= 120
        if not spoonacular_matches_meal_type(recipe, meal_prompt):
            score -= 80
        if score <= 0:
            continue
        recipe["_snapp_search_score"] = score
        candidates.append(recipe)

    candidates.sort(
        key=lambda recipe: (
            -recipe.get("_snapp_search_score", 0),
            recipe.get("title", "").casefold(),
        )
    )
    deduped = []
    seen_names = set()
    for recipe in candidates[:20]:
        name = normalized_recipe_name(recipe.get("title"))
        if name in seen_names:
            continue
        seen_names.add(name)
        deduped.append(recipe)
        if len(deduped) >= 20:
            break
    return deduped


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
    for summary in summaries[:THEMEALDB_FILTER_LOOKUP_LIMIT]:
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
    seen_terms = set()
    for idea in recipe_ideas:
        for value in (idea.get("query"), idea.get("name")):
            term = re.sub(r"\s+", " ", value or "").strip()
            identity = term.casefold()
            if term and identity not in seen_terms:
                search_terms.append(term)
                seen_terms.add(identity)
    prompt_term = re.sub(r"\s+", " ", meal_prompt or "").strip()
    if prompt_term and prompt_term.casefold() not in seen_terms:
        search_terms.append(prompt_term)
    search_terms = search_terms[:6]

    def add_recipe(meal):
        recipe = mealdb_recipe_to_recipe(meal)
        recipe_id = spoonacular_recipe_id(recipe or {})
        if recipe and recipe_id not in seen_ids:
            candidates.append(recipe)
            seen_ids.add(recipe_id)
        return len(candidates) >= THEMEALDB_SEARCH_LIMIT

    for query in search_terms:
        for meal in search_mealdb_meals(query):
            if add_recipe(meal):
                return candidates

    requested_area = detect_requested_spoonacular_cuisine(meal_prompt)
    idea_areas = [
        idea.get("cuisine")
        for idea in recipe_ideas
        if idea.get("cuisine")
    ]
    for area in [requested_area, *idea_areas]:
        if not area:
            continue
        for meal in mealdb_filter_meals("a", "American" if area == "United States" else area):
            if add_recipe(meal):
                return candidates

    requested_ingredients = requested_spoonacular_ingredient_groups(meal_prompt)
    for ingredient, _aliases in requested_ingredients:
        for meal in mealdb_filter_meals("i", ingredient):
            if add_recipe(meal):
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
            if add_recipe(meal):
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


INGREDIENT_CANONICAL_PATTERNS = (
    (r"\b(sirloin|ribeye|rib eye|brisket|steak|short ribs?|ground beef|minced beef|beef)\b", "beef"),
    (r"\b(chicken|poultry)\b", "chicken"),
    (r"\b(pork|bacon|ham|sausage)\b", "pork"),
    (r"\b(shrimp|prawns?)\b", "shrimp"),
    (r"\b(salmon|tuna|cod|fish)\b", "fish"),
    (r"\b(flat rice noodles?|rice noodles?|egg noodles?|noodles?|spaghetti|pasta|penne|linguine|macaroni)\b", "noodles"),
    (r"\b(jasmine rice|basmati rice|brown rice|white rice|rice)\b", "rice"),
    (r"\b(birds eye chilli(?:es)?|birds eye chile(?:s)?|bird'?s eye|chill(?:i|y|ies)|chiles?|jalapenos?|serranos?|peppers?)\b", "pepper"),
    (r"\b(tomatoes?|diced tomatoes|canned tomatoes|crushed tomatoes|tomato sauce|tomato paste)\b", "tomato"),
    (r"\b(garlic|garlic cloves?|minced garlic)\b", "garlic"),
    (r"\b(onions?|shallots?)\b", "onion"),
    (r"\b(basil|basil leaves|fresh basil)\b", "basil"),
    (r"\b(cilantro|coriander|parsley|mint|thyme|oregano|rosemary)\b", "herbs"),
    (r"\b(broccoli|broccolini)\b", "broccoli"),
    (r"\b(carrots?)\b", "carrot"),
    (r"\b(potatoes?)\b", "potato"),
    (r"\b(beans?|black beans|kidney beans|pinto beans)\b", "beans"),
    (r"\b(cheddar|mozzarella|parmesan|pecorino|feta|cheese)\b", "cheese"),
    (r"\b(soy sauce|tamari)\b", "soy sauce"),
    (r"\b(fish sauce)\b", "fish sauce"),
    (r"\b(oyster sauce)\b", "oyster sauce"),
    (r"\b(vegetable oil|canola oil|olive oil|oil)\b", "oil"),
    (r"\b(sugar|caster sugar|brown sugar)\b", "sugar"),
)


def ingredient_match_terms(value):
    text = normalize_cuisine_text(value)
    terms = set(normalized_food_words(text))
    for phrase, aliases in RECIPE_INGREDIENT_ALIASES.items():
        phrase_text = normalize_cuisine_text(phrase)
        if phrase_text and re.search(rf"\b{re.escape(phrase_text)}\b", text):
            terms.add(phrase_text)
            terms.update(normalize_cuisine_text(alias) for alias in aliases)
    for pattern, canonical in INGREDIENT_CANONICAL_PATTERNS:
        if re.search(pattern, text):
            terms.add(canonical)
    return {term for term in terms if term}


def generate_general_ingredient_search_terms(recipe_ingredients):
    ingredient_names = [
        re.sub(r"\s+", " ", ingredient.get("name") or "").strip()
        for ingredient in recipe_ingredients
        if ingredient.get("name")
    ]
    if not ingredient_names:
        return {}

    cache_key = tuple(name.casefold() for name in ingredient_names)
    cached = ingredient_generalization_cache.get(cache_key)
    if cached is not None:
        return cached

    by_name = {}
    for name in ingredient_names:
        terms = sorted(ingredient_match_terms(name))
        if terms:
            by_name[name.casefold()] = terms[:6]

    ingredient_generalization_cache[cache_key] = by_name
    return by_name


def product_recipe_match_score(product, recipe_ingredient, recipe_search_terms=None):
    product_text = " ".join(
        str(value or "")
        for value in (
            product.get("ingredient"),
            product.get("product_name"),
            product.get("food_group"),
            product.get("package_size"),
        )
    )
    recipe_text = recipe_ingredient or ""
    product_terms = ingredient_match_terms(product_text)
    recipe_terms = ingredient_match_terms(recipe_text)
    for term in recipe_search_terms or []:
        recipe_terms.update(ingredient_match_terms(term))
        normalized_term = normalize_cuisine_text(term)
        if normalized_term:
            recipe_terms.add(normalized_term)
    if not product_terms or not recipe_terms:
        return 0

    score = len(product_terms & recipe_terms) * 10
    product_normalized = normalize_cuisine_text(product_text)
    recipe_normalized = normalize_cuisine_text(recipe_text)
    for term in recipe_terms:
        if re.search(rf"\b{re.escape(term)}\b", product_normalized):
            score += 4
    for term in product_terms:
        if re.search(rf"\b{re.escape(term)}\b", recipe_normalized):
            score += 2
    if normalize_cuisine_text(product.get("ingredient")) in recipe_terms:
        score += 8
    return score


def product_matches_recipe_ingredient(product, recipe_ingredient, recipe_search_terms=None):
    return product_recipe_match_score(product, recipe_ingredient, recipe_search_terms) > 0


def match_recipe_ingredients_to_products(recipe, products):
    matches = []
    used_product_ids = set()
    recipe_ingredients = spoonacular_ingredients(recipe)
    generalized_terms = generate_general_ingredient_search_terms(recipe_ingredients)
    for ingredient in recipe_ingredients:
        ingredient_terms = generalized_terms.get(ingredient["name"].casefold(), [])
        eligible_products = [
            product
            for product in products
            if product.get("id") not in used_product_ids
            and product_matches_recipe_ingredient(
                product,
                ingredient["name"],
                ingredient_terms,
            )
        ]
        if not eligible_products:
            matches.append((ingredient, None))
            continue
        product = sorted(
            eligible_products,
            key=lambda item: (
                -product_recipe_match_score(
                    item,
                    ingredient["name"],
                    ingredient_terms,
                ),
                product_effective_price(item),
            ),
        )[0]
        used_product_ids.add(product["id"])
        matches.append((ingredient, product))
    return matches


def morton_williams_store_lookup():
    return {"morton-williams": {"id": "morton-williams", "name": "Morton Williams"}}


def should_buy_recipe_ingredient(ingredient):
    ingredient_texts = [
        normalize_cuisine_text(str(ingredient.get(key) or ""))
        for key in ("name", "measure", "display", "original")
    ]
    text = normalize_cuisine_text(" ".join(value for value in ingredient_texts if value))
    if not text:
        return False
    quantity_prefix = r"(?:\d+(?:\.\d+)?|\d+\s+\d+/\d+|\d+/\d+)?\s*(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|pounds?|lbs?|ounces?|oz|grams?|g|kilograms?|kg|cloves?|cans?)?\s*"
    prep_only = rf"^{quantity_prefix}(?:very\s+)?(?:thinly\s+|finely\s+|roughly\s+|coarsely\s+)?(?:sliced|diced|minced|chopped|shredded|julienned|grated|crushed)$"
    no_buy_patterns = (
        prep_only,
        r"\bwater\b",
        r"\bboiling water\b",
        r"\bwarm water\b",
        r"\bcold water\b",
        r"\bas desired\b",
        r"\bto taste\b",
    )
    if any(value and re.search(prep_only, value) for value in ingredient_texts):
        return False
    return not any(re.search(pattern, text) for pattern in no_buy_patterns)


SPICE_PANTRY_TERMS = {
    "salt",
    "black pepper",
    "paprika",
    "smoked paprika",
    "cayenne pepper",
    "crushed red pepper flakes",
    "chili powder",
    "ground cumin",
    "ground coriander",
    "ground cinnamon",
    "ground ginger",
    "ground nutmeg",
    "ground cloves",
    "allspice",
    "turmeric",
    "dried oregano",
    "dried basil",
    "dried thyme",
    "dried rosemary",
    "dried sage",
    "dried parsley",
    "dill weed",
    "bay leaves",
    "Italian seasoning",
    "herbes de Provence",
    "poultry seasoning",
    "celery seed",
    "mustard powder",
    "garlic powder",
    "onion powder",
}

SPICE_PANTRY_ALIASES = {
    "pepper": "black pepper",
    "cayenne": "cayenne pepper",
    "red pepper flakes": "crushed red pepper flakes",
    "crushed red pepper": "crushed red pepper flakes",
    "cumin": "ground cumin",
    "coriander": "ground coriander",
    "cinnamon": "ground cinnamon",
    "ginger": "ground ginger",
    "nutmeg": "ground nutmeg",
    "cloves": "ground cloves",
    "oregano": "dried oregano",
    "basil": "dried basil",
    "thyme": "dried thyme",
    "rosemary": "dried rosemary",
    "sage": "dried sage",
    "parsley": "dried parsley",
    "dill": "dill weed",
    "bay leaf": "bay leaves",
    "italian seasoning": "Italian seasoning",
    "herbs de provence": "herbes de Provence",
    "herbes de provence": "herbes de Provence",
    "mustard": "mustard powder",
    "dry mustard": "mustard powder",
}


def ingredient_display_text(ingredient):
    return ingredient.get("display") or ingredient.get("measure") or ingredient.get("name") or ""


def pantry_entry_text(item):
    quantity = str(item.get("quantity") or "").strip()
    name = str(item.get("name") or "").strip()
    return f"{quantity} {name}".strip() if quantity else name


def ingredient_identity_key(text):
    from ingredient_normalization import canonical_for_product, normalize_text, parse_ingredient

    parsed = parse_ingredient(text)
    canonical = canonical_for_product(parsed.canonical_name) or canonical_for_product(normalize_text(text)) or parsed.canonical_name
    return normalize_text(canonical or text)


def spice_requirements_for_text(text):
    normalized = normalize_cuisine_text(text)
    terms = set()
    for term in SPICE_PANTRY_TERMS:
        if re.search(rf"\b{re.escape(normalize_cuisine_text(term))}s?\b", normalized):
            terms.add(term)
    for alias, canonical in SPICE_PANTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}s?\b", normalized):
            terms.add(canonical)
    return terms


def pantry_spice_keys(pantry_items):
    keys = set()
    for item in pantry_items or []:
        keys.update(spice_requirements_for_text(pantry_entry_text(item)))
    return keys


def pantry_ingredient_identity_key(text):
    # Pantry coverage cannot erase a subtype/cut/grade requirement either.
    from product_ontology import describe
    identity = describe(text).to_dict()
    if not identity.get("family"):
        return ingredient_identity_key(text)
    # Whole pantry ingredients can be chopped/sliced/grated during cooking.
    # Keep purchase forms such as ground meat and all subtype/cut constraints.
    if identity.get("form") in {"chopped", "minced", "diced", "sliced", "shredded", "grated"}:
        identity["form"] = None
    for key in ("normalized_text", "evidence", "brand"):
        identity.pop(key, None)
    return json.dumps(identity, sort_keys=True)


def pantry_quantity_buckets(pantry_items):
    from basket_quantity import canonical_quantity
    from ingredient_normalization import parse_ingredient

    buckets = {}
    for item in pantry_items or []:
        text = pantry_entry_text(item)
        parsed = parse_ingredient(text)
        key = pantry_ingredient_identity_key(text)
        if not key:
            continue
        quantity = canonical_quantity(parsed.quantity, parsed.unit, parsed.canonical_name)
        if quantity.base_quantity is None:
            continue
        bucket = buckets.setdefault(
            key,
            {
                "base_unit": quantity.base_unit,
                "dimension": quantity.dimension,
                "base_quantity": 0.0,
            },
        )
        if bucket["base_unit"] == quantity.base_unit:
            bucket["base_quantity"] += quantity.base_quantity
    return buckets


def pantry_adjusted_ingredient_text(ingredient, pantry_buckets, spice_keys, servings=None):
    from basket_quantity import Quantity, canonical_quantity, convert_quantity
    from ingredient_normalization import parse_ingredient

    text = ingredient_display_text(ingredient)
    spice_terms = spice_requirements_for_text(text)
    if spice_terms and spice_terms <= spice_keys:
        return None
    key = pantry_ingredient_identity_key(text)
    parsed = parse_ingredient(text)
    if servings and parsed.quantity is not None and re.search(r"\bper person\b", normalize_cuisine_text(text)):
        parsed.quantity *= max(1, int(servings))
        from recipe_ingredient_adapter import ingredient_with_quantity
        text = ingredient_with_quantity(text, parsed.quantity, parsed.unit)
    required = canonical_quantity(parsed.quantity, parsed.unit, parsed.canonical_name)
    bucket = pantry_buckets.get(key)
    if not bucket or required.base_quantity is None:
        return text
    if bucket["base_unit"] != required.base_unit:
        pantry_quantity = Quantity(
            bucket["base_quantity"],
            bucket["base_unit"],
            bucket["dimension"],
            bucket["base_quantity"],
            bucket["base_unit"],
        )
        pantry_quantity = convert_quantity(pantry_quantity, required.base_unit, parsed.canonical_name)
        pantry_base = pantry_quantity.base_quantity
    else:
        pantry_base = bucket["base_quantity"]
    if pantry_base is None or pantry_base <= 0:
        return text
    if pantry_base >= required.base_quantity:
        if bucket["base_unit"] == required.base_unit:
            bucket["base_quantity"] = max(0.0, bucket["base_quantity"] - required.base_quantity)
        else:
            required_in_pantry_units = convert_quantity(required, bucket["base_unit"], parsed.canonical_name)
            if required_in_pantry_units.base_quantity is not None:
                bucket["base_quantity"] = max(0.0, bucket["base_quantity"] - required_in_pantry_units.base_quantity)
            else:
                bucket["base_quantity"] = 0.0
        return None
    remaining_base = required.base_quantity - pantry_base
    bucket["base_quantity"] = 0.0
    remaining = convert_quantity(
        Quantity(remaining_base, required.base_unit, required.dimension, remaining_base, required.base_unit),
        required.unit,
        parsed.canonical_name,
    )
    if remaining.quantity is None:
        return text
    from recipe_ingredient_adapter import ingredient_with_quantity
    return ingredient_with_quantity(text, remaining.quantity, remaining.unit)


def pantry_adjusted_recipe_ingredients(recipe, pantry_items=None, servings=None):
    pantry_buckets = pantry_quantity_buckets(pantry_items or [])
    spice_keys = pantry_spice_keys(pantry_items or [])
    adjusted = []
    original_by_text = {}
    for ingredient in spoonacular_ingredients(recipe):
        if not should_buy_recipe_ingredient(ingredient):
            continue
        adjusted_text = pantry_adjusted_ingredient_text(ingredient, pantry_buckets, spice_keys, servings=servings)
        if not adjusted_text:
            continue
        adjusted.append(adjusted_text)
        original_by_text[adjusted_text] = ingredient
    return adjusted, original_by_text


def morton_williams_feature_to_product(feature, ranked_match=None):
    from basket_quantity import parse_package_info, parse_price_info

    package = parse_package_info(feature)
    price = parse_price_info(feature.get("raw_price") or feature.get("price"), feature)
    checkout_price = price.checkout_price
    if checkout_price is None and price.unit_price is not None:
        checkout_price = price.unit_price
    package_grams = None
    if package.base_quantity is not None:
        if package.base_unit == "gram":
            package_grams = int(round(package.base_quantity))
        elif package.base_unit == "milliliter":
            package_grams = int(round(package.base_quantity))
        elif package.base_unit in {"count", "each"}:
            package_grams = 454
    if not package_grams or package_grams < 1:
        package_grams = 454
    package_size = feature.get("raw_unit_text") or feature.get("package_size")
    if not package_size and package.package_quantity and package.package_unit:
        package_size = f"{package.package_quantity:g} {package.package_unit}"
    return {
        "id": feature.get("product_id"),
        "ingredient": feature.get("canonical_name") or feature.get("normalized_name"),
        "product_name": feature.get("original_product_name") or feature.get("normalized_name"),
        "food_group": feature.get("category"),
        "store_id": "morton-williams",
        "package_size": package_size or "Package size unavailable",
        "package_grams": package_grams,
        "price": round(float(checkout_price), 2) if checkout_price is not None else 0,
        "sale_price": None,
        "is_on_sale": feature.get("is_on_sale") is True,
        "sale_offer": feature.get("raw_sale_price") if feature.get("is_on_sale") is True else None,
        "calories_per_100g": 0,
        "match_confidence": getattr(ranked_match, "confidence", None),
        "match_score": getattr(ranked_match, "final_score", None),
        "pricing_source": "morton_williams",
    }


def basket_item_to_morton_williams_product(item, feature):
    product = morton_williams_feature_to_product(feature)
    checkout_cost = item.checkout_cost
    if checkout_cost is not None:
        product["price"] = round(float(checkout_cost), 2)
    if item.package.package_quantity and item.package.package_unit:
        product["package_size"] = f"{item.package.package_quantity:g} {item.package.package_unit}"
    product["packages_purchased"] = item.packages_required
    product["required_quantity"] = item.total_required.to_dict()
    required_quantity = getattr(item.total_required, "quantity", None)
    required_unit = getattr(item.total_required, "unit", None)
    if required_quantity is not None:
        product["required_quantity_display"] = f"{required_quantity:g} {required_unit or ''}".strip()
    else:
        product["required_quantity_display"] = None
    product["source_ingredients"] = list(item.ingredients)
    product["leftover_quantity"] = item.leftover.to_dict()
    product["estimated_price_total"] = round(float(checkout_cost), 2) if checkout_cost is not None else product.get("price")
    product["quantity_optimization_warnings"] = item.warnings
    product["pricing_source"] = "morton_williams_quantity_engine"
    product["purchase_quantity_display"] = purchase_quantity_display(product)
    from deal_presentation import shopping_deal_fields
    product["deal"] = shopping_deal_fields(getattr(item, "optimized_purchase", None))
    return product


def purchase_quantity_display(product):
    packages = product.get("packages_purchased")
    package_size = re.sub(r"\s+", " ", str(product.get("package_size") or "")).strip()
    if packages is None:
        return package_size or None
    try:
        packages = float(packages)
    except (TypeError, ValueError):
        return package_size or None
    if packages <= 0:
        return package_size or None
    amount = f"{packages:g}"
    normalized_size = package_size.casefold()
    if normalized_size in {"lb", "lbs", "pound", "pounds", "per lb", "per pound", "1 lb", "1 pound"}:
        return f"{amount} lb"
    if normalized_size in {"oz", "ounce", "ounces", "per oz", "per ounce", "1 oz", "1 ounce"}:
        return f"{amount} oz"
    if normalized_size in {"each", "ea", "ct", "count", "1 count"}:
        return f"{amount} item" if packages == 1 else f"{amount} items"
    if package_size:
        return f"{amount} x {package_size}"
    return f"{amount} package" if packages == 1 else f"{amount} packages"


def estimated_grams_from_required_quantity(required_quantity, ingredient_name=None):
    if not isinstance(required_quantity, dict):
        return None
    base_quantity = required_quantity.get("base_quantity")
    base_unit = required_quantity.get("base_unit")
    if base_quantity is None:
        return None
    try:
        base_quantity = float(base_quantity)
    except (TypeError, ValueError):
        return None
    if base_unit == "gram":
        return max(1, int(round(base_quantity)))
    if base_unit == "milliliter":
        from basket_quantity import density_for_ingredient

        density = density_for_ingredient(ingredient_name)
        if density:
            return max(1, int(round(base_quantity * density)))
        return max(1, int(round(base_quantity)))
    return None


def should_use_semantic_recipe_matching():
    state = matcher_warmup.get_warmup_status()
    return bool(state.model_loaded and state.index_loaded and state.status == "ready")


def prewarm_morton_williams_recipe_matches(recipes, pantry_items=None):
    ingredient_texts = []
    for recipe in recipes:
        adjusted, _original_by_text = pantry_adjusted_recipe_ingredients(
            recipe,
            pantry_items,
            servings=source_recipe_servings(recipe),
        )
        ingredient_texts.extend(adjusted)
    if not ingredient_texts:
        return
    service = basket_builder_match_service()
    service.match_recipe_ingredients(
        ingredient_texts,
        limit=15,
        use_semantic=should_use_semantic_recipe_matching(),
    )


def match_recipe_ingredients_to_morton_williams(recipe, pantry_items=None, servings=None):
    from basket_quantity import build_recipe_basket

    ingredient_texts, original_by_text = pantry_adjusted_recipe_ingredients(recipe, pantry_items, servings=servings)
    if not ingredient_texts:
        return []
    basket_recipe = {
        "id": spoonacular_recipe_id(recipe) or recipe.get("title") or "recipe",
        "ingredients": ingredient_texts,
    }
    basket = build_recipe_basket(
        basket_recipe,
        optimization_mode="balanced",
        use_semantic=should_use_semantic_recipe_matching(),
    )
    service = basket_builder_match_service()
    matches = []
    for item in basket.shopping_basket:
        feature = service.feature_by_id.get(item.product_id)
        if not feature:
            continue
        raw_ingredient = item.ingredients[0] if item.ingredients else item.product_name
        ingredient = original_by_text.get(
            raw_ingredient,
            {
                "name": ingredient_identity_key(raw_ingredient),
                "measure": raw_ingredient,
                "display": raw_ingredient,
            },
        )
        matches.append((ingredient, basket_item_to_morton_williams_product(item, feature)))
    covered_ingredients = {ingredient for item in basket.shopping_basket for ingredient in item.ingredients}
    for matched in getattr(basket, "matched_ingredients", []):
        if matched.raw_ingredient in covered_ingredients:
            continue
        if not matched.product_id or matched.match_confidence in {"low", "no_safe_match", "substitution_only"}:
            continue
        feature = service.feature_by_id.get(matched.product_id)
        if not feature:
            continue
        product = morton_williams_feature_to_product(feature)
        product["pricing_source"] = "morton_williams_match_fallback"
        product["quantity_optimization_warnings"] = matched.warnings
        ingredient = original_by_text.get(
            matched.raw_ingredient,
            {
                "name": ingredient_identity_key(matched.raw_ingredient),
                "measure": matched.raw_ingredient,
                "display": matched.raw_ingredient,
            },
        )
        matches.append((ingredient, product))
    return matches


def basket_builder_match_service():
    from basket_quantity import get_basket_builder

    return get_basket_builder().match_service


def matched_product_count(matched_products):
    return sum(1 for _ingredient, product in matched_products if product)


def spoonacular_recipe_to_dish(
    recipe,
    matched_products,
    stores,
    household_size,
    grocery_label="grocery database",
):
    from recipe_nutrition import recipe_nutrition
    source_servings = source_recipe_servings(recipe)
    nutrition = recipe_nutrition(recipe, source_servings or household_size,
                                 servings_source="recipe" if source_servings else "household")
    ingredient_lines = []
    total_price = 0
    placeholder_nutrients = {
        "protein_g": "x g",
        "carbohydrates_g": "x g",
        "fat_g": "x g",
        "fiber_g": "x g",
        "sugars_g": "x g",
        "sodium_mg": "x g",
    }

    for recipe_ingredient, product in matched_products:
        if not product:
            continue
        package_grams = int(product.get("package_grams") or 0)
        grams_total = estimated_grams_from_required_quantity(
            product.get("required_quantity"),
            recipe_ingredient.get("name") or product.get("ingredient"),
        )
        if grams_total is None:
            grams_total = package_grams if package_grams > 0 else 0
        if grams_total < 1:
            continue

        package_price = float(
            product.get("estimated_price_total")
            if product.get("estimated_price_total") is not None
            else product_effective_price(product)
        )
        total_price += package_price
        store = stores.get(product.get("store_id"), {})
        ingredient_lines.append(
            {
                "product_id": product.get("id"),
                "is_on_sale": product.get("is_on_sale") is True,
                "sale_offer": product.get("sale_offer"),
                "name": product.get("ingredient"),
                "recipe_ingredient": recipe_ingredient["name"],
                "recipe_measure": recipe_ingredient["measure"],
                "required_quantity_display": product.get("required_quantity_display"),
                "source_ingredients": product.get("source_ingredients") or [recipe_ingredient["measure"]],
                "product_name": product.get("product_name"),
                "matched_food": product.get("product_name"),
                "food_group": product.get("food_group"),
                "store_name": store.get("name", product.get("store_id")),
                "package_size": product.get("package_size"),
                "package_grams": product.get("package_grams"),
                "packages_purchased": product.get("packages_purchased"),
                "purchase_quantity_display": product.get("purchase_quantity_display"),
                "required_quantity": product.get("required_quantity"),
                "leftover_quantity": product.get("leftover_quantity"),
                "deal": product.get("deal"),
                "grams_total": grams_total,
                "grams_per_person": round(grams_total / max(1, household_size)),
                "calories_total": 0,
                "calories_per_person": 0,
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
        "servings_display": str(household_size),
        "calories_total": 0,
        "calories_per_person": 0,
        "estimated_price_total": round(total_price, 2),
        "estimated_price_per_serving": round(total_price / household_size, 2),
        "nutrition_total": dict(placeholder_nutrients),
        "nutrition_per_person": dict(placeholder_nutrients),
        "ingredients": ingredient_lines,
        "ingredients_to_buy": ingredient_lines,
        "portion_note": f"Recipe from {provider_name}. Grocery matches are from {grocery_label}.",
        "method": recipe["instructions"],
        "recipe": recipe,
        "recipe_id": recipe["id"],
        "recipe_source": recipe["source"],
        "spoonacular_id": recipe["id"],
        "spoonacular_source": recipe["source"],
        "recipe_provider": provider,
        **nutrition,
    }


def build_spoonacular_grocery_dishes(
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
        if matched_product_count(matches) < minimum_matches:
            return False
        dishes.append(spoonacular_recipe_to_dish(recipe, matches, stores, household_size))
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
    database_recipe = recipe.get("_snapp_database_recipe")
    if database_recipe:
        category = (database_recipe.get("category") or [None])[0]
        source = recipe.get("sourceUrl") or database_recipe.get("source_url")
        recipe_details = {
            "id": spoonacular_recipe_id(recipe),
            "name": recipe.get("title"),
            "category": category,
            "area": spoonacular_cuisine_label(recipe) or None,
            "instructions": spoonacular_instructions(recipe),
            "ingredients": spoonacular_ingredients(recipe),
            "thumbnail": recipe.get("image"),
            "youtube": recipe.get("_snapp_youtube"),
            "source": source,
            "source_name": database_recipe.get("source"),
            "original_usda_url": database_recipe.get("original_usda_url"),
            "equipment": database_recipe.get("equipment") or [],
            "description": database_recipe.get("description"),
            "notes": database_recipe.get("notes"),
            "nutrition": database_recipe.get("nutrition") or {},
            "food_groups": database_recipe.get("food_groups") or [],
        }
        return recipe_details
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


def parse_recipe_servings_value(value):
    if isinstance(value, int):
        return value if value > 0 else None
    raw_text = str(value or "").casefold().replace("\u2013", "-").replace("\u2014", "-")
    range_match = re.search(r"\b(\d+)\s*(?:-|to)\s*(\d+)(?:\s+servings?)?\b", raw_text)
    if range_match:
        return int(range_match.group(2))
    text = normalize_cuisine_text(raw_text)
    if not text:
        return None
    serves_match = re.search(r"\bserves\s+(\d+)\b", text)
    if serves_match:
        return int(serves_match.group(1))
    match = re.search(r"\b(\d+)\s+(?:one half cup\s+)?servings?\b", text)
    if match:
        return int(match.group(1))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def recipe_servings(recipe, fallback_servings):
    servings = parse_recipe_servings_value(recipe.get("servings"))
    if servings is None:
        database_recipe = recipe.get("_snapp_database_recipe") or recipe
        servings = parse_recipe_servings_value(database_recipe.get("yield"))
    if servings is None:
        servings = fallback_servings
    return max(MIN_HOUSEHOLD_SIZE, min(servings, MAX_HOUSEHOLD_SIZE))


def source_recipe_servings(recipe):
    servings = parse_recipe_servings_value(recipe.get("servings"))
    if servings is None:
        database_recipe = recipe.get("_snapp_database_recipe") or recipe
        servings = parse_recipe_servings_value(database_recipe.get("servings"))
    if servings is None:
        database_recipe = recipe.get("_snapp_database_recipe") or recipe
        servings = parse_recipe_servings_value(database_recipe.get("yield"))
    return servings if servings and servings > 0 else None


def source_recipe_servings_display(recipe):
    database_recipe = recipe.get("_snapp_database_recipe") or recipe
    for value in (
        database_recipe.get("servings"),
        recipe.get("servings"),
        database_recipe.get("yield"),
    ):
        if isinstance(value, int) and value > 0:
            return str(value)
        text = str(value or "").strip()
        if not text:
            continue
        range_match = re.search(r"\b(\d+)\s*(?:-|to)\s*(\d+)\b", text.casefold())
        if range_match:
            return f"{range_match.group(1)}-{range_match.group(2)}"
        servings = parse_recipe_servings_value(text)
        if servings:
            return str(servings)
    return None


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
    score = recipe.get("_snapp_search_score", 0) + spoonacular_prompt_score(recipe, meal_prompt) * 10
    if recipe_matches_filter_terms(recipe, filters["include_ingredients"], require_all=True):
        score += 20 * len(filters["include_ingredients"])
    if recipe_matches_dietary_preference(recipe, filters["dietary_preference"]):
        score += 20
    minutes = recipe_ready_minutes(recipe)
    if filters["max_cook_time"] and minutes and minutes <= filters["max_cook_time"]:
        score += 10
    return score


def collect_recipe_candidates(meal_prompt, dietary_restrictions, recipe_ideas=None):
    candidates = all_recipe_candidates_for_prompt(
        meal_prompt,
        dietary_restrictions=dietary_restrictions,
        recipe_ideas=recipe_ideas,
    )
    if candidates:
        return candidates
    raise RuntimeError("The all_recipes database could not provide recipe matches.")


def recipe_result_from_recipe(
    recipe,
    matched_products,
    stores,
    filters,
    relevance_score,
    exact_match,
    grocery_label="grocery database",
):
    servings = filters["servings"]
    dish = spoonacular_recipe_to_dish(
        recipe,
        matched_products,
        stores,
        servings,
        grocery_label=grocery_label,
    )
    recipe_details = dish.get("recipe") or {}
    recipe_details["servings"] = recipe_servings(recipe, servings)
    recipe_details["servings_display"] = source_recipe_servings_display(recipe) or str(recipe_details["servings"])
    recipe_details["cook_time_minutes"] = recipe_ready_minutes(recipe)
    recipe_details["dietary_tags"] = recipe_dietary_tags(recipe)
    recipe_details["source_link"] = recipe_details.get("source")
    dish["servings"] = recipe_details["servings"]
    dish["servings_display"] = recipe_details["servings_display"]
    dish["estimated_price_per_serving"] = round(
        dish["estimated_price_total"] / max(1, dish["servings"]), 2
    )
    dish["recipe"] = recipe_details
    dish["cook_time_minutes"] = recipe_details["cook_time_minutes"]
    dish["dietary_tags"] = recipe_details["dietary_tags"]
    dish["relevance_score"] = relevance_score
    dish["exact_match"] = exact_match
    dish["portion_note"] = (
        f"Real recipe result matched against {grocery_label} prices."
        if exact_match
        else "Closest affordable real recipe match; at least one requested filter was relaxed."
    )
    return dish


def build_real_recipe_results(
    meal_prompt,
    filters,
    products=None,
    stores=None,
    result_limit=3,
    recipe_ideas=None,
    grocery_label="grocery database",
    pantry_items=None,
):
    stores = stores or morton_williams_store_lookup()
    candidates = collect_recipe_candidates(
        meal_prompt,
        filters["dietary_restrictions"],
        recipe_ideas=recipe_ideas,
    )
    ranked_candidates = []
    for recipe in candidates:
        if not spoonacular_ingredients(recipe):
            continue
        relevance_score = recipe_constraint_score(recipe, meal_prompt, filters)
        exact_match = recipe_passes_hard_filters(recipe, filters)
        ranked_candidates.append((recipe, relevance_score, exact_match))

    ranked_candidates.sort(
        key=lambda item: (
            0 if item[2] else 1,
            -item[1],
            (item[0].get("title") or item[0].get("name") or "").casefold(),
        )
    )
    match_window = max(result_limit + 2, result_limit * max(1, REAL_RECIPE_MATCH_MULTIPLIER))
    if len(ranked_candidates) > result_limit:
        exact_ranked = [item for item in ranked_candidates if item[2]]
        if len(exact_ranked) >= result_limit:
            selected = exact_ranked[:match_window]
            selected_ids = {spoonacular_recipe_id(item[0]) for item in selected}
            fallback = [
                item for item in ranked_candidates
                if spoonacular_recipe_id(item[0]) not in selected_ids
            ][:result_limit]
            ranked_candidates = selected + fallback
        else:
            ranked_candidates = ranked_candidates[:match_window]

    prewarm_morton_williams_recipe_matches(
        [recipe for recipe, _relevance_score, _exact_match in ranked_candidates],
        pantry_items=pantry_items,
    )

    exact_results = []
    closest_results = []
    for recipe, relevance_score, exact_match in ranked_candidates:
        if products is None:
            matches = match_recipe_ingredients_to_morton_williams(
                recipe,
                pantry_items=pantry_items,
                servings=source_recipe_servings(recipe),
            )
        else:
            matches = match_recipe_ingredients_to_products(recipe, products)
        if not matches:
            continue
        result = recipe_result_from_recipe(
            recipe,
            matches,
            stores,
            filters,
            relevance_score,
            exact_match,
            grocery_label=grocery_label,
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
        best_score = exact_results[0]["relevance_score"]
        high_relevance_results = [
            result for result in exact_results
            if result["relevance_score"] >= best_score - 20
        ]
        if normalized_recipe_name(exact_results[0].get("name")) == normalized_recipe_name(meal_prompt):
            remaining = high_relevance_results[1:] or exact_results[1:]
            return [exact_results[0]] + random.sample(remaining, min(result_limit - 1, len(remaining))), False
        if len(high_relevance_results) >= result_limit:
            return random.sample(high_relevance_results, result_limit), False
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
    random.shuffle(closest_results)
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


def build_sale_ingredient_recipe_results(
    ingredient_id,
    filters,
    *,
    stores=None,
    result_limit=3,
    grocery_label="Morton Williams",
    pantry_items=None,
):
    ingredient_id = ingredient_identity_key(ingredient_id)
    recipe_ids = recipe_ids_for_sale_ingredient(ingredient_id)
    if len(recipe_ids) < MIN_SALE_RECIPE_COUNT:
        raise RuntimeError("Not enough recipes use that sale ingredient.")

    stores = stores or morton_williams_store_lookup()
    recipes_by_id = load_all_recipes_by_id()
    candidates = []
    for recipe_id in recipe_ids:
        database_recipe = recipes_by_id.get(str(recipe_id))
        if not database_recipe:
            continue
        recipe = all_recipe_to_spoonacular_recipe(database_recipe)
        if not recipe_uses_sale_ingredient(recipe, ingredient_id):
            continue
        if not spoonacular_respects_restrictions(recipe, filters["dietary_restrictions"]):
            continue
        relevance_score = recipe_constraint_score(recipe, ingredient_id, filters)
        exact_match = recipe_passes_hard_filters(recipe, filters)
        candidates.append((recipe, relevance_score, exact_match))

    candidates.sort(
        key=lambda item: (
            0 if item[2] else 1,
            -item[1],
            (item[0].get("title") or item[0].get("name") or "").casefold(),
        )
    )
    prewarm_morton_williams_recipe_matches(
        [recipe for recipe, _relevance_score, _exact_match in candidates[: max(result_limit + 3, result_limit * SALE_RECIPE_MATCH_MULTIPLIER)]],
        pantry_items=pantry_items,
    )
    results = []
    relaxed = False
    seen = set()
    for recipe, relevance_score, exact_match in candidates[: max(result_limit + 3, result_limit * SALE_RECIPE_MATCH_MULTIPLIER)]:
        matches = match_recipe_ingredients_to_morton_williams(
            recipe,
            pantry_items=pantry_items,
            servings=source_recipe_servings(recipe),
        )
        if not matches:
            continue
        matched_ingredient_ids = {
            ingredient_identity_key(ingredient.get("display") or ingredient.get("measure") or ingredient.get("name") or "")
            for ingredient, product in matches
            if product
        }
        if ingredient_id not in matched_ingredient_ids and not any(
            ingredient_id in key or key in ingredient_id for key in matched_ingredient_ids if key
        ):
            continue
        result = recipe_result_from_recipe(
            recipe,
            matches,
            stores,
            filters,
            relevance_score,
            exact_match,
            grocery_label=grocery_label,
        )
        if filters["max_budget"] is not None and result["estimated_price_total"] > filters["max_budget"]:
            relaxed = True
        recipe_key = result.get("recipe_id")
        if recipe_key in seen:
            continue
        results.append(result)
        seen.add(recipe_key)
        if len(results) == result_limit:
            return results, relaxed or any(not item.get("exact_match") for item in results)
    if len(results) < result_limit:
        raise RuntimeError("Recipe sources could not provide 3 recipes for that sale ingredient.")
    return results, relaxed


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
    store = {
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
    snap_status = store_snap_status(store, tags)
    store.update(snap_status)
    return store


def format_nominatim_store(place):
    name = place.get("name")
    if not name:
        display_name = place.get("display_name", "")
        name = display_name.split(",", 1)[0].strip()
    if not name:
        return None

    store = {
        "name": name,
        "address": place.get("display_name") or "Address not available",
        "latitude": place.get("lat"),
        "longitude": place.get("lon"),
        "website": None,
    }
    store.update(store_snap_status(store, {}))
    return store


def truthy_osm_tag(value):
    return str(value or "").casefold() in {"yes", "true", "1", "only"}


def store_snap_status(store, tags):
    name = store.get("name") or tags.get("name") or tags.get("brand") or ""
    explicit_snap = any(
        truthy_osm_tag(tags.get(key))
        for key in (
            "payment:ebt",
            "payment:snap",
            "payment:food_stamps",
            "payment:food_stamps_card",
            "payment:wic",
        )
    )
    if explicit_snap:
        return {
            "accepts_snap": True,
            "snap_source": "OpenStreetMap payment tag",
        }
    if any(re.search(pattern, name, re.IGNORECASE) for pattern in SNAP_ACCEPTING_CHAIN_PATTERNS):
        return {
            "accepts_snap": True,
            "snap_source": "Known SNAP-accepting grocery chain",
        }
    return {
        "accepts_snap": False,
        "snap_source": "SNAP acceptance not verified",
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
            timeout_seconds=STORE_LOOKUP_TIMEOUT_SECONDS,
            retry_attempts=1,
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
    try:
        zip_data = fetch_json(
            f"{ZIPPOPOTAM_URL}/{zip_code}",
            service_name="Zippopotam",
            timeout_seconds=STORE_LOOKUP_TIMEOUT_SECONDS,
            retry_attempts=1,
        )
        places = zip_data.get("places") or []
        if places:
            place = places[0]
            latitude = float(place["latitude"])
            longitude = float(place["longitude"])
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
    except (RuntimeError, KeyError, TypeError, ValueError):
        print("Zippopotam ZIP lookup unavailable; trying Nominatim.", flush=True)

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
            timeout_seconds=STORE_LOOKUP_TIMEOUT_SECONDS,
            retry_attempts=1,
        )
        if locations:
            return locations[0]
    except RuntimeError:
        return None
    return None


def find_stores_with_overpass(zip_code, boundingbox, require_postcode=True):
    south, north, west, east = boundingbox
    postcode_filter = (
        f'["addr:postcode"~"^{zip_code}(-[0-9]{{4}})?$"]'
        if require_postcode
        else ""
    )
    overpass_query = f"""
        [out:json][timeout:5];
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
        timeout_seconds=STORE_LOOKUP_TIMEOUT_SECONDS,
        retry_attempts=1,
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


def find_grocery_stores(zip_code, radius_miles=None, snap_only=False):
    cache_key = (zip_code, bool(snap_only))
    cached_result = store_search_cache.get(cache_key)
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
        if snap_only:
            stores = [store for store in stores if store.get("accepts_snap")]
        stores = stores[:30]
        store_search_cache[cache_key] = {
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


@app.get("/ready")
def ready():
    if os.getenv("SNAPP_ENV", "").lower() == "production" and os.getenv("SNAPP_DEPENDENCY_READINESS", "1") == "1":
        from security_readiness import dependencies_ready
        if not dependencies_ready():
            return jsonify({"status": "unavailable", "dependencies": "unavailable"}), 503
    state = matcher_warmup.get_warmup_status()
    artifact_validation = validate_runtime_artifacts().safe_dict()
    allow_degraded = os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() in {"1", "true", "yes"}
    is_ready = state.status == "ready" and artifact_validation["ok"]
    is_degraded_allowed = state.status == "degraded" and allow_degraded and artifact_validation["ok"]
    status_code = 200 if is_ready or is_degraded_allowed else 503
    payload = state.safe_dict()
    payload["artifact_validation"] = artifact_validation
    payload["semantic_readiness"] = state.semantic_readiness if is_ready or is_degraded_allowed else "unavailable"
    ready_diagnostics = matcher_warmup.module_diagnostics(include_private_ids=True)
    ready_message = (
        "ready_request "
        f"pid={ready_diagnostics.get('pid')} "
        f"ppid={os.getppid()} "
        f"thread={ready_diagnostics.get('thread')} "
        f"module_name={ready_diagnostics.get('module_name')} "
        f"manager_id={ready_diagnostics.get('manager_id')} "
        f"state_id={ready_diagnostics.get('state_id')} "
        f"status={state.status} "
        f"warmup_completed={state.warmup_completed} "
        f"model_loaded={state.model_loaded} "
        f"index_loaded={state.index_loaded} "
        f"finished_at={state.finished_at}"
    )
    log_event(
        ready_message,
        event_name="ready_request",
        request_id=request.snapp_request_id,
        status=state.status,
        status_code=status_code,
        artifact_validation_ok=artifact_validation["ok"],
        state_artifact_validation_ok=state.artifact_validation_ok,
        **ready_diagnostics,
    )
    if state.status == "warming" and actual_matcher_components_ready():
        log_event(
            ready_message.replace("ready_request", "ready_state_invariant_violation"),
            level=40,
            event_name="ready_state_invariant_violation",
            request_id=request.snapp_request_id,
            status=state.status,
            status_code=status_code,
            artifact_validation_ok=artifact_validation["ok"],
            state_artifact_validation_ok=state.artifact_validation_ok,
            **ready_diagnostics,
        )
    return jsonify(payload), status_code


def actual_matcher_components_ready():
    try:
        import product_compatibility

        service = getattr(product_compatibility, "_match_service_singleton", None)
        if service is None:
            return False
        retriever = service.retriever
        return (
            getattr(retriever, "_features", None) is not None
            and getattr(retriever, "_lexical_docs", None) is not None
            and getattr(retriever, "_index_embeddings", None) is not None
            and getattr(retriever.backend, "_model", None) is not None
        )
    except Exception:
        return False


@app.get("/internal/diagnostics")
def internal_diagnostics():
    auth_error = admin_required()
    if auth_error:
        return auth_error
    from product_compatibility import get_product_match_service

    service = get_product_match_service()
    return jsonify(
        {
            "request_id": request.snapp_request_id,
            "health": "ok",
            "ready": matcher_warmup.get_warmup_status().safe_dict(),
            "artifact_validation": validate_runtime_artifacts().safe_dict(),
            "warmup_module": matcher_warmup.module_diagnostics(include_private_ids=True),
            "override_summary": override_summary(),
            "retrieval_stats": service.retriever.stats.to_dict(),
            "match_cache_size": len(service.cache),
            "query_cache_size": len(service.retriever.query_cache),
            "metrics": metrics.snapshot(),
        }
    )


@app.get("/internal/metrics")
def internal_metrics():
    auth_error = admin_required()
    if auth_error:
        return auth_error
    return jsonify(metrics.snapshot())


@app.post("/internal/cache/clear")
def internal_cache_clear():
    auth_error = admin_required()
    if auth_error:
        return auth_error
    from basket_quantity import get_basket_builder
    from product_compatibility import get_product_match_service

    data, error = validated_json_payload()
    if error:
        return error
    service = get_product_match_service()
    service.cache.clear()
    service.retriever.query_cache.clear()
    builder = get_basket_builder()
    builder.clear_caches()
    metrics.increment("cache_clear_requests")
    return jsonify({"status": "cleared", "request_id": request.snapp_request_id})


@app.get("/internal/review/queues")
def internal_review_queues():
    auth_error = admin_required()
    if auth_error:
        return auth_error
    report_path = Path(__file__).resolve().parent / "evaluation" / "recipe_pipeline_failure_reports.json"
    if not report_path.exists():
        return json_error("Failure report artifact is missing. Run audit_recipe_pipeline.py first.", 503)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    limit = max(1, min(int(request.args.get("limit", MAX_REVIEW_REPORT_ITEMS)), MAX_REVIEW_REPORT_ITEMS))
    return jsonify(
        {
            "request_id": request.snapp_request_id,
            "unmatched": report.get("top_unmatched_normalized_ingredients", [])[:limit],
            "low_confidence": report.get("top_low_confidence_ingredients", [])[:limit],
            "parsing_warnings": report.get("top_parsing_warnings", [])[:limit],
            "quantity_warnings": report.get("top_quantity_failures", [])[:limit],
            "suspicious_cost": report.get("top_basket_cost_impact_failures", [])[:limit],
        }
    )


@app.get("/internal/review/inspect")
def internal_review_inspect():
    auth_error = admin_required()
    if auth_error:
        return auth_error
    ingredient = request.args.get("ingredient", "").strip()
    if not ingredient:
        return json_error("ingredient query parameter is required.", 400)
    if len(ingredient) > MAX_DISH_PROMPT_CHARS:
        return json_error("ingredient query is too long.", 400)
    from basket_quantity import canonical_quantity, parse_package_info, parse_price_info
    from ingredient_normalization import parse_ingredient
    from product_compatibility import get_product_match_service, profile_from_query

    service = get_product_match_service()
    profile, parsed = profile_from_query(ingredient, service.overrides)
    retrieval = service.retriever.retrieve_product_candidates(profile.normalized_signature, limit=30)
    match = service._match_from_retrieval(ingredient, profile, parsed, retrieval, time.perf_counter(), 5, 30)
    package = None
    price = None
    if match.selected_match:
        feature = service.feature_by_id.get(match.selected_match.product_id, {})
        package = parse_package_info(feature).__dict__
        price = parse_price_info(feature.get("raw_price") or feature.get("price"), feature).__dict__
    parsed_ingredient = parse_ingredient(ingredient)
    required = canonical_quantity(parsed_ingredient.quantity, parsed_ingredient.unit, parsed_ingredient.canonical_name)
    return jsonify(
        {
            "request_id": request.snapp_request_id,
            "ingredient": ingredient,
            "parsed": parsed,
            "required_quantity": required.__dict__,
            "top_candidates": [candidate.to_dict() for candidate in retrieval.candidates[:10]],
            "match": match.to_dict(),
            "selected_package": package,
            "selected_price": price,
        }
    )


@app.post("/internal/review/overrides")
def internal_review_overrides():
    auth_error = admin_required()
    if auth_error:
        return auth_error
    data, error = validated_json_payload()
    if error:
        return error
    action = str(data.get("action") or "").strip()
    actor = str(data.get("actor") or "internal-admin").strip()[:80]
    try:
        result = mutate_override(action, data, actor=actor)
    except ValueError as exc:
        return json_error(str(exc), 400)
    except Exception as exc:
        metrics.increment("override_mutation_failures")
        log_event("override_mutation_failed", error_type=type(exc).__name__)
        return json_error("Override mutation failed.", 500)
    metrics.increment("override_mutations")
    log_event("override_mutated", action=action, actor=actor)
    return jsonify({"request_id": request.snapp_request_id, **result})


@app.get("/dev/product-candidates")
def dev_product_candidates():
    environment = os.getenv("SNAPP_ENV") or os.getenv("FLASK_ENV") or ""
    if environment.casefold() == "production":
        return jsonify({"error": "Development endpoint is disabled in production."}), 404
    ingredient = request.args.get("ingredient", "").strip()
    if not ingredient:
        return jsonify({"error": "ingredient query parameter is required."}), 400
    try:
        limit = max(1, min(int(request.args.get("limit", 30)), 50))
    except ValueError:
        return jsonify({"error": "limit must be an integer."}), 400
    try:
        from product_retrieval import retrieve_product_candidates

        result = retrieve_product_candidates(ingredient, limit=limit)
    except Exception as exc:
        return jsonify({"error": "Candidate retrieval failed.", "details": str(exc)}), 503
    return jsonify(result.to_dict())


@app.get("/dev/product-match")
def dev_product_match():
    environment = os.getenv("SNAPP_ENV") or os.getenv("FLASK_ENV") or ""
    if environment.casefold() == "production":
        return jsonify({"error": "Development endpoint is disabled in production."}), 404
    ingredient = request.args.get("ingredient", "").strip()
    if not ingredient:
        return jsonify({"error": "ingredient query parameter is required."}), 400
    try:
        limit = max(1, min(int(request.args.get("limit", 5)), 20))
    except ValueError:
        return jsonify({"error": "limit must be an integer."}), 400
    try:
        from product_compatibility import match_recipe_ingredient

        result = match_recipe_ingredient(ingredient, limit=limit)
    except Exception as exc:
        return jsonify({"error": "Product matching failed.", "details": str(exc)}), 503
    return jsonify(result.to_dict())


@app.post("/api/recipes/search")
def recipe_search():
    request_started = time.perf_counter()
    data, error = validated_json_payload()
    if error:
        return error
    query = re.sub(r"\s+", " ", str(data.get("query") or "")).strip()
    if not query:
        return json_error("Recipe search query is required.", 400)
    if len(query) > MAX_DISH_PROMPT_CHARS:
        return json_error("Recipe search query is too long.", 400)
    try:
        limit = max(1, min(int(data.get("limit") or 10), 50))
    except (TypeError, ValueError):
        return json_error("limit must be an integer.", 400)

    try:
        from recipe_search_typesense import TypesenseUnavailable, search_recipes

        result = search_recipes(
            query,
            limit=limit,
            max_time=data.get("max_time"),
            min_time=data.get("min_time"),
            include_ingredients=data.get("include_ingredients"),
            exclude_ingredients=data.get("exclude_ingredients"),
            categories=data.get("categories"),
            dietary=data.get("dietary"),
            state=data.get("state"),
        )
    except TypesenseUnavailable:
        log_event(
            "recipe_search_unavailable",
            request_id=request.snapp_request_id,
            total_ms=round((time.perf_counter() - request_started) * 1000, 2),
        )
        return json_error("Recipe search is temporarily unavailable.", 503)
    except Exception as exc:
        log_event("recipe_search_failed", request_id=request.snapp_request_id, error_type=type(exc).__name__)
        return json_error("Recipe search failed.", 503)

    metrics.observe_latency("recipe_search", result["total_latency_ms"])
    log_event(
        "recipe_search_complete",
        request_id=request.snapp_request_id,
        result_count=len(result["results"]),
        found=result.get("found"),
        typesense_ms=result["typesense_latency_ms"],
        total_ms=result["total_latency_ms"],
    )
    return jsonify({"request_id": request.snapp_request_id, **result})


@app.route("/api/recipes/search", methods=["OPTIONS"])
def recipe_search_options():
    return ("", 204)


def recipe_chat_detail_record(recipe_id):
    """Typesense owns generated recipe facts; Dishes keeps its own source."""
    from recipe_chat import configured_service
    from recipe_search_typesense import get_recipe_by_id
    indexed = get_recipe_by_id(recipe_id, configured_service().config)
    if indexed is None:
        return None, None
    names = indexed.get("ingredient_names") or []
    lines = indexed.get("ingredients_text") or names
    instructions = indexed.get("instructions") or ""
    matcher_instructions = (
        "\n".join(step for step in instructions if isinstance(step, str))
        if isinstance(instructions, list) else instructions
    )
    recipe = {
        "id": recipe_id, "title": indexed.get("title"),
        "extendedIngredients": [
            {"name": names[i] if i < len(names) else line, "original": line}
            for i, line in enumerate(lines)],
        "instructions": matcher_instructions,
        "servings": indexed.get("servings"),
        "_snapp_recipe_provider": "SNAPP recipe index",
    }
    detail = spoonacular_recipe_from_recipe(recipe)
    # Keep original step order/text rather than the Dishes string conversion.
    detail["instructions"] = indexed.get("instructions") or ""
    detail["servings"] = indexed.get("servings")
    detail["categories"] = indexed.get("categories", [])
    detail["equipment"] = indexed.get("equipment", [])
    detail["source_id"] = indexed.get("source_id")
    detail["stored_ingredients"] = indexed.get("ingredients", [])
    for key in ("total_time_minutes", "cook_time_minutes"):
        if indexed.get(key) is not None:
            detail[key] = indexed[key]
    return recipe, detail


def recipe_chat_grocery_estimate(recipe, matches, pantry):
    required, _ = pantry_adjusted_recipe_ingredients(
        recipe, pantry, servings=source_recipe_servings(recipe))
    covered, total = set(), 0.0
    for ingredient, product in matches:
        if not product:
            continue
        price = product.get("estimated_price_total")
        if price is None:
            price = product.get("price")
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(price) or price <= 0:
            continue
        total += price
        covered.update(product.get("source_ingredients") or [ingredient.get("measure") or ingredient.get("display")])
    missing = sum(line not in covered for line in required)
    status = "complete" if not missing else "partial" if total > 0 else "unavailable"
    return {"total": round(total, 2) if status != "unavailable" else None,
            "currency": "USD", "status": status, "unpriced_ingredients": missing}


@app.route("/api/recipes/nutrition", methods=["POST", "OPTIONS"])
def recipe_nutrition_preview():
    if request.method == "OPTIONS":
        return ("", 204)
    data, error = validated_json_payload()
    if error:
        return error
    recipe = data.get("recipe")
    if not isinstance(recipe, dict):
        return json_error("A recipe is required.", 400)
    ingredients = recipe.get("ingredients") or recipe.get("extendedIngredients") or []
    if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= 100:
        return json_error("Provide between 1 and 100 ingredient lines.", 400)
    if any(len(json.dumps(item)) > 4000 for item in ingredients):
        return json_error("Ingredient line is too long.", 400)
    from recipe_nutrition import recipe_nutrition
    source_servings = source_recipe_servings(recipe)
    servings = source_servings or parse_household_size(data.get("household_size"))
    return jsonify(recipe_nutrition(recipe, servings, servings_source="recipe" if source_servings else "household"))


@app.route("/api/recipes/detail", methods=["POST", "OPTIONS"])
def recipe_chat_detail():
    if request.method == "OPTIONS":
        return ("", 204)
    data, error = validated_json_payload()
    if error:
        return error
    recipe_id = data.get("recipe_id")
    if not isinstance(recipe_id, str) or not recipe_id.strip() or len(recipe_id) > 500:
        return json_error("A recipe ID is required.", 400)
    try:
        recipe, detail = recipe_chat_detail_record(recipe_id)
        if recipe is None:
            return json_error("Recipe is no longer available.", 404)
        dish = {"recipe_id": recipe_id, "name": detail.get("name"), "recipe": detail}
        matches = None
        if data.get("for_schedule") or data.get("include_price_estimate"):
            pantry = parse_pantry_items(data.get("pantry_items"))
            if len(pantry) > MAX_PANTRY_ITEMS_PER_REQUEST:
                return json_error("Too many pantry items in request.", 400)
            try:
                matches = match_recipe_ingredients_to_morton_williams(
                    recipe, pantry_items=pantry, servings=source_recipe_servings(recipe))
                dish["grocery_estimate"] = recipe_chat_grocery_estimate(recipe, matches, pantry)
            except Exception:
                if data.get("for_schedule"):
                    raise
                dish["grocery_estimate"] = {"total": None, "currency": "USD", "status": "unavailable"}
        if data.get("for_schedule"):
            estimate = dish["grocery_estimate"]
            dish = spoonacular_recipe_to_dish(
                recipe, matches, morton_williams_store_lookup(),
                parse_household_size(data.get("household_size")), grocery_label="Morton Williams")
            dish["recipe"] = detail
            dish.pop("servings", None)
            dish.pop("servings_display", None)
            dish["grocery_estimate"] = estimate
        elif data.get("include_nutrition"):
            from recipe_nutrition import recipe_nutrition
            source_servings = source_recipe_servings(recipe)
            dish.update(recipe_nutrition(recipe, source_servings or parse_household_size(data.get("household_size")),
                                        servings_source="recipe" if source_servings else "household"))
        if data.get("include_sale_matches"):
            # Presentation metadata from existing matching; never infer offers from recipe words.
            try:
                sale_matches = match_recipe_ingredients_to_morton_williams(
                    recipe, pantry_items=[], servings=source_recipe_servings(recipe))
                dish["sale_ingredients"] = [
                    {"recipe_measure": ingredient.get("measure"),
                     "recipe_display": ingredient.get("display"),
                     "product_name": product.get("product_name"),
                     "is_on_sale": True, "sale_offer": product.get("sale_offer")}
                    for ingredient, product in sale_matches
                    if product and product.get("is_on_sale") is True]
            except Exception as exc:
                log_event("recipe_sale_metadata_failed", request_id=request.snapp_request_id,
                          error_type=type(exc).__name__)
                dish["sale_metadata_unavailable"] = True
        from recipe_chat_presentation import localize_detail
        display = localize_detail(recipe_id, detail, data.get("locale", "en"))
        if display is not None:
            dish["localized_recipe"] = display
        return jsonify({"dish": dish})
    except Exception as exc:
        log_event("recipe_detail_failed", request_id=request.snapp_request_id, error_type=type(exc).__name__)
        return json_error("Recipe could not be loaded. Try again shortly.", 503)


@app.post("/api/recipes/chat", provide_automatic_options=False)
def recipe_chat():
    data, error = validated_json_payload()
    if error:
        return error
    from recipe_chat import configured_service
    from recipe_search_typesense import TypesenseUnavailable

    try:
        from recipe_chat_multilingual import handle_message as localized_chat
        result = localized_chat(configured_service(), data.get("message"), data.get("state"),
                                locale=data.get("locale", "en"),
                                pantry_items=parse_pantry_items(data.get("pantry_items")),
                                household_size=parse_household_size(data.get("household_size")))
    except ValueError as exc:
        return json_error(str(exc), 400)
    except TypesenseUnavailable:
        return json_error("Recipe search is temporarily unavailable.", 503)
    except Exception as exc:
        log_event("recipe_chat_failed", request_id=request.snapp_request_id, error_type=type(exc).__name__)
        return json_error("Recipe chat is temporarily unavailable.", 503)
    metrics.observe_latency("recipe_chat", result["search_metadata"]["latency_ms"])
    return jsonify({"request_id": request.snapp_request_id, **result})


@app.route("/api/recipes/chat", methods=["OPTIONS"])
def recipe_chat_options():
    return ("", 204)


@app.post("/chat")
def chat():
    data, error = validated_json_payload()
    if error:
        return error
    message = (data.get("message") or "").strip()
    if not message:
        return json_error("Message is required.", 400)
    if len(message) > 1000:
        return json_error("Message is too long.", 400)
    try:
        reply, total_tokens = generate_reply(message)
    except Exception as exc:
        return json_error("Model request failed.", 503)
    return jsonify({"reply": reply, "usage": {"total_tokens": total_tokens}})


@app.route("/chat", methods=["OPTIONS"])
def chat_options():
    return ("", 204)


@app.get("/grocery-stores")
def grocery_stores():
    zip_code = request.args.get("zip", "").strip()
    radius_miles = parse_store_radius_miles(request.args.get("radius_miles"))
    snap_only = str(request.args.get("snap_only") or "1").casefold() not in {"0", "false", "no"}
    if not ZIP_CODE_PATTERN.fullmatch(zip_code):
        return jsonify({"error": "Enter a valid 5-digit US ZIP code."}), 400

    try:
        location, stores, center = find_grocery_stores(zip_code, radius_miles, snap_only=snap_only)
    except RuntimeError as exc:
        return json_error("Store search is temporarily unavailable.", 503)

    if location is None:
        return jsonify({"error": "ZIP code not found."}), 404

    return jsonify(
        {
            "zip_code": zip_code,
            "location": location,
            "center": center,
            "radius_miles": radius_miles,
            "snap_only": snap_only,
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
        return json_error("Store search is temporarily unavailable.", 503)

    if not result:
        return jsonify({"error": "ZIP code not found."}), 404
    if not result.get("store"):
        return jsonify({"error": "No Trader Joe's store found for that location."}), 404
    return jsonify(result)


@app.route("/trader-joes-store", methods=["OPTIONS"])
def trader_joes_store_options():
    return ("", 204)


@app.get("/sale-ingredients")
def sale_ingredients():
    from store_catalogs import CatalogError
    from store_comparison_api import engine
    from store_home_sales import store_sale_pool
    store_id = request.args.get("store_id", "")
    if not store_id:
        return jsonify({"error": "Select a grocery store first."}), 400
    try:
        catalog = engine().registry.select([store_id])[0]
        pool = store_sale_pool(catalog, build_sale_ingredient_pool, sale_ingredient_pool)
        selected = weighted_sale_sample(pool)
        return jsonify({"store_id": store_id, "inventory_version": catalog.metadata.inventory_version,
            "candidate_pool_size": len(pool),
            "sale_ingredients": [public_sale_candidate(candidate) for candidate in selected],
            "source": catalog.metadata.store_name})
    except CatalogError:
        return jsonify({"error": "Selected store is unavailable."}), 400
    except Exception as exc:
        log_event("sale_ingredients_failed", request_id=request.snapp_request_id, error_type=type(exc).__name__)
        return jsonify({"error": "Sale ingredients are temporarily unavailable."}), 503


@app.route("/sale-ingredients", methods=["OPTIONS"])
def sale_ingredients_options():
    return ("", 204)


@app.post("/dishes")
def dishes():
    request_started = time.perf_counter()
    rid = request.snapp_request_id
    data, error = validated_json_payload()
    if error:
        return error
    sale_ingredient_id = ingredient_identity_key(data.get("sale_ingredient_id") or "")
    meal_prompt = (data.get("meal_prompt") or data.get("ingredients") or data.get("message") or "").strip()
    if sale_ingredient_id and not meal_prompt:
        meal_prompt = sale_ingredient_id
    if len(meal_prompt) > MAX_DISH_PROMPT_CHARS:
        return json_error("Meal prompt is too long.", 400)
    household_size = parse_household_size(data.get("household_size"))
    dietary_restrictions = re.sub(
        r"\s+", " ", (data.get("dietary_restrictions") or "").strip()
    )[:500]
    pantry_items = parse_pantry_items(data.get("pantry_items"))
    if len(pantry_items) > MAX_PANTRY_ITEMS_PER_REQUEST:
        return json_error("Too many pantry items in request.", 400)
    filters = parse_recipe_filters(data, household_size, dietary_restrictions)
    if not meal_prompt:
        return json_error("Describe the meal you want.", 400)

    try:
        metrics.increment("match_requests")
        stores = morton_williams_store_lookup()
        grocery_label = "Morton Williams"
        recipe_ideas = [{"name": meal_prompt, "query": meal_prompt, "cuisine": ""}]
        if sale_ingredient_id:
            filters["include_ingredients"] = list(dict.fromkeys([sale_ingredient_id] + filters["include_ingredients"]))
            dishes, used_relaxed_matches = build_sale_ingredient_recipe_results(
                sale_ingredient_id,
                filters,
                stores=stores,
                grocery_label=grocery_label,
                pantry_items=pantry_items,
            )
        else:
            dishes, used_relaxed_matches = build_real_recipe_results(
                meal_prompt,
                filters,
                products=None,
                stores=stores,
                recipe_ideas=recipe_ideas,
                grocery_label=grocery_label,
                pantry_items=pantry_items,
            )
        from recipe_chat_multilingual import locale_code
        if locale_code(data.get("locale", "en")) != "en":
            from concurrent.futures import ThreadPoolExecutor
            from recipe_chat_presentation import localize_detail
            def translate_dish(dish):
                detail = dict(dish.get("recipe") or {})
                detail.setdefault("name", dish.get("name", ""))
                dish["localized_recipe"] = localize_detail(
                    str(dish.get("recipe_id") or dish.get("name")), detail, data["locale"])
            with ThreadPoolExecutor(max_workers=3) as executor:
                list(executor.map(translate_dish, dishes))
        ingredient_count = sum(len(dish.get("recipe", {}).get("ingredients", [])) for dish in dishes)
        unmatched_count = sum(
            1
            for dish in dishes
            for ingredient in dish.get("ingredients_to_buy", [])
            if ingredient.get("availability_status") == "unavailable" or ingredient.get("unavailable")
        )
        low_confidence_count = sum(
            1
            for dish in dishes
            for ingredient in dish.get("ingredients_to_buy", [])
            if ingredient.get("match_confidence") in {"low", "no_safe_match", "substitution_only"}
        )
        elapsed_ms = round((time.perf_counter() - request_started) * 1000, 2)
        metrics.observe_latency("dishes", elapsed_ms)
        metrics.increment("dish_ingredient_lines", ingredient_count)
        metrics.increment("dish_unmatched_ingredients", unmatched_count)
        metrics.increment("dish_low_confidence_ingredients", low_confidence_count)
        log_event(
            "dishes_request_complete",
            request_id=rid,
            recipe_count=len(dishes),
            ingredient_line_count=ingredient_count,
            unmatched_count=unmatched_count,
            low_confidence_count=low_confidence_count,
            total_ms=elapsed_ms,
        )
        return jsonify(
            {
                "request_id": rid,
                "meal_prompt": meal_prompt,
                "sale_ingredient_id": sale_ingredient_id or None,
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
                "store_number": None,
                "pricing_source": "morton_williams",
                "pricing_unavailable": False,
                "source": "SNAPP all_recipes database selected from the user's Dishes request and matched against Morton Williams product data",
            }
        )
    except RuntimeError as exc:
        metrics.increment("dish_request_failures")
        log_event("dishes_request_failed", request_id=rid, error_type=type(exc).__name__)
        return jsonify({"error": str(exc), "request_id": rid}), 503
    except Exception as exc:
        metrics.increment("dish_request_failures")
        log_event("dishes_request_failed", request_id=rid, error_type=type(exc).__name__)
        return jsonify({"error": "Dish generation failed.", "details": str(exc), "request_id": rid}), 503


@app.route("/dishes", methods=["OPTIONS"])
def dishes_options():
    return ("", 204)


from store_comparison_api import register_store_comparison
register_store_comparison(app, validated_json_payload, json_error, should_use_semantic_recipe_matching)

apply_route_limits(app, security_limiter)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
