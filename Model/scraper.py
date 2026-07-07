import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen


MORTON_WILLIAMS_BASE_URL = "https://shop.mortonwilliams.com"
MORTON_WILLIAMS_STOREFRONT_URL = (
    "https://shop.mortonwilliams.com/store/morton-williams-supermarket/storefront"
)
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("data.json")
DEFAULT_MAX_PAGES = 8
DEFAULT_MAX_PRODUCTS = 250
HTTP_TIMEOUT_SECONDS = 20
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

robots_cache = {}


class ProductLinkParser(HTMLParser):
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


def normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


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


def parse_links(html, base_url=MORTON_WILLIAMS_BASE_URL):
    parser = ProductLinkParser(base_url)
    parser.feed(html)
    return parser.links


def morton_williams_page_urls(max_pages=DEFAULT_MAX_PAGES):
    if not robots_allows(MORTON_WILLIAMS_STOREFRONT_URL):
        return []
    html = fetch_text(MORTON_WILLIAMS_STOREFRONT_URL, service_name="Morton Williams storefront")
    if not html:
        return []
    urls = [MORTON_WILLIAMS_STOREFRONT_URL]
    seen = set(urls)
    for link in parse_links(html):
        url = link["url"].split("#", 1)[0]
        parsed = urlparse(url)
        if parsed.netloc != urlparse(MORTON_WILLIAMS_BASE_URL).netloc:
            continue
        if not re.search(r"/(collections|categories|departments)/", parsed.path):
            continue
        if url not in seen:
            urls.append(url)
            seen.add(url)
        if len(urls) >= max_pages:
            break
    return urls


def clean_product_text(value):
    text = re.sub(r"\s+", " ", value or "").strip()
    text = re.sub(r"\$\s+(\d+)\s+(\d{2})", r"$\1.\2", text)
    text = re.sub(r"\bSp onsored\b", " ", text, flags=re.I)
    text = re.sub(r"\bSee eligible items\b", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def strip_leading_price_tokens(value):
    text = value.strip()
    token = r"(?:each|lb|oz|ct|\(est\.\)|estimated|\(estimated\))"
    text = re.sub(rf"^(?:{token})+\s*", "", text, flags=re.I)
    text = re.sub(rf"^\$\d+(?:\.\d{{2}})?(?:\s+{token})*\s*", "", text, flags=re.I)
    text = re.sub(rf"^(?:{token})+\s*", "", text, flags=re.I)
    text = re.sub(r"^Spend\s+\$\d+(?:\.\d{2})?,\s*save\s+\$\d+(?:\.\d{2})?\s*", "", text, flags=re.I)
    return text.strip()


def parse_package_size(value):
    patterns = (
        r"\b\d+\s*x\s*\d+(?:\.\d+)?\s*(?:oz|lb|g|kg|ct|count)\b",
        r"\b\d+(?:\.\d+)?\s*(?:fl oz|oz|lb|g|kg|ct|count|gal|ml|l)\b",
        r"\bPackage\s+\d+(?:\.\d+)?\s*(?:oz|lb|g|kg|ct|count)\b",
        r"\bAbout\s+\d+(?:\.\d+)?\s*lb\s+each\b",
        r"\b\d+\s+each\b",
    )
    matches = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, value, flags=re.I))
    if not matches:
        return None
    match = sorted(matches, key=lambda item: item.start())[-1]
    return re.sub(r"\s+", " ", match.group(0)).strip()


def package_grams(package_size):
    if not package_size:
        return None
    text = package_size.casefold()
    compound = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(oz|lb|g|kg)", text)
    if compound:
        count = float(compound.group(1))
        amount = float(compound.group(2))
        unit = compound.group(3)
        return round(count * grams_for_amount(amount, unit))
    about_lb = re.search(r"about\s+(\d+(?:\.\d+)?)\s*lb", text)
    if about_lb:
        return round(float(about_lb.group(1)) * 453.592)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(fl oz|oz|lb|g|kg|ct|count|each|gal|ml|l)\b", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2)
    if unit in {"ct", "count", "each"}:
        return round(amount * 50)
    return round(grams_for_amount(amount, unit))


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


def clean_product_name(value, size):
    text = value
    text = re.sub(r"^\$\d+(?:\.\d{2})?\s*", " ", text)
    text = re.sub(r"\bMany in stock\b", " ", text, flags=re.I)
    text = re.sub(r"\bOriginal Price:.*$", " ", text, flags=re.I)
    text = re.sub(r"\$\d+(?:\.\d{2})?\s*/\s*(?:lb|oz|ct|each)\b", " ", text, flags=re.I)
    text = re.sub(r"\bAbout\s+\d+(?:\.\d+)?\s*lb\s+each\b", " ", text, flags=re.I)
    text = re.sub(r"\bSpend\s+\$\d+(?:\.\d{2})?,\s*save\s+\$\d+(?:\.\d{2})?\b", " ", text, flags=re.I)
    text = re.sub(r"\b(Fat free|Gluten free|Whole grain|Organic|Zero trans fat)\b", " ", text, flags=re.I)
    if size:
        text = re.sub(re.escape(size), " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,-")
    return text[:140]


