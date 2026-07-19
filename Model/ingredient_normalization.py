from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from typing import Any


FEATURE_EXTRACTION_VERSION = "ingredient-foundation-v1"

VALID_PRODUCT = "valid_grocery_product"
PROBABLE_PRODUCT = "probably_valid_grocery_product"
SCRAPER_NOISE = "scraper_navigation_description_noise"
MALFORMED_RECORD = "malformed_record"

UNICODE_FRACTIONS = {
    "\u00bc": "1/4",
    "\u00bd": "1/2",
    "\u00be": "3/4",
    "\u2150": "1/7",
    "\u2151": "1/9",
    "\u2152": "1/10",
    "\u2153": "1/3",
    "\u2154": "2/3",
    "\u2155": "1/5",
    "\u2156": "2/5",
    "\u2157": "3/5",
    "\u2158": "4/5",
    "\u2159": "1/6",
    "\u215a": "5/6",
    "\u215b": "1/8",
    "\u215c": "3/8",
    "\u215d": "5/8",
    "\u215e": "7/8",
}

UNIT_ALIASES = {
    "c": "cup",
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tablespoon",
    "tbs": "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "tsp": "teaspoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "lb": "pound",
    "lbs": "pound",
    "pound": "pound",
    "pounds": "pound",
    "oz": "ounce",
    "ounce": "ounce",
    "ounces": "ounce",
    "fl oz": "fluid ounce",
    "fluid ounce": "fluid ounce",
    "fluid ounces": "fluid ounce",
    "pint": "pint",
    "pints": "pint",
    "pt": "pint",
    "quart": "quart",
    "quarts": "quart",
    "qt": "quart",
    "gallon": "gallon",
    "gallons": "gallon",
    "gal": "gallon",
    "g": "gram",
    "gram": "gram",
    "grams": "gram",
    "kg": "kilogram",
    "kilogram": "kilogram",
    "kilograms": "kilogram",
    "ml": "milliliter",
    "milliliter": "milliliter",
    "milliliters": "milliliter",
    "l": "liter",
    "liter": "liter",
    "liters": "liter",
    "pinch": "pinch",
    "pinches": "pinch",
    "clove": "clove",
    "cloves": "clove",
    "stick": "stick",
    "sticks": "stick",
    "egg": "egg",
    "eggs": "egg",
    "onion": "onion",
    "onions": "onion",
    "lemon": "lemon",
    "lemons": "lemon",
    "avocado": "avocado",
    "avocados": "avocado",
    "stalk": "stalk",
    "stalks": "stalk",
    "bunch": "bunch",
    "bunches": "bunch",
    "package": "package",
    "packages": "package",
    "pkg": "package",
    "can": "can",
    "cans": "can",
    "jar": "jar",
    "jars": "jar",
    "each": "each",
    "ct": "count",
    "count": "count",
    "pack": "pack",
    "ea": "each",
    "per pound": "pound",
}

ALIAS_TO_CANONICAL = {
    "a p flour": "all-purpose flour",
    "ap flour": "all-purpose flour",
    "all purpose flour": "all-purpose flour",
    "plain flour": "all-purpose flour",
    "cornflour": "corn starch",
    "corn flour": "corn starch",
    "cornstarch": "corn starch",
    "tinned pineapple": "pineapple",
    "double cream": "heavy cream",
    "confectioner sugar": "powdered sugar",
    "confectioners sugar": "powdered sugar",
    "icing sugar": "powdered sugar",
    "scallion": "green onions",
    "scallions": "green onions",
    "spring onions": "green onions",
    "almondmilk": "almond milk",
    "oatmilk": "oat milk",
}

MISSPELLINGS = {
    "mozarella": "mozzarella",
    "parmesan": "parmesan",
    "confectioner's": "confectioners",
    "confectioners'": "confectioners",
}

MEANINGFUL_MODIFIERS = {
    "fat_level": [
        "reduced-fat",
        "low-fat",
        "fat-free",
        "non-fat",
        "nonfat",
        "2 percent",
        "1 percent",
        "whole",
        "light",
        "heavy",
    ],
    "salted_status": ["no-salt-added", "reduced-sodium", "unsalted", "salted"],
    "sweetened_status": ["unsweetened", "sweetened"],
    "freshness": ["fresh", "frozen", "dried", "canned"],
    "form": [
        "extra virgin",
        "powdered",
        "ground",
        "shredded",
        "crushed",
        "paste",
        "sliced",
        "whole",
    ],
    "bone_status": ["boneless", "bone-in"],
    "skin_status": ["skinless", "skin-on"],
}

DIETARY_ATTRIBUTES = [
    "gluten-free",
    "nut-free",
    "lactose-free",
    "dairy-free",
    "vegan",
    "vegetarian",
    "organic",
]

PREPARATION_TERMS = [
    "for garnish",
    "for dredging",
    "for browning",
    "per person",
    "room temperature",
    "roughly chopped",
    "finely chopped",
    "chopped",
    "diced",
    "minced",
    "divided",
    "melted",
    "softened",
    "rinsed",
    "drained",
]

IDENTITY_PHRASES = {
    "ground beef",
    "crushed tomatoes",
    "tomato paste",
    "powdered sugar",
    "baking powder",
    "all-purpose flour",
}

