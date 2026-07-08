import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


APIFY_API_BASE_URL = os.getenv("APIFY_API_BASE_URL", "https://api.apify.com").rstrip("/")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_TRADER_JOES_ACTOR_ID = os.getenv(
    "APIFY_TRADER_JOES_ACTOR_ID", "merry_arctic~trader-joes-scraper"
)
APIFY_TRADER_JOES_STORE_NUMBER = os.getenv("APIFY_TRADER_JOES_STORE_NUMBER", "613")
APIFY_TRADER_JOES_CRAWL_URL = os.getenv("APIFY_TRADER_JOES_CRAWL_URL", "")
APIFY_TIMEOUT_SECONDS = int(os.getenv("APIFY_TIMEOUT_SECONDS", "360"))
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("data.json")
DEFAULT_MAX_PRODUCTS = int(os.getenv("APIFY_TRADER_JOES_MAX_PRODUCTS", "500"))
USER_AGENT = "SNAPP/1.0 (https://github.com/KittCoder/Snapp)"

RECIPE_INGREDIENT_ALIASES = {
    "beef": {"beef", "brisket", "steak", "ground beef", "short ribs"},
    "chicken": {"chicken", "chicken thighs", "chicken breast"},
    "fish": {"fish", "cod", "salmon", "tuna"},
    "pork": {"pork", "bacon", "ham", "sausage"},
    "shrimp": {"shrimp", "prawn", "prawns"},
    "tomato": {"tomato", "tomatoes", "canned tomatoes"},
    "pasta": {"pasta", "spaghetti", "penne", "noodles"},
    "rice": {"rice", "brown rice", "white rice"},
    "potato": {"potato", "potatoes"},
    "beans": {"beans", "black beans", "kidney beans"},
    "corn": {"corn", "frozen corn"},
    "broccoli": {"broccoli", "frozen broccoli"},
    "tortilla": {"tortilla", "tortillas"},
    "cheese": {"cheese", "cheddar", "mozzarella", "parmesan"},
    "eggs": {"egg", "eggs"},
    "milk": {"milk"},
    "yogurt": {"yogurt"},
    "banana": {"banana", "bananas"},
    "apple": {"apple", "apples"},
    "zucchini": {"zucchini"},
    "spinach": {"spinach"},
    "carrots": {"carrot", "carrots"},
}

FOOD_GROUP_CALORIES_PER_100G = {
    "protein": 165,
    "grains": 160,
    "dairy": 90,
    "vegetables": 45,
    "fruits": 60,
    "other": 120,
}


def normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def actor_api_id(actor_id):
    return actor_id.strip().replace("/", "~")


def first_present(record, keys):
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    lowered = {str(key).casefold(): value for key, value in record.items()}
    for key in keys:
        value = lowered.get(key.casefold())
        if value not in (None, ""):
            return value
    return None


def parse_price(value):
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, dict):
        for key in ("amount", "value", "price", "current", "regular"):
            parsed = parse_price(value.get(key))
            if parsed is not None:
                return parsed
    match = re.search(r"\d+(?:\.\d{1,2})?", str(value or "").replace(",", ""))
    return round(float(match.group(0)), 2) if match else None


def parse_package_size(value):
    patterns = (
        r"\b\d+\s*x\s*\d+(?:\.\d+)?\s*(?:oz|lb|g|kg|ct|count)\b",
        r"\b\d+(?:\.\d+)?\s*(?:fl oz|oz|lb|g|kg|ct|count|gal|ml|l)\b",
        r"\b\d+\s+each\b",
    )
    for pattern in patterns:
        matches = list(re.finditer(pattern, value or "", flags=re.I))
        if matches:
            return re.sub(r"\s+", " ", matches[-1].group(0)).strip()
    return None


def grams_for_amount(amount, unit):
    if unit == "kg":
        return amount * 1000
    if unit == "g":
        return amount
    if unit == "lb":
        return amount * 453.592
    if unit in {"oz", "fl oz"}:
        return amount * 28.3495
    if unit == "gal":
        return amount * 3785.41
    if unit == "l":
        return amount * 1000
    if unit == "ml":
        return amount
    return amount


