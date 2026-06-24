
import os
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request
from openai import OpenAI

app = Flask(__name__)

SYSTEM_PROMPT = (
    "You are a helpful meal generating assistant who generates concise meal ideas initially, asks for feedback, iterates, then returns recipes upon confirmation of meals from user. "
)
MAX_TURNS = 6
conversation_history = []
ZIP_CODE_PATTERN = re.compile(r"^\d{5}$")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HTTP_TIMEOUT_SECONDS = 20
HTTP_RETRY_ATTEMPTS = 2
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"
STORE_CACHE_TTL_SECONDS = 15 * 60
FOOD_CACHE_TTL_SECONDS = 60 * 60
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

    return {
        key: round(value, 1) if value else 0
        for key, value in nutrients.items()
    }, nutrient_units


def choose_food_match(foods):
    preferred_types = ("Foundation", "SR Legacy", "Survey (FNDDS)")
    for preferred_type in preferred_types:
        for food in foods:
            if food.get("dataType") == preferred_type:
                return food
    return foods[0] if foods else None


def search_food_nutrition(ingredient):
    cached_result = food_search_cache.get(ingredient.casefold())
    now = time.time()
    if cached_result and now - cached_result["cached_at"] < FOOD_CACHE_TTL_SECONDS:
        return cached_result["food"]

    data = fetch_fooddata_json(
        f"{FDC_SEARCH_URL}?{urlencode({'api_key': FDC_API_KEY})}",
        {
            "query": ingredient,
            "pageSize": 8,
            "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
        },
    )
    food = choose_food_match(data.get("foods", []))
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


def make_dish_name(index, ingredients):
    names = [ingredient["ingredient"].title() for ingredient in ingredients]
    if len(names) == 1:
        base = names[0]
    elif len(names) == 2:
        base = f"{names[0]} and {names[1]}"
    else:
        base = f"{names[0]}, {names[1]}, and {names[2]}"

    dish_types = ("Skillet Bowl", "Sheet-Pan Plate", "Warm Grain Bowl")
    return f"{base} {dish_types[index]}"


def build_dishes(ingredients):
    dish_styles = (
        {
            "method": "Saute the main ingredients with garlic or onion, then serve over rice, pasta, or greens.",
            "servings": 2,
            "grams": (160, 140, 100, 80, 60, 50, 40, 30),
        },
        {
            "method": "Roast everything on one pan with a little oil, salt, and pepper until browned and tender.",
            "servings": 3,
            "grams": (180, 150, 120, 90, 70, 50, 40, 30),
        },
        {
            "method": "Combine the ingredients in a bowl with a simple sauce, herbs, and an optional cooked grain.",
            "servings": 4,
            "grams": (140, 120, 100, 80, 70, 55, 45, 35),
        },
    )
    dishes = []
    for index, style in enumerate(dish_styles):
        ingredient_lines = []
        total_calories = 0
        totals = {
            "protein_g": 0,
            "carbohydrates_g": 0,
            "fat_g": 0,
            "fiber_g": 0,
            "sugars_g": 0,
            "sodium_mg": 0,
        }
        for ingredient_index, ingredient in enumerate(ingredients):
            grams = style["grams"][ingredient_index]
            nutrients = ingredient["nutrients_per_100g"]
            multiplier = grams / 100
            calories = nutrients["calories"] * multiplier
            total_calories += calories
            for key in totals:
                totals[key] += nutrients[key] * multiplier
            ingredient_lines.append(
                {
                    "name": ingredient["ingredient"],
                    "matched_food": ingredient["description"],
                    "grams_total": grams,
                    "fdc_id": ingredient["fdc_id"],
                    "calories_total": round(calories),
                }
            )

        servings = style["servings"]
        dishes.append(
            {
                "name": make_dish_name(index, ingredients),
                "servings": servings,
                "calories_per_person": round(total_calories / servings),
                "nutrition_per_person": {
                    key: round(value / servings, 1) for key, value in totals.items()
                },
                "ingredients": ingredient_lines,
                "method": style["method"],
            }
        )
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


def find_grocery_stores(zip_code):
    cached_result = store_search_cache.get(zip_code)
    now = time.time()
    if cached_result and now - cached_result["cached_at"] < STORE_CACHE_TTL_SECONDS:
        return cached_result["location"], cached_result["stores"]

    location_params = urlencode(
        {
            "postalcode": zip_code,
            "country": "USA",
            "countrycodes": "us",
            "format": "jsonv2",
            "limit": 1,
        }
    )
    locations = fetch_json(
        f"{NOMINATIM_URL}?{location_params}",
        service_name="Nominatim",
    )
    if not locations:
        return None, []

    location = locations[0]
    try:
        south, north, west, east = location["boundingbox"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("The grocery store data service returned invalid location data.") from exc
    overpass_query = f"""
        [out:json][timeout:20];
        (
          nwr["shop"~"^(supermarket|grocery)$"]
             ["addr:postcode"~"^{zip_code}(-[0-9]{{4}})?$"]
             ({south},{west},{north},{east});
        );
        out center tags;
    """
    try:
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
    except RuntimeError:
        print("Overpass unavailable; using Nominatim store fallback.", flush=True)
        stores = find_stores_with_nominatim(zip_code, location["boundingbox"])

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
    raw_ingredients = (data.get("ingredients") or data.get("message") or "").strip()
    ingredients = parse_ingredients(raw_ingredients)
    if not ingredients:
        return jsonify({"error": "Enter at least one ingredient."}), 400

    matched_ingredients = []
    missing_ingredients = []
    try:
        for ingredient in ingredients:
            food = search_food_nutrition(ingredient)
            if food:
                matched_ingredients.append(food)
            else:
                missing_ingredients.append(ingredient)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if not matched_ingredients:
        return jsonify({"error": "No matching foods were found in FoodData Central."}), 404

    return jsonify(
        {
            "input_ingredients": ingredients,
            "matched_ingredients": matched_ingredients,
            "missing_ingredients": missing_ingredients,
            "dishes": build_dishes(matched_ingredients),
            "source": "U.S. Department of Agriculture, Agricultural Research Service. FoodData Central.",
        }
    )


@app.route("/dishes", methods=["OPTIONS"])
def dishes_options():
    return ("", 204)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