COUNT_UNIT_INGREDIENTS = {
    "onion",
    "egg",
    "lemon",
    "avocado",
    "carrot",
    "potato",
    "cabbage",
    "celery",
    "pepper",
    "tomato",
}

COUNT_DESCRIPTOR_WORDS = {
    "small",
    "medium",
    "large",
}

COUNT_CONTAINER_UNITS = {
    "head": "head",
    "heads": "head",
    "stalk": "stalk",
    "stalks": "stalk",
}

COUNT_INGREDIENT_UNITS = {
    "carrot": "carrots",
    "carrots": "carrots",
    "onion": "onions",
    "onions": "onions",
    "potato": "potatoes",
    "potatoes": "potatoes",
    "cabbage": "cabbage",
    "celery": "celery",
    "pepper": "peppers",
    "peppers": "peppers",
    "tomato": "tomatoes",
    "tomatoes": "tomatoes",
    "garlic": "garlic",
}

COMMON_PRODUCE_CANONICALS = (
    "arugula",
    "asparagus",
    "avocado",
    "beets",
    "broccoli",
    "cabbage",
    "carrots",
    "cauliflower",
    "celery",
    "cucumber",
    "eggplant",
    "garlic",
    "kale",
    "leeks",
    "lettuce",
    "mushrooms",
    "onions",
    "potatoes",
    "radishes",
    "shallots",
    "spinach",
    "squash",
    "zucchini",
)