def package_grams(package_size):
    if not package_size:
        return None
    text = package_size.casefold()
    compound = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(oz|lb|g|kg)", text)
    if compound:
        return round(
            float(compound.group(1))
            * grams_for_amount(float(compound.group(2)), compound.group(3))
        )
    match = re.search(r"(\d+(?:\.\d+)?)\s*(fl oz|oz|lb|g|kg|ct|count|each|gal|ml|l)\b", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2)
    if unit in {"ct", "count", "each"}:
        return round(amount * 50)
    return round(grams_for_amount(amount, unit))


def infer_food_group(name, tags=None):
    words = normalize_text(" ".join([name or "", " ".join(tags or [])]))
    if re.search(r"\b(chicken|beef|turkey|pork|bacon|fish|salmon|tuna|shrimp|egg|eggs|tofu|beans|lentils|sausage)\b", words):
        return "protein"
    if re.search(r"\b(rice|pasta|bread|tortilla|cereal|oats|mac|noodle|bagel|grain)\b", words):
        return "grains"
    if re.search(r"\b(yogurt|milk|cheese|cream|butter)\b", words):
        return "dairy"
    if re.search(r"\b(strawberr|banana|apple|lemon|orange|fruit|berry|berries)\b", words):
        return "fruits"
    if re.search(r"\b(zucchini|squash|broccoli|carrot|potato|tomato|lettuce|spinach|vegetable|pepper|onion)\b", words):
        return "vegetables"
    return "other"


def product_ingredient_from_name(name, tags=None):
    words = normalize_text(" ".join([name or "", " ".join(tags or [])]))
    for ingredient, aliases in RECIPE_INGREDIENT_ALIASES.items():
        if re.search(rf"\b{re.escape(normalize_text(ingredient))}\b", words):
            return ingredient
        if any(re.search(rf"\b{re.escape(normalize_text(alias))}\b", words) for alias in aliases):
            return ingredient
    stopwords = {
        "trader",
        "joe",
        "joes",
        "fresh",
        "premium",
        "original",
        "organic",
        "large",
        "small",
        "whole",
        "frozen",
        "package",
        "brand",
        "each",
    }
    product_words = [word for word in words.split() if word not in stopwords and not word.isdigit()]
    return " ".join(product_words[-2:] or product_words[:1])[:80] or (name or "")[:80]


def list_value(value):
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r",|\|", value) if part.strip()]
    return []


