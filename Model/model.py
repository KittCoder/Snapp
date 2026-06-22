
import os
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI

app = Flask(__name__, static_folder="../Web", static_url_path="")

SYSTEM_PROMPT = (
    "You are a helpful meal generating assistant who generates concise meal ideas initially, asks for feedback, iterates, then returns recipes upon confirmation of meals from user. "
)
MAX_TURNS = 6
conversation_history = []
ZIP_CODE_PATTERN = re.compile(r"^\d{5}$")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HTTP_TIMEOUT_SECONDS = 12
USER_AGENT = "SNAPP-grocery-finder/1.0"


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
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


def fetch_json(url, data=None):
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urlencode(data).encode("utf-8")

    request_object = Request(url, data=data, headers=headers)
    try:
        with urlopen(request_object, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("The grocery store data service is unavailable.") from exc


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


def find_grocery_stores(zip_code):
    location_params = urlencode(
        {
            "postalcode": zip_code,
            "country": "USA",
            "countrycodes": "us",
            "format": "jsonv2",
            "limit": 1,
        }
    )
    locations = fetch_json(f"{NOMINATIM_URL}?{location_params}")
    if not locations:
        return None, []

    location = locations[0]
    try:
        south, north, west, east = location["boundingbox"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("The grocery store data service returned invalid location data.") from exc
    overpass_query = f"""
        [out:json][timeout:10];
        (
          nwr["shop"~"^(supermarket|grocery)$"]
             ["addr:postcode"~"^{zip_code}(-[0-9]{{4}})?$"]
             ({south},{west},{north},{east});
        );
        out center tags;
    """
    store_data = fetch_json(OVERPASS_URL, {"data": overpass_query})

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

    stores.sort(key=lambda store: store["name"].casefold())
    return location.get("display_name", zip_code), stores[:30]


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "main.html")


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


if __name__ == "__main__":
    app.run(debug=False)