CANONICAL_PATTERNS = (
    (r"\ball[-\s]?purpose flour\b|\bplain flour\b|\bap flour\b", "all-purpose flour"),
    (r"\bwhole wheat flour\b", "whole wheat flour"),
    (r"\bbread flour\b", "bread flour"),
    (r"\bcake flour\b", "cake flour"),
    (r"\bflour\b", "flour"),
    (r"\balmond flour\b", "almond flour"),
    (r"\bcoconut flour\b", "coconut flour"),
    (r"\bbaking powder\b", "baking powder"),
    (r"\bbaking soda\b", "baking soda"),
    (r"^soda$|\bbicarbonate of soda\b", "baking soda"),
    (r"\bcurry powder\b", "curry powder"),
    (r"\bchili powder\b", "chili powder"),
    (r"\bpaprika\b", "paprika"),
    (r"\bcumin\b", "cumin"),
    (r"\bcinnamon\b", "cinnamon"),
    (r"\bnutmeg\b", "nutmeg"),
    (r"\ballspice\b", "allspice"),
    (r"\bsage\b", "sage"),
    (r"\bwalnuts?\b", "walnuts"),
    (r"\bpecans?\b|\bpecan meats?\b", "pecans"),
    (r"\balmonds?\b", "almonds"),
    (r"\bolives?\b|\bkalamata\b", "olives"),
    (r"\bvanilla extract\b|\bvanilla\b", "vanilla extract"),
    (r"\blemon extract\b", "lemon extract"),
    (r"\balmond extract\b", "almond extract"),
    (r"\bcream of tartar\b", "cream of tartar"),
    (r"\bmolasses\b", "molasses"),
    (r"\bcorn syrup\b", "corn syrup"),
    (r"\bgelatin\b", "gelatin"),
    (r"\bbreadcrumbs?\b|\bbread crumbs?\b", "breadcrumbs"),
    (r"\bcocoa\b", "cocoa"),
    (r"\blemon juice\b", "lemon juice"),
    (r"\blime juice\b", "lime juice"),
    (r"\bworcestershire sauce\b", "worcestershire sauce"),
    (r"\btabasco sauce\b", "hot sauce"),
    (r"\bhot sauce\b", "hot sauce"),
    (r"\bwine vinegar\b|\bred wine vinegar\b|\bwhite wine vinegar\b|\bvinegar\b", "vinegar"),
    (r"\bolive oil\b", "olive oil"),
    (r"\bsesame oil\b", "sesame oil"),
    (r"\bcanola oil\b|\bcorn oil\b|\bvegetable oil\b|\boil\b", "cooking oil"),
    (r"\bquinoa\b", "quinoa"),
    (r"\brolled oats\b|\boats\b", "oats"),
    (r"\bcornmeal\b|\bcorn meal\b", "cornmeal"),
    (r"\braisins?\b", "raisins"),
    (r"\bpeas\b", "peas"),
    (r"\bmustard\b", "mustard"),
    (r"\bhoney\b", "honey"),
    (r"\bbuttermilk\b", "buttermilk"),
    (r"\bginger\b", "ginger"),
    (r"\bbay leaves?\b|\bbay leaf\b", "bay leaf"),
    (r"\bsalt\b", "salt"),
    (r"\bshortening\b", "shortening"),
    (r"\bcorn\b", "corn"),
    (r"\bcorn\s*starch\b|\bcornflour\b|\bcorn flour\b", "corn starch"),
    (r"\bpowdered sugar\b|\bconfectioners sugar\b|\bicing sugar\b", "powdered sugar"),
    (r"\bbrown sugar\b", "brown sugar"),
    (r"\bsugar\b", "sugar"),
    (r"\b(chicken breast|chicken breasts)\b", "chicken breast"),
    (r"\bchicken thighs?\b", "chicken thighs"),
    (r"\bchicken\b", "chicken"),
    (r"\bground beef\b", "ground beef"),
    (r"\bbeef sausage\b", "beef sausage"),
    (r"\bpork sausage\b|\bpork sausages\b", "pork sausage"),
    (r"\bchicken sausage\b|\bchicken sausages\b", "chicken sausage"),
    (r"\bbeef\s+for\s+stew\b|\bbeef stew meat\b|\bstew meat\b", "beef stew meat"),
    (r"\b(beef|hanger steak|rib steak|ribeye steak|sirloin steak|short ribs?|steak)\b", "beef"),
    (r"\bpork\b", "pork"),
    (r"\bham\b", "ham"),
    (r"\bbacon\b", "bacon"),
    (r"\bturkey\b", "turkey"),
    (r"\bshrimp\b", "shrimp"),
    (r"\bsalmon\b", "salmon"),
    (r"\btuna\b", "tuna"),
    (r"\bsardines?\b", "sardines"),
    (r"\beggs?\b", "eggs"),
    (r"\bwhole milk\b|\blow-fat milk\b|\breduced-fat milk\b|\bfat-free milk\b|\b2 percent milk\b|\bmilk\b", "milk"),
    (r"\b(evaporated milk)\b", "evaporated milk"),
    (r"\b(condensed milk)\b", "condensed milk"),
    (r"\boat milk\b|\boatmilk\b", "oat milk"),
    (r"\balmond milk\b|\balmondmilk\b", "almond milk"),
    (r"\bcoconut milk\b", "coconut milk"),
    (r"\bbutter\b", "butter"),
    (r"\bcream cheese\b", "cream cheese"),
    (r"\bheavy cream\b", "heavy cream"),
    (r"\byogurt\b", "yogurt"),
    (r"\bmozzarella\b", "mozzarella cheese"),
    (r"\bcheddar\b", "cheddar cheese"),
    (r"\bparmesan\b", "parmesan cheese"),
    (r"\bfeta\b", "feta cheese"),
    (r"\bricotta\b", "ricotta cheese"),
    (r"\bcottage cheese\b", "cottage cheese"),
    (r"\bcheese\b", "cheese"),
    (r"\bparsley\b", "parsley"),
    (r"\bcilantro\b", "cilantro"),
    (r"\bbasil\b", "basil"),
    (r"\bthyme\b", "thyme"),
    (r"\boregano\b", "oregano"),
    (r"\brosemary\b", "rosemary"),
    (r"\bstrawberr(?:y|ies)\b", "strawberries"),
    (r"\bnectarines?\b", "nectarines"),
    (r"\bbananas?\b", "bananas"),
    (r"\bapples?\b", "apples"),
    (r"\bpineapple\b", "pineapple"),
    (r"\btomato paste\b", "tomato paste"),
    (r"\btomato sauce\b", "tomato sauce"),
    (r"\bcrushed tomatoes\b", "crushed tomatoes"),
    (r"\bdiced tomatoes\b", "diced tomatoes"),
    (r"\bstewed tomatoes\b", "stewed tomatoes"),
    (r"\btomatoes?\b", "tomatoes"),
    (r"\bpeppers?\b", "peppers"),
    (r"\blettuce\b", "lettuce"),
    (r"\bspinach\b", "spinach"),
    (r"\barugula\b", "arugula"),
    (r"\bkale\b", "kale"),
    (r"\bcelery\b", "celery"),
    (r"\bcucumbers?\b", "cucumber"),
    (r"\bmushrooms?\b", "mushrooms"),
    (r"\bgarlic\b", "garlic"),
    (r"\bshallots?\b", "shallots"),
    (r"\bzucchini\b", "zucchini"),
    (r"\bsquash\b", "squash"),
    (r"\basparagus\b", "asparagus"),
    (r"\bcauliflower\b", "cauliflower"),
    (r"\bcabbage\b", "cabbage"),
    (r"\bavocados?\b", "avocado"),
    (r"\beggplants?\b", "eggplant"),
    (r"\bbeets?\b", "beets"),
    (r"\bradishes?\b", "radishes"),
    (r"\bleeks?\b", "leeks"),
    (r"\bbroccoli\b", "broccoli"),
    (r"\bcarrots?\b", "carrots"),
    (r"\bonions?\b", "onions"),
    (r"\bpotatoes\b", "potatoes"),
    (r"\brice\b", "rice"),
    (r"\bpasta\b|\bspaghetti\b|\bpenne\b|\blinguine\b|\bravioli\b", "pasta"),
    (r"\bbeans?\b", "beans"),
    (r"\bbroth\b", "broth"),
    (r"\bstock\b", "stock"),
    (r"\bsoup\b", "soup"),
    (r"\bpasta sauce\b|\bmarinara\b|\btomato basil sauce\b", "pasta sauce"),
    (r"\bsoy sauce\b", "soy sauce"),
    (r"\bsalsa\b", "salsa"),
    (r"\bsalad dressing\b|\bdressing\b", "salad dressing"),
    (r"\bmayonnaise\b|\bmayo\b", "mayonnaise"),
    (r"\bavocado oil\b", "avocado oil"),
    (r"\bvegetable oil\b", "vegetable oil"),
    (r"\bpeanut butter\b", "peanut butter"),
    (r"\byeast\b", "yeast"),
)