def infer_food_group(name):
    words = normalize_text(name)
    if re.search(r"\b(chicken|beef|turkey|pork|bacon|fish|salmon|tuna|shrimp|egg|eggs|tofu|beans|lentils|hot dog|franks)\b", words):
        return "protein"
    if re.search(r"\b(rice|pasta|bread|tortilla|cereal|oats|mac|noodle|bagel)\b", words):
        return "grains"
    if re.search(r"\b(yogurt|milk|cheese|cream)\b", words):
        return "dairy"
    if re.search(r"\b(strawberr|banana|apple|lemon|orange|fruit)\b", words):
        return "fruits"
    if re.search(r"\b(zucchini|squash|broccoli|carrot|potato|tomato|lettuce|spinach|vegetable)\b", words):
        return "vegetables"
    return "other"


def product_ingredient_from_name(name):
    words = normalize_text(name)
    for ingredient, aliases in RECIPE_INGREDIENT_ALIASES.items():
        if re.search(rf"\b{re.escape(normalize_text(ingredient))}\b", words):
            return ingredient
        if any(re.search(rf"\b{re.escape(normalize_text(alias))}\b", words) for alias in aliases):
            return ingredient
    stopwords = {
        "fresh",
        "premium",
        "original",
        "organic",
        "large",
        "small",
        "whole",
        "frozen",
        "package",
        "kitchen",
        "brand",
    }
    product_words = [word for word in words.split() if word not in stopwords]
    return " ".join(product_words[-2:] or product_words[:1])[:80] or name[:80]


def parse_product(link):
    text = clean_product_text(link.get("text"))
    if "Current price:" not in text:
        return None
    current_match = re.search(r"Current price:\s*\$(\d+(?:\.\d{2})?)", text, re.I)
    if not current_match:
        return None
    original_match = re.search(r"Original Price:\s*\$(\d+(?:\.\d{2})?)", text, re.I)
    product_text = text[original_match.end():] if original_match else text[current_match.end():]
    product_text = strip_leading_price_tokens(product_text)
    size = parse_package_size(product_text)
    name = clean_product_name(product_text, size)
    if not name or len(name) < 2:
        return None
    unit_price_match = re.search(r"\$(\d+(?:\.\d{2})?)\s*/\s*(lb|oz|ct|each)\b", product_text, re.I)
    current_price = float(current_match.group(1))
    original_price = float(original_match.group(1)) if original_match else current_price
    food_group = infer_food_group(name)
    product_id = hashlib.sha256(link["url"].encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"mw_{product_id}",
        "store_id": "morton_williams_online",
        "ingredient": product_ingredient_from_name(name),
        "product_name": name,
        "food_group": food_group,
        "package_size": size,
        "package_grams": package_grams(size),
        "price": round(original_price, 2),
        "sale_price": round(current_price, 2) if original_match and current_price < original_price else None,
        "on_sale": bool(original_match and current_price < original_price),
        "unit_price": float(unit_price_match.group(1)) if unit_price_match else None,
        "unit": unit_price_match.group(2).casefold() if unit_price_match else None,
        "in_stock": bool(re.search(r"\bMany in stock\b", text, re.I)),
        "snap_eligible": True,
        "snap_eligible_note": "Assumed for SNAPP matching; verify eligibility at checkout.",
        "calories_per_100g": FOOD_GROUP_CALORIES_PER_100G.get(food_group, FOOD_GROUP_CALORIES_PER_100G["other"]),
        "url": link["url"],
        "source": "Morton Williams public online storefront",
    }


def scrape_products(max_pages=DEFAULT_MAX_PAGES, max_products=DEFAULT_MAX_PRODUCTS):
    products = []
    seen_ids = set()
    for url in morton_williams_page_urls(max_pages=max_pages):
        if len(products) >= max_products:
            break
        if not robots_allows(url):
            continue
        html = fetch_text(url, service_name="Morton Williams products")
        if not html:
            continue
        for link in parse_links(html):
            if len(products) >= max_products:
                break
            product = parse_product(link)
            if not product or product["id"] in seen_ids:
                continue
            products.append(product)
            seen_ids.add(product["id"])
    return products


def build_database(products):
    return {
        "metadata": {
            "source": "Morton Williams public online storefront",
            "source_url": MORTON_WILLIAMS_STOREFRONT_URL,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "product_count": len(products),
            "notes": [
                "Run this scraper manually once or twice per week to refresh pricing.",
                "sale_price is populated when the storefront exposes an original price higher than current price.",
                "snap_eligible is assumed for SNAPP matching and should be verified at checkout.",
            ],
        },
        "stores": [
            {
                "id": "morton_williams_online",
                "name": "Morton Williams Supermarket",
                "website": MORTON_WILLIAMS_STOREFRONT_URL,
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
        description="Scrape Morton Williams public storefront pricing into data.json."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--max-products", type=int, default=DEFAULT_MAX_PRODUCTS)
    args = parser.parse_args()

    products = scrape_products(
        max_pages=max(1, args.max_pages),
        max_products=max(1, args.max_products),
    )
    database = build_database(products)
    write_database(database, args.output)
    sale_count = sum(1 for product in products if product.get("on_sale"))
    print(
        f"Wrote {len(products)} Morton Williams products to {args.output} "
        f"({sale_count} on sale)."
    )


if __name__ == "__main__":
    main()