def fetch_apify_trader_joes_items(store_number, crawl_url=None):
    if not APIFY_API_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN is not set.")

    actor_id = actor_api_id(APIFY_TRADER_JOES_ACTOR_ID)
    query = urlencode({"timeout": min(APIFY_TIMEOUT_SECONDS, 300)})
    url = f"{APIFY_API_BASE_URL}/v2/acts/{actor_id}/run-sync-get-dataset-items?{query}"
    actor_input = {"store_number": str(store_number)}
    if crawl_url:
        actor_input["crawl_url"] = crawl_url

    request_object = Request(
        url,
        data=json.dumps(actor_input).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {APIFY_API_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(request_object, timeout=APIFY_TIMEOUT_SECONDS + 30) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Apify Trader Joe's scraper request failed: {exc}") from exc

    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    if not isinstance(data, list):
        raise RuntimeError("Apify Trader Joe's scraper returned an unexpected response.")
    return data


def normalize_apify_product(item, store_id, max_index):
    if not isinstance(item, dict):
        return None
    name = first_present(
        item,
        (
            "product_name",
            "productName",
            "name",
            "title",
            "item_name",
            "itemName",
        ),
    )
    if not name:
        return None
    name = re.sub(r"\s+", " ", str(name)).strip()[:140]

    sku = first_present(item, ("sku", "SKU", "product_sku", "productSku", "id"))
    url = first_present(item, ("product_url", "productUrl", "url", "link"))
    tags = list_value(first_present(item, ("tags", "keywords", "related_keywords", "relatedKeywords", "categories")))
    package_size = first_present(item, ("package_size", "packageSize", "size", "net_weight", "netWeight"))
    package_size = str(package_size).strip() if package_size else parse_package_size(name)
    current_price = parse_price(first_present(item, ("current_price", "currentPrice", "sale_price", "salePrice", "price")))
    original_price = parse_price(first_present(item, ("original_price", "originalPrice", "regular_price", "regularPrice", "list_price", "listPrice")))
    if current_price is None:
        return None
    if original_price is None:
        original_price = current_price
    sale_price = current_price if current_price < original_price else None
    food_group = infer_food_group(name, tags)
    stable_id = sku or url or f"{name}-{max_index}"
    product_id = hashlib.sha256(str(stable_id).encode("utf-8")).hexdigest()[:16]
    availability = str(first_present(item, ("availability", "stock", "status")) or "").casefold()
    explicit_in_stock = first_present(item, ("in_stock", "inStock", "available", "isAvailable"))
    if isinstance(explicit_in_stock, bool):
        in_stock = explicit_in_stock
    elif isinstance(explicit_in_stock, str):
        in_stock = explicit_in_stock.casefold() not in {"false", "no", "0", "out of stock"}
    else:
        in_stock = "out" not in availability

    return {
        "id": f"tj_{product_id}",
        "store_id": store_id,
        "ingredient": product_ingredient_from_name(name, tags),
        "product_name": name,
        "food_group": food_group,
        "package_size": package_size,
        "package_grams": package_grams(package_size),
        "price": round(original_price, 2),
        "sale_price": round(sale_price, 2) if sale_price is not None else None,
        "on_sale": sale_price is not None,
        "unit_price": parse_price(first_present(item, ("unit_price", "unitPrice"))),
        "unit": first_present(item, ("unit", "price_unit", "priceUnit")),
        "in_stock": in_stock,
        "snap_eligible": True,
        "snap_eligible_note": "Assumed for SNAPP matching; verify eligibility at checkout.",
        "calories_per_100g": FOOD_GROUP_CALORIES_PER_100G.get(food_group, FOOD_GROUP_CALORIES_PER_100G["other"]),
        "sku": str(sku) if sku else None,
        "tags": tags,
        "url": str(url) if url else None,
        "source": "Apify Trader Joe's Scraper",
    }


def normalize_apify_products(items, store_number, max_products=DEFAULT_MAX_PRODUCTS):
    store_id = f"trader_joes_{store_number}"
    products = []
    seen_ids = set()
    for index, item in enumerate(items):
        if len(products) >= max_products:
            break
        product = normalize_apify_product(item, store_id, index)
        if not product or product["id"] in seen_ids:
            continue
        products.append(product)
        seen_ids.add(product["id"])
    return products


def build_database(products, store_number, crawl_url=None):
    return {
        "metadata": {
            "source": "Apify Trader Joe's Scraper",
            "source_url": "https://apify.com/merry_arctic/trader-joes-scraper",
            "actor_id": actor_api_id(APIFY_TRADER_JOES_ACTOR_ID),
            "store_number": str(store_number),
            "crawl_url": crawl_url or None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "product_count": len(products),
            "notes": [
                "Run this scraper manually once or twice per week to refresh Trader Joe's pricing.",
                "sale_price is populated only when the Apify dataset exposes a regular price above the current price.",
                "snap_eligible is assumed for SNAPP matching and should be verified at checkout.",
            ],
        },
        "stores": [
            {
                "id": f"trader_joes_{store_number}",
                "name": f"Trader Joe's Store {store_number}",
                "website": "https://www.traderjoes.com/home",
                "accepts_snap": True,
            }
        ],
        "products": products,
    }


def write_database(database, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output_path.parent,
        delete=False,
    ) as file:
        json.dump(database, file, indent=2, sort_keys=True)
        file.write("\n")
        temp_name = file.name
    os.replace(temp_name, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Run the Apify Trader Joe's scraper and write pricing into data.json."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--store-number", default=APIFY_TRADER_JOES_STORE_NUMBER)
    parser.add_argument("--crawl-url", default=APIFY_TRADER_JOES_CRAWL_URL)
    parser.add_argument("--max-products", type=int, default=DEFAULT_MAX_PRODUCTS)
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Write an empty products list if no products are returned.",
    )
    args = parser.parse_args()

    try:
        raw_items = fetch_apify_trader_joes_items(args.store_number, args.crawl_url)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    products = normalize_apify_products(
        raw_items,
        args.store_number,
        max_products=max(1, args.max_products),
    )
    if not products and not args.allow_empty:
        raise SystemExit(
            f"Apify returned {len(raw_items)} items, but none could be normalized. "
            f"Existing {args.output} left unchanged."
        )

    database = build_database(products, args.store_number, args.crawl_url)
    write_database(database, args.output)
    sale_count = sum(1 for product in products if product.get("on_sale"))
    print(
        f"Wrote {len(products)} Trader Joe's products to {args.output} "
        f"({sale_count} on sale)."
    )


if __name__ == "__main__":
    main()