BRAND_HINTS = {
    "arm and hammer",
    "barilla",
    "belgioioso",
    "betty crocker",
    "boars head",
    "bob s red mill",
    "bowl and basket",
    "bushs",
    "campbells",
    "carnation",
    "chobani",
    "college inn",
    "domino",
    "goya",
    "gold medal",
    "hellmanns",
    "heinz",
    "jell-o",
    "kerrygold",
    "king arthur",
    "kitchen basics",
    "kraft",
    "land o lakes",
    "minute rice",
    "morton williams",
    "pillsbury",
    "progresso",
    "ronzoni",
    "swanson",
}

PRODUCT_EVIDENCE_PATTERNS = (
    r"\b(milk|butter|cheese|cream|yogurt|flour|sugar|baking|yeast|chicken|beef|pork|steak|turkey|ham|bacon|shrimp|salmon|tuna|fish|eggs?)\b",
    r"\b(rice|pasta|spaghetti|penne|beans|soup|broth|stock|sauce|salsa|dressing|oil|vinegar|mayonnaise|mustard)\b",
    r"\b(tomatoes?|peppers?|lettuce|spinach|arugula|kale|celery|cucumbers?|mushrooms?|garlic|shallots?|zucchini|squash|asparagus|cauliflower|cabbage|avocados?|eggplants?|beets?|radishes?|leeks?|broccoli|carrots?|onions?|potatoes|parsley|cilantro|basil|strawberr|nectarine|banana|apple)\b",
    r"\b(water|soda|juice|tea|coffee|beer|chips|crackers|cookies|cereal|oatmeal|bread|rolls?|buns?|tortilla)\b",
)

NOISE_NAME_PATTERNS = (
    r"^the cost is$",
    r"^subtotal$",
    r"^total$",
    r"^delivery$",
    r"^pickup$",
    r"^sign in$",
    r"^search$",
    r"^menu$",
    r"^shop now$",
    r"^view all$",
    r"^weekly ad$",
    r"^privacy policy$",
    r"^terms of use$",
    r"^copyright$",
)

SENTENCE_FRAGMENT_PATTERNS = (
    r"^for\s+",
    r"^rolled in\s+",
    r"^stuffed with\s+",
    r"^with\s+",
    r"^made with\s+",
    r"^just heat\b",
)

NON_FOOD_CATEGORY_PATTERNS = (
    r"\b(bandages?|toilet paper|paper towels?|cleaner|detergent|dishwasher|soap|shampoo|conditioner|gloves|tissue|cat food|dog food|air freshener|medicine|caplets|cough drops)\b",
)

BRAND_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9'&.-]+(?:\s+[A-Z][A-Za-z0-9'&.-]+){0,2})\s+brand\b")


@dataclass
class ParsedIngredient:
    raw_text: str
    quantity: float | None = None
    quantity_min: float | None = None
    quantity_max: float | None = None
    unit: str | None = None
    canonical_name: str = ""
    brand: str | None = None
    form: str | None = None
    fat_level: str | None = None
    salted_status: str | None = None
    sweetened_status: str | None = None
    freshness: str | None = None
    cut: str | None = None
    bone_status: str | None = None
    skin_status: str | None = None
    nutritional_qualifiers: list[str] = field(default_factory=list)
    dietary_qualifiers: list[str] = field(default_factory=list)
    preparation: list[str] = field(default_factory=list)
    optional: bool = False
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_unicode(value: str) -> str:
    text = str(value or "")
    for char, replacement in UNICODE_FRACTIONS.items():
        text = text.replace(char, f" {replacement}")
    return unicodedata.normalize("NFKC", text).replace("\u2044", "/")


def normalize_text(value: str, *, keep_percent_word: bool = True) -> str:
    text = normalize_unicode(value).casefold()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"\b(\d+)\s*%", r"\1 percent", text)
    text = re.sub(r"\b(\d+)\s*pct\b", r"\1 percent", text)
    text = text.replace("&", " and ")
    text = re.sub(r"(?<=\w)'s\b", "s", text)
    text = text.replace("'", "")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    text = re.sub(r"[./]", " ", text)
    text = re.sub(r"[^a-z0-9%+\-\s]", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    for wrong, right in MISSPELLINGS.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text)
    if keep_percent_word:
        text = re.sub(r"\b(\d+)\s+percent\b", r"\1 percent", text)
    return text


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return None
    unit = normalize_text(value)
    unit = unit.replace("fl ounce", "fl oz").replace("fluid oz", "fl oz")
    return UNIT_ALIASES.get(unit, unit)


def apply_alias(value: str) -> str:
    normalized = normalize_text(value)
    return ALIAS_TO_CANONICAL.get(normalized, normalized)


def parse_number(value: str) -> float | None:
    value = normalize_unicode(value).strip()
    if not value:
        return None
    parts = value.split()
    try:
        if len(parts) == 2 and "/" in parts[1]:
            return float(Fraction(parts[0]) + Fraction(parts[1]))
        if "/" in value:
            return float(Fraction(value))
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None


def _quantity_pattern() -> str:
    simple = r"\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?"
    return rf"(?P<first>{simple})(?:\s*(?:-|to)\s*(?P<second>{simple}))?"


