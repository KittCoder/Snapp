
import os
import json
import math
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
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
MEALDB_API_KEY = os.getenv("MEALDB_API_KEY", "1")
MEALDB_BASE_URL = os.getenv(
    "MEALDB_BASE_URL", f"https://www.themealdb.com/api/json/v1/{MEALDB_API_KEY}"
).rstrip("/")
HTTP_TIMEOUT_SECONDS = 20
HTTP_RETRY_ATTEMPTS = 2
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"
STORE_CACHE_TTL_SECONDS = 15 * 60
FOOD_CACHE_TTL_SECONDS = 60 * 60
DEMO_GROCERY_DB_FILENAME = "snapp_demo_grocery_db.json"
store_search_cache = {}
food_search_cache = {}
mealdb_search_cache = {}
mealdb_lookup_cache = {}
mealdb_area_cache = None
mealdb_area_meals_cache = {}
FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_API_KEY = os.getenv("FDC_API_KEY") or os.getenv("FOODDATA_CENTRAL_API_KEY") or "DEMO_KEY"
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
MEALDB_SEARCH_STOPWORDS = {
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
MEALDB_INGREDIENT_ALIASES = {
    "chicken": {"chicken thighs"},
    "chicken breast": {"chicken thighs"},
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
MEALDB_AREA_ALIASES = {
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
MEALDB_DIVERSE_AREA_ORDER = (
    "Mexican",
    "Italian",
    "Indian",
    "Chinese",
    "Japanese",
    "Thai",
    "Moroccan",
    "Greek",
    "Spanish",
    "Vietnamese",
    "Jamaican",
    "Turkish",
    "Canadian",
    "United States",
    "British",
    "French",
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
    "https://snapp-1d5j.vercel.app"
)
VERCEL_DEPLOYMENT_ORIGIN_PATTERN = re.compile(
    r"^https://snapp-1d5j-[a-z0-9-]+\.vercel\.app$"
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


def fetch_mealdb_json(path, params=None):
    query = f"?{urlencode(params)}" if params else ""
    url = f"{MEALDB_BASE_URL}/{path}{query}"
    try:
        return fetch_json(url, service_name="TheMealDB")
    except RuntimeError as exc:
        raise RuntimeError("TheMealDB recipe service is unavailable.") from exc


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
        Path(__file__).with_name(DEMO_GROCERY_DB_FILENAME),
        Path(__file__).resolve().parent.parent / DEMO_GROCERY_DB_FILENAME,
    )
    for path in search_paths:
        if path.exists():
            with path.open(encoding="utf-8") as file:
                return json.load(file)
    raise RuntimeError("The SNAPP demo grocery database is missing.")


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


def mealdb_ingredients(meal):
    ingredients = []
    for index in range(1, 21):
        ingredient = re.sub(r"\s+", " ", meal.get(f"strIngredient{index}") or "").strip()
        measure = re.sub(r"\s+", " ", meal.get(f"strMeasure{index}") or "").strip()
        if not ingredient:
            continue
        ingredients.append(
            {
                "name": ingredient,
                "measure": measure,
                "display": f"{measure} {ingredient}".strip(),
            }
        )
    return ingredients


def mealdb_text_for_restrictions(meal):
    return " ".join(
        [
            meal.get("strMeal") or "",
            meal.get("strCategory") or "",
            meal.get("strArea") or "",
            " ".join(ingredient["display"] for ingredient in mealdb_ingredients(meal)),
        ]
    )


def mealdb_respects_restrictions(meal, dietary_restrictions):
    if not dietary_restrictions:
        return True
    meal_text = mealdb_text_for_restrictions(meal)
    return not any(
        restriction_pattern.search(dietary_restrictions)
        and ingredient_pattern.search(meal_text)
        for restriction_pattern, ingredient_pattern in RESTRICTION_RULES
    )


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


def list_mealdb_areas():
    global mealdb_area_cache
    if mealdb_area_cache is not None:
        return mealdb_area_cache

    data = fetch_mealdb_json("list.php", {"a": "list"})
    mealdb_area_cache = [
        area.get("strArea")
        for area in data.get("meals") or []
        if area.get("strArea")
    ]
    return mealdb_area_cache


def filter_mealdb_meals_by_area(area):
    if not area:
        return []
    cached = mealdb_area_meals_cache.get(area)
    if cached is not None:
        return cached

    data = fetch_mealdb_json("filter.php", {"a": area})
    meals = data.get("meals") or []
    mealdb_area_meals_cache[area] = meals
    return meals


def fetch_random_mealdb_meal(dietary_restrictions, used_ids):
    for _ in range(18):
        data = fetch_mealdb_json("random.php")
        meals = data.get("meals") or []
        if not meals:
            continue
        meal = meals[0]
        meal_id = meal.get("idMeal")
        if (
            meal_id
            and meal_id not in used_ids
            and mealdb_ingredients(meal)
            and mealdb_respects_restrictions(meal, dietary_restrictions)
        ):
            return meal
    return None


def mealdb_prompt_terms(meal_prompt):
    prompt = re.sub(r"[^a-zA-Z0-9\s]", " ", meal_prompt or "")
    words = [
        word.casefold()
        for word in prompt.split()
        if len(word) > 2 and word.casefold() not in MEALDB_SEARCH_STOPWORDS
    ]
    terms = [meal_prompt]
    terms.extend(words[:5])
    return list(dict.fromkeys(term.strip() for term in terms if term and term.strip()))


def normalize_cuisine_text(value):
    return re.sub(r"[^a-z0-9]+", " ", value or "").strip().casefold()


def detect_requested_mealdb_area(meal_prompt):
    prompt_text = f" {normalize_cuisine_text(meal_prompt)} "
    for alias, area in sorted(
        MEALDB_AREA_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if re.search(rf"\b{re.escape(alias)}\b", prompt_text):
            return area

    for area in list_mealdb_areas():
        normalized_area = normalize_cuisine_text(area)
        if re.search(rf"\b{re.escape(normalized_area)}\b", prompt_text):
            return area
    return None


def mealdb_prompt_score(meal, meal_prompt):
    meal_words = normalized_food_words(meal.get("strMeal"))
    prompt_words = {
        word
        for word in normalized_food_words(meal_prompt)
        if word not in MEALDB_SEARCH_STOPWORDS
    }
    return len(meal_words & prompt_words)


def mealdb_candidates_for_prompt(meal_prompt):
    candidates = []
    seen_ids = set()
    for term in mealdb_prompt_terms(meal_prompt):
        for meal in search_mealdb_meals(term):
            meal_id = meal.get("idMeal")
            if meal_id and meal_id not in seen_ids:
                candidates.append(meal)
                seen_ids.add(meal_id)
    return candidates


def mealdb_candidates_for_area(area, meal_prompt):
    candidates = []
    for summary in filter_mealdb_meals_by_area(area):
        meal = lookup_mealdb_meal(summary.get("idMeal"))
        if meal:
            candidates.append(meal)
    return sorted(
        candidates,
        key=lambda meal: mealdb_prompt_score(meal, meal_prompt),
        reverse=True,
    )


def mealdb_diverse_area_candidates(meal_prompt, already_seen_ids):
    candidates = []
    for area in MEALDB_DIVERSE_AREA_ORDER:
        best_meal = None
        best_score = -1
        for summary in filter_mealdb_meals_by_area(area):
            meal_id = summary.get("idMeal")
            if not meal_id or meal_id in already_seen_ids:
                continue
            meal = lookup_mealdb_meal(meal_id)
            if not meal:
                continue
            score = mealdb_prompt_score(meal, meal_prompt)
            if score > best_score:
                best_meal = meal
                best_score = score
        if best_meal:
            candidates.append(best_meal)
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
    product_terms.update(MEALDB_INGREDIENT_ALIASES.get(product_ingredient.casefold(), set()))

    recipe_text = recipe_ingredient.casefold()
    recipe_terms = {recipe_text}
    recipe_terms.update(MEALDB_INGREDIENT_ALIASES.get(recipe_text, set()))

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


def match_recipe_ingredients_to_products(meal, products):
    matches = []
    used_product_ids = set()
    for ingredient in mealdb_ingredients(meal):
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


def mealdb_meal_to_demo_dish(meal, matched_products, stores, household_size):
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

    recipe = mealdb_recipe_from_meal(meal)
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
        "portion_note": f"Recipe from TheMealDB. Grocery matches are from the SNAPP demo grocery database.",
        "method": recipe["instructions"],
        "recipe": recipe,
        "mealdb_id": recipe["id"],
        "mealdb_source": recipe["source"],
    }


def build_mealdb_demo_grocery_dishes(
    meal_prompt, household_size, dietary_restrictions, products, stores
):
    dishes = []
    used_ids = set()
    used_areas = set()
    used_recipe_names = set()
    requested_area = detect_requested_mealdb_area(meal_prompt)

    def try_add_meal(meal, minimum_matches, require_new_area=False):
        meal_id = meal.get("idMeal")
        meal_area = meal.get("strArea") or ""
        recipe_name = normalized_recipe_name(meal.get("strMeal"))
        if not meal_id or meal_id in used_ids:
            return False
        if recipe_name in used_recipe_names:
            return False
        if requested_area and meal_area != requested_area:
            return False
        if require_new_area and meal_area in used_areas:
            return False
        if not mealdb_ingredients(meal):
            return False
        if not mealdb_respects_restrictions(meal, dietary_restrictions):
            return False
        matches = match_recipe_ingredients_to_products(meal, products)
        if len(matches) < minimum_matches:
            return False
        dishes.append(mealdb_meal_to_demo_dish(meal, matches, stores, household_size))
        used_ids.add(meal_id)
        used_recipe_names.add(recipe_name)
        if meal_area:
            used_areas.add(meal_area)
        return True

    candidates = (
        mealdb_candidates_for_area(requested_area, meal_prompt)
        if requested_area
        else mealdb_candidates_for_prompt(meal_prompt)
    )

    candidate_passes = (
        [(2, False), (1, False), (0, False)]
        if requested_area
        else [(2, True), (1, True), (0, True)]
    )
    for minimum_matches, require_new_area in candidate_passes:
        for meal in candidates:
            if len(dishes) == 3:
                return dishes
            try_add_meal(meal, minimum_matches, require_new_area)

    if requested_area:
        if len(dishes) != 3:
            raise RuntimeError(
                f"TheMealDB could not provide 3 {requested_area} recipe-backed dishes."
            )
        return dishes

    diverse_candidates = mealdb_diverse_area_candidates(meal_prompt, used_ids)
    for minimum_matches in (2, 1, 0):
        for meal in diverse_candidates:
            if len(dishes) == 3:
                return dishes
            try_add_meal(meal, minimum_matches, True)

    for minimum_matches, require_new_area in (
        (2, True),
        (1, True),
        (0, True),
    ):
        for _ in range(36):
            if len(dishes) == 3:
                return dishes
            meal = fetch_random_mealdb_meal(dietary_restrictions, used_ids)
            if meal:
                try_add_meal(meal, minimum_matches, require_new_area)

    if len(dishes) != 3:
        raise RuntimeError("TheMealDB could not provide 3 recipe-backed dishes.")
    return dishes


def mealdb_recipe_from_meal(meal):
    instructions = re.sub(r"\s+", " ", meal.get("strInstructions") or "").strip()
    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "instructions": instructions,
        "ingredients": mealdb_ingredients(meal),
        "thumbnail": meal.get("strMealThumb"),
        "youtube": meal.get("strYoutube"),
        "source": meal.get("strSource") or f"https://www.themealdb.com/meal/{meal.get('idMeal')}",
    }


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


def find_zip_location(zip_code):
    location_params = urlencode(
        {
            "postalcode": zip_code,
            "country": "USA",
            "countrycodes": "us",
            "format": "jsonv2",
            "limit": 1,
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


@app.post("/dishes")
def dishes():
    data = request.get_json(silent=True) or {}
    meal_prompt = (data.get("meal_prompt") or data.get("ingredients") or data.get("message") or "").strip()
    household_size = parse_household_size(data.get("household_size"))
    dietary_restrictions = re.sub(
        r"\s+", " ", (data.get("dietary_restrictions") or "").strip()
    )[:500]
    pantry_items = parse_pantry_items(data.get("pantry_items"))
    if not meal_prompt:
        return jsonify({"error": "Describe the meal you want."}), 400

    try:
        grocery_db = load_demo_grocery_db()
        stores = demo_store_lookup(grocery_db)
        products = available_demo_products(grocery_db)
        dishes = build_mealdb_demo_grocery_dishes(
            meal_prompt, household_size, dietary_restrictions, products, stores
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
            "matched_ingredients": [
                ingredient
                for dish in dishes
                for ingredient in dish["ingredients"]
            ],
            "missing_ingredients": [],
            "dishes": dishes,
            "source": "SNAPP demo grocery database and TheMealDB",
        }
    )


@app.route("/dishes", methods=["OPTIONS"])
def dishes_options():
    return ("", 204)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
