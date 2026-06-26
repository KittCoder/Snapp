
import os
import json
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
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ZIPPOPOTAM_URL = "https://api.zippopotam.us/us"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HTTP_TIMEOUT_SECONDS = 20
HTTP_RETRY_ATTEMPTS = 2
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"
STORE_CACHE_TTL_SECONDS = 15 * 60
FOOD_CACHE_TTL_SECONDS = 60 * 60
DEMO_GROCERY_DB_FILENAME = "snapp_demo_grocery_db.json"
store_search_cache = {}
food_search_cache = {}
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


def generate_dish_candidates(ingredients, household_size):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    ingredient_text = ", ".join(ingredients)
    user_prompt = f"""
Available ingredients: {ingredient_text}
Household size: {household_size} people

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


def generate_demo_grocery_dish_candidates(meal_prompt, household_size, catalog):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    user_prompt = f"""
User meal request: {meal_prompt}
Household size: {household_size} people
Available grocery products JSON:
{json.dumps(catalog, separators=(",", ":"))}

Generate exactly 3 normal meal ideas that satisfy the user's request. Use only product IDs from the
available grocery products JSON. Optimize across:
- price: prefer sale prices, lower total package cost, and overlapping inexpensive staples
- taste: choose familiar, coherent meals people would actually want to eat
- health: include balanced food groups when possible and avoid meals that are only starch or only dairy

Rules:
- The user is describing the kind of meal they want, not listing pantry ingredients.
- Choose 3 to 6 grocery products per dish.
- Use product_id values exactly as provided.
- If the user requests a food that is unavailable in the catalog, choose the closest normal substitute
  available in the catalog and mention the substitution in portion_note.
- grams_total is the amount used by the whole household meal, not the full package unless needed.
- grams_total may be less than package_grams because the shopper buys the package and uses part of it.
- Keep portions realistic for {household_size} people.
- Return short notes only, with no recipes and no cooking steps.

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


def find_grocery_stores(zip_code):
    cached_result = store_search_cache.get(zip_code)
    now = time.time()
    if cached_result and now - cached_result["cached_at"] < STORE_CACHE_TTL_SECONDS:
        return cached_result["location"], cached_result["stores"]

    location = find_zip_location(zip_code)
    if not location:
        return None, []
    try:
        boundingbox = location["boundingbox"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("The grocery store data service returned invalid location data.") from exc

    try:
        stores = find_stores_with_overpass(zip_code, boundingbox, require_postcode=True)
        if not stores:
            stores = find_stores_with_overpass(zip_code, boundingbox, require_postcode=False)
    except RuntimeError:
        print("Overpass unavailable; using Nominatim store fallback.", flush=True)
        stores = find_stores_with_nominatim(zip_code, boundingbox)

    stores.sort(key=lambda store: store["name"].casefold())
    location_name = location.get("display_name", zip_code)
    stores = stores[:30]
    store_search_cache[zip_code] = {
        "cached_at": now,
        "location": location_name,
        "stores": stores,
    }
    return location_name, stores


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
    if not ZIP_CODE_PATTERN.fullmatch(zip_code):
        return jsonify({"error": "Enter a valid 5-digit US ZIP code."}), 400

    try:
        location, stores = find_grocery_stores(zip_code)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if location is None:
        return jsonify({"error": "ZIP code not found."}), 404

    return jsonify(
        {
            "zip_code": zip_code,
            "location": location,
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
    if not meal_prompt:
        return jsonify({"error": "Describe the meal you want."}), 400

    try:
        grocery_db = load_demo_grocery_db()
        stores = demo_store_lookup(grocery_db)
        products = available_demo_products(grocery_db)
        products_by_id = {
            product["id"]: product
            for product in products
            if product.get("id")
        }
        catalog = demo_catalog_for_prompt(products, stores)
        dish_candidates = generate_demo_grocery_dish_candidates(
            meal_prompt, household_size, catalog
        )
        dishes = build_demo_grocery_dishes(dish_candidates, products_by_id, stores)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": "Dish generation failed.", "details": str(exc)}), 503

    return jsonify(
        {
            "meal_prompt": meal_prompt,
            "household_size": household_size,
            "matched_ingredients": [
                ingredient
                for dish in dishes
                for ingredient in dish["ingredients"]
            ],
            "missing_ingredients": [],
            "dishes": dishes,
            "source": "SNAPP demo grocery database",
        }
    )


@app.route("/dishes", methods=["OPTIONS"])
def dishes_options():
    return ("", 204)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