def extract_quantity_and_unit(text: str) -> tuple[float | None, float | None, float | None, str | None, str]:
    normalized = normalize_unicode(text)
    match = re.match(rf"^\s*{_quantity_pattern()}\s*(?P<rest>.*)$", normalized, re.I)
    if not match:
        return None, None, None, None, normalized.strip()
    first = parse_number(match.group("first"))
    second = parse_number(match.group("second") or "")
    rest = match.group("rest").strip()
    unit = None
    words = rest.split()
    if words:
        two_word_unit = " ".join(words[:2]).rstrip(".")
        one_word_unit = words[0].rstrip(".")
        if normalize_unit(two_word_unit) in UNIT_ALIASES.values():
            unit = normalize_unit(two_word_unit)
            rest = " ".join(words[2:])
        elif normalize_unit(one_word_unit):
            candidate = normalize_unit(one_word_unit)
            if normalize_text(one_word_unit) in UNIT_ALIASES:
                unit = candidate
                rest = " ".join(words[1:])
    if second is not None:
        return first, first, second, unit, rest
    return first, None, None, unit, rest


def split_alternatives(text: str) -> tuple[str, list[str]]:
    alternatives = []
    cleaned = text
    parenthetical_alts = re.findall(r"\((?:or|or use)\s+([^)]+)\)", cleaned, flags=re.I)
    alternatives.extend(normalize_text(item) for item in parenthetical_alts)
    cleaned = re.sub(r"\((?:or|or use)\s+[^)]+\)", "", cleaned, flags=re.I)
    if re.search(r"\s+or\s+", cleaned, flags=re.I):
        primary, *alts = re.split(r"\s+or\s+", cleaned, maxsplit=2, flags=re.I)
        alternatives.extend(normalize_text(alt) for alt in alts if alt.strip())
        cleaned = primary
    return cleaned.strip(), [alt for alt in alternatives if alt]


def extract_preparation(text: str) -> tuple[str, list[str]]:
    found = []
    working = text
    for term in PREPARATION_TERMS:
        pattern = rf"(?:,\s*|\b){re.escape(term)}\b"
        if re.search(pattern, working, flags=re.I):
            found.append(term)
            working = re.sub(pattern, " ", working, flags=re.I)
    working = re.sub(r"\s+", " ", working).strip(" ,")
    return working, found


def _extract_phrase(text: str, phrase: str) -> tuple[str, bool]:
    if re.search(rf"\b{re.escape(phrase)}\b", text):
        text = re.sub(rf"\b{re.escape(phrase)}\b", " ", text).strip()
        return re.sub(r"\s+", " ", text), True
    return text, False


def extract_modifiers(text: str, *, preserve_identity: bool = False) -> tuple[str, dict[str, Any]]:
    features: dict[str, Any] = {
        "nutritional_qualifiers": [],
        "dietary_qualifiers": [],
    }
    working = normalize_text(text)
    for attr in DIETARY_ATTRIBUTES:
        working, found = _extract_phrase(working, attr)
        if found:
            features["dietary_qualifiers"].append(attr)

    for feature, phrases in MEANINGFUL_MODIFIERS.items():
        for phrase in phrases:
            identity_match = (
                preserve_identity
                and any(identity == working and phrase in identity for identity in IDENTITY_PHRASES)
            )
            next_working, found = _extract_phrase(working, phrase)
            if found and not features.get(feature):
                features[feature] = phrase
                if feature in {"fat_level", "salted_status"}:
                    features["nutritional_qualifiers"].append(phrase)
            if found and not identity_match:
                working = next_working

    working = re.sub(r"\s+", " ", working).strip()
    return working, features


def extract_brand(text: str) -> tuple[str, str | None]:
    match = BRAND_PATTERN.search(text)
    if not match:
        return text, None
    brand = match.group(1).strip()
    cleaned = (text[: match.start()] + " " + text[match.end() :]).strip()
    return re.sub(r"\s+", " ", cleaned), brand


def parse_ingredient(raw_text: str) -> ParsedIngredient:
    raw = str(raw_text or "").strip()
    if re.match(r"^\s*\d+\s*(?:%|pct\b)", raw, flags=re.I):
        quantity, quantity_min, quantity_max, unit, rest = None, None, None, None, raw
    else:
        quantity, quantity_min, quantity_max, unit, rest = extract_quantity_and_unit(raw)
    rest, alternatives = split_alternatives(rest)
    rest, preparation = extract_preparation(rest)
    rest, brand = extract_brand(rest)
    normalized_rest = normalize_text(rest)
    optional = bool(re.search(r"\boptional\b", normalized_rest))
    normalized_rest = re.sub(r"\boptional\b", " ", normalized_rest).strip()
    canonical_source, features = extract_modifiers(normalized_rest, preserve_identity=True)
    canonical_source = re.sub(r"\bcut into\b.*$", " ", canonical_source).strip()
    canonical_source = re.sub(r"^of\s+", "", canonical_source).strip()
    if re.search(r"\bstew meat\b", canonical_source) and "beef" not in canonical_source:
        canonical_source = "beef stew meat"
    canonical_words = canonical_source.split()
    if quantity is not None and unit is None and canonical_words:
        if canonical_words[0] in COUNT_CONTAINER_UNITS and len(canonical_words) > 1:
            unit = COUNT_CONTAINER_UNITS[canonical_words[0]]
            canonical_source = " ".join(canonical_words[1:])
            canonical_words = canonical_source.split()
        if canonical_words and canonical_words[0] in COUNT_DESCRIPTOR_WORDS and len(canonical_words) > 1:
            canonical_source = " ".join(canonical_words[1:])
            canonical_words = canonical_source.split()
        if canonical_words and canonical_words[0] in COUNT_INGREDIENT_UNITS:
            unit = canonical_words[0].rstrip("s") if canonical_words[0] != "potatoes" else "potato"
            canonical_source = COUNT_INGREDIENT_UNITS[canonical_words[0]]
    canonical = apply_alias(canonical_source)
    canonical = re.sub(r"\s+", " ", canonical).strip(" ,-")
    if not canonical and unit in COUNT_UNIT_INGREDIENTS:
        canonical = unit
    return ParsedIngredient(
        raw_text=raw,
        quantity=quantity,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        unit=unit,
        canonical_name=canonical,
        brand=brand,
        form=features.get("form"),
        fat_level=features.get("fat_level"),
        salted_status=features.get("salted_status"),
        sweetened_status=features.get("sweetened_status"),
        freshness=features.get("freshness"),
        bone_status=features.get("bone_status"),
        skin_status=features.get("skin_status"),
        nutritional_qualifiers=features["nutritional_qualifiers"],
        dietary_qualifiers=features["dietary_qualifiers"],
        preparation=preparation,
        optional=optional,
        alternatives=alternatives,
    )


def stable_product_id(product: dict[str, Any], index: int | None = None) -> str:
    identity = {
        "name": product.get("name") or product.get("product_name"),
        "price": product.get("price"),
        "unit": product.get("unit") or product.get("package_size"),
        "source": product.get("source"),
        "notes": product.get("notes") or product.get("url"),
        "index": index,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"mw_{digest}"


def clean_product_name(value: str | None) -> str:
    text = normalize_unicode(value or "")
    text = re.sub(r"\u200b", "", text)
    text = re.sub(r"\.{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    return text


def parse_price_value(value: Any) -> float | None:
    text = str(value or "").replace(",", "")
    multi = re.search(r"\b\d+\s+for\s+\$(\d+(?:\.\d{1,2})?)\b", text, flags=re.I)
    if multi:
        return round(float(multi.group(1)), 2)
    match = re.search(r"\$(\d+(?:\.\d{1,2})?)\b", text)
    if match:
        return round(float(match.group(1)), 2)
    return None


def product_evidence_score(name: str, price: Any, unit: Any, source: str) -> tuple[int, list[str]]:
    normalized = normalize_text(name)
    reasons = []
    score = 0
    if parse_price_value(price) is not None:
        score += 35
    else:
        reasons.append("no usable price")
    if normalize_text(unit):
        score += 15
    if source == "mortonwilliams-storefront":
        score += 20
    if any(re.search(pattern, normalized) for pattern in PRODUCT_EVIDENCE_PATTERNS):
        score += 20
    if len(normalized.split()) >= 2:
        score += 10
    if any(brand in normalized for brand in BRAND_HINTS):
        score += 10
    return min(score, 100), reasons


def classify_product_record(
    product: Any,
    index: int | None = None,
    seen_fingerprints: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    if not isinstance(product, dict):
        return {
            "record_status": MALFORMED_RECORD,
            "exclusion_reasons": ["record is not an object"],
            "source_quality_score": 0,
            "normalized_name": "",
            "eligible_for_retrieval": False,
        }

    raw_name = product.get("name") or product.get("product_name") or ""
    name = clean_product_name(raw_name)
    normalized_name = normalize_text(name)
    price = product.get("price")
    unit = product.get("unit") or product.get("package_size") or ""
    source = str(product.get("source") or "")
    exclusion_reasons = []

    if not normalized_name or len(normalized_name) < 3:
        exclusion_reasons.append("empty or nearly empty name")
    if product.get("price") in (None, ""):
        exclusion_reasons.append("missing price")
    if not source:
        exclusion_reasons.append("missing source")

    if exclusion_reasons:
        return {
            "record_status": MALFORMED_RECORD,
            "exclusion_reasons": exclusion_reasons,
            "source_quality_score": 0,
            "normalized_name": normalized_name,
            "eligible_for_retrieval": False,
        }

    for pattern in NOISE_NAME_PATTERNS:
        if re.search(pattern, normalized_name):
            exclusion_reasons.append("scraper/navigation/description noise")
            break
    for pattern in SENTENCE_FRAGMENT_PATTERNS:
        if re.search(pattern, normalized_name):
            exclusion_reasons.append("sentence fragment")
            break
    if re.search(r"\b(shopping cart|add to cart|learn more|browse aisle|view details)\b", normalized_name):
        exclusion_reasons.append("instructional or navigation text")

    score, evidence_reasons = product_evidence_score(name, price, unit, source)
    exclusion_reasons.extend(evidence_reasons)
    if score < 35:
        exclusion_reasons.append("no usable price or product evidence")

    fingerprint = (normalized_name, str(price or "").strip(), normalize_text(str(unit or "")))
    if seen_fingerprints is not None:
        if fingerprint in seen_fingerprints:
            exclusion_reasons.append("duplicate scraper artifact")
        else:
            seen_fingerprints.add(fingerprint)

    if exclusion_reasons:
        return {
            "record_status": SCRAPER_NOISE,
            "exclusion_reasons": sorted(set(exclusion_reasons)),
            "source_quality_score": min(score, 45),
            "normalized_name": normalized_name,
            "eligible_for_retrieval": False,
        }

    probable_reasons = []
    if source == "mortonwilliams-pdf":
        probable_reasons.append("pdf flyer row")
    if re.search(r"\bor\b", normalized_name):
        probable_reasons.append("multi-product flyer row")
    if len(normalized_name.split()) <= 2 and not any(brand in normalized_name for brand in BRAND_HINTS):
        probable_reasons.append("generic short product name")
    if any(re.search(pattern, normalized_name) for pattern in NON_FOOD_CATEGORY_PATTERNS):
        probable_reasons.append("non-food grocery aisle product")

    if probable_reasons:
        return {
            "record_status": PROBABLE_PRODUCT,
            "exclusion_reasons": [],
            "source_quality_score": max(50, min(score, 74)),
            "quality_notes": probable_reasons,
            "normalized_name": normalized_name,
            "eligible_for_retrieval": True,
        }

    return {
        "record_status": VALID_PRODUCT,
        "exclusion_reasons": [],
        "source_quality_score": max(75, score),
        "quality_notes": [],
        "normalized_name": normalized_name,
        "eligible_for_retrieval": True,
    }


def normalize_package_text(value: str | None) -> str:
    text = normalize_unicode(value or "").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    text = re.sub(r"[^a-z0-9.+\-\sx/]", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_package_size(value: str | None) -> tuple[float | None, str | None, float | None, str | None]:
    text = normalize_package_text(value or "")
    if not text:
        return None, None, None, None
    match = re.search(r"(?P<count>\d+(?:\.\d+)?)\s*x\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>fl oz|fluid ounce|oz|lb|pound|g|gram|kg|ct|count|each|ml|l|liter)", text)
    if match:
        quantity = float(match.group("count")) * float(match.group("amount"))
        unit = normalize_unit(match.group("unit"))
    else:
        match = re.search(r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>fl oz|fluid ounce|oz|lb|pound|g|gram|kg|ct|count|each|ml|l|liter|pack)\b", text)
        if not match:
            return None, None, None, None
        quantity = float(match.group("amount"))
        unit = normalize_unit(match.group("unit"))
    base_quantity, base_unit = to_base_unit(quantity, unit)
    return quantity, unit, base_quantity, base_unit


def validate_package_parse(
    quantity: float | None,
    unit: str | None,
    source_text: str | None,
    product_name: str | None = None,
) -> tuple[str, str | None, list[str]]:
    warnings: list[str] = []
    source = "structured_unit" if normalize_package_text(source_text or "") else None
    if quantity is None or not unit:
        return "none", source, ["package size unavailable"]
    text = normalize_package_text(" ".join(part for part in (source_text, product_name) if part))
    if re.search(r"\b(variable weight|sold by weight|average weight|avg weight|per lb|per pound|family pack)\b", text):
        warnings.append("variable-weight package; fixed package quantity is not reliable")
    if re.search(r"\b\d+\s+\d+\s*(?:oz|fl oz|lb|ml|l|g|kg)\b", text) and not re.search(
        r"\b\d+\s+\d+/\d+\s*(?:oz|fl oz|lb|ml|l|g|kg)\b", text
    ):
        warnings.append("adjacent numeric tokens may indicate decimal-loss or merged source text")
    if unit in {"ounce", "fluid ounce"} and quantity >= 128:
        warnings.append("large ounce package should be verified before optimization")
    if unit == "gram" and quantity > 10000:
        warnings.append("large gram package should be verified before optimization")
    if quantity <= 0:
        warnings.append("non-positive package quantity")
    confidence = "high"
    if warnings:
        confidence = "low" if any("large ounce" in warning or "variable-weight" in warning or "non-positive" in warning for warning in warnings) else "medium"
    return confidence, source, warnings


def to_base_unit(quantity: float, unit: str | None) -> tuple[float | None, str | None]:
    if quantity is None or not unit:
        return None, None
    conversions = {
        "pound": (453.592, "gram"),
        "ounce": (28.3495, "gram"),
        "kilogram": (1000, "gram"),
        "gram": (1, "gram"),
        "fluid ounce": (29.5735, "milliliter"),
        "liter": (1000, "milliliter"),
        "milliliter": (1, "milliliter"),
    }
    factor, base = conversions.get(unit, (1, unit))
    return round(quantity * factor, 3), base


def infer_category(name: str) -> tuple[str | None, str | None]:
    text = normalize_text(name)
    rules = (
        (r"\b(chicken|beef|steak|pork|bacon|turkey|fish|salmon|shrimp|ham|sausage)\b", "meat", None),
        (r"\b(milk|cheese|butter|cream|yogurt)\b", "dairy", None),
        (r"\b(flour|sugar|baking powder|baking soda|yeast|cake mix|brownie)\b", "pantry", "baking"),
        (r"\b(tomato paste|canned|sauce|pasta|rice|beans|broth|stock|soup|oil|vinegar|mayonnaise|mustard|salsa)\b", "pantry", None),
        (r"\b(parsley|cilantro|basil|thyme|oregano|lettuce|spinach|arugula|kale|celery|cucumbers?|mushrooms?|garlic|shallots?|zucchini|squash|asparagus|cauliflower|cabbage|avocados?|eggplants?|beets?|radishes?|leeks?|peppers?|onions?|strawberr|nectarines?|apples?|bananas?|tomatoes?|broccoli|carrots?|potatoes)\b", "produce", None),
        (r"\b(water|soda|juice|ale)\b", "beverage", None),
        (r"\b(chips|crackers|cookies|cereal|pretzel|popcorn)\b", "snacks", None),
        (r"\b(cleaner|detergent|paper towel|tissue|bandage|soap|shampoo|conditioner)\b", "household", None),
    )
    for pattern, category, subcategory in rules:
        if re.search(pattern, text):
            return category, subcategory
    return None, None


def canonical_for_product(normalized_name: str) -> str | None:
    normalized = apply_alias(normalized_name)
    for pattern, canonical in CANONICAL_PATTERNS:
        if re.search(pattern, normalized):
            if canonical == "peppers" and "dr pepper" in normalized:
                continue
            if canonical == "sugar" and re.search(r"\b(soda|drink|sports drink)\b", normalized):
                continue
            if canonical == "milk" and "muscle milk" in normalized:
                continue
            if canonical in {"beef", "chicken", "chicken breast", "chicken thighs"} and re.search(r"\b(broth|stock|bouillon)\b", normalized):
                continue
            if canonical == "pasta" and re.search(r"\bpasta sauce\b", normalized):
                continue
            if canonical == "butter" and re.search(r"\bpeanut butter\b", normalized):
                return "peanut butter"
            return canonical
    return normalized if normalized in set(ALIAS_TO_CANONICAL.values()) else None


def infer_brand(name: str) -> str | None:
    normalized = normalize_text(name)
    for brand in sorted(BRAND_HINTS, key=len, reverse=True):
        if normalized.startswith(brand):
            return " ".join(word.capitalize() for word in brand.split())
    return None


def uncertainty_reasons(feature: dict[str, Any]) -> list[str]:
    reasons = []
    status = feature.get("record_status")
    if status == MALFORMED_RECORD:
        reasons.append("malformed source record")
    if status == SCRAPER_NOISE:
        reasons.append("probable scraper noise")
    if feature.get("eligible_for_retrieval") and not feature.get("canonical_name"):
        reasons.append("canonical ingredient not assigned")
    if feature.get("eligible_for_retrieval") and not feature.get("brand"):
        reasons.append("brand unavailable")
    if feature.get("eligible_for_retrieval") and (
        not feature.get("category") or not feature.get("subcategory")
    ):
        reasons.append("insufficient product metadata")
    if feature.get("eligible_for_retrieval") and not feature.get("package_quantity"):
        reasons.append("package size unavailable")
    if feature.get("eligible_for_retrieval") and (
        " or " in feature.get("normalized_name", "")
        or feature.get("record_status") == PROBABLE_PRODUCT
    ):
        reasons.append("ambiguous product identity")
    return reasons


def extract_product_features(
    product: dict[str, Any],
    index: int | None = None,
    seen_fingerprints: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    classification = classify_product_record(product, index, seen_fingerprints)
    source_name = clean_product_name(product.get("product_name") or product.get("name") or "")
    normalized_name = classification["normalized_name"]
    remaining, features = extract_modifiers(normalized_name, preserve_identity=True)
    category = product.get("category")
    subcategory = product.get("subcategory")
    inferred_category, inferred_subcategory = infer_category(normalized_name)
    package_source_text = product.get("package_size") or product.get("unit") or ""
    package_quantity, package_unit, package_quantity_base, base_unit = parse_package_size(package_source_text)
    package_confidence, package_source, package_warnings = validate_package_parse(
        package_quantity,
        package_unit,
        package_source_text,
        source_name,
    )
    feature = {
        "product_id": product.get("id") or stable_product_id(product, index),
        "original_product_name": source_name,
        "normalized_name": normalized_name,
        "record_status": classification["record_status"],
        "exclusion_reasons": classification["exclusion_reasons"],
        "source_quality_score": classification["source_quality_score"],
        "quality_notes": classification.get("quality_notes", []),
        "eligible_for_retrieval": classification["eligible_for_retrieval"],
        "raw_price": product.get("price"),
        "raw_unit_text": package_source_text,
        "price": parse_price_value(product.get("price")),
        "canonical_name": canonical_for_product(normalized_name),
        "brand": product.get("brand") or infer_brand(source_name),
        "category": category or product.get("food_group") or inferred_category,
        "subcategory": subcategory or inferred_subcategory,
        "form": features.get("form"),
        "fat_level": features.get("fat_level"),
        "salted_status": features.get("salted_status"),
        "sweetened_status": features.get("sweetened_status"),
        "freshness": features.get("freshness"),
        "cut": features.get("cut"),
        "bone_status": features.get("bone_status"),
        "skin_status": features.get("skin_status"),
        "dietary_attributes": features.get("dietary_qualifiers", []),
        "package_quantity": package_quantity,
        "package_unit": package_unit,
        "package_quantity_base": package_quantity_base,
        "base_unit": base_unit,
        "package_parse_confidence": package_confidence,
        "package_parse_source": package_source,
        "package_parse_warnings": package_warnings,
        "feature_extraction_version": FEATURE_EXTRACTION_VERSION,
    }
    feature["uncertainty_reasons"] = uncertainty_reasons(feature)
    return feature
