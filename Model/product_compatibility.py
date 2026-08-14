from __future__ import annotations

import json
import copy
import re
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ingredient_normalization import COMMON_PRODUCE_CANONICALS, apply_alias, canonical_for_product, normalize_text, parse_ingredient
from product_retrieval import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_INDEX_DIR,
    Candidate,
    CandidateRetrievalResult,
    ProductCandidateRetriever,
    load_existing_index,
    load_features,
)


MATCHER_VERSION = "ingredient-product-matcher-v1.12"
DEFAULT_OVERRIDES_PATH = Path(__file__).resolve().parent / "product_match_overrides.json"
DEFAULT_EVALUATION_FIXTURE = Path(__file__).resolve().parent / "evaluation" / "product_match_cases.jsonl"

COMPATIBLE = "compatible"
SOFT_PREFERENCE = "soft_preference"
STRONG_PENALTY = "strong_penalty"
HARD_REJECT = "hard_reject"
UNKNOWN = "unknown"

EXACT = "exact"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"
NO_SAFE_MATCH = "no_safe_match"
SUBSTITUTION_ONLY = "substitution_only"

SUBSTITUTION_SCORES = {
    "exact_equivalent": 1.00,
    "strong_substitute": 0.90,
    "good_substitute": 0.80,
    "acceptable_substitute": 0.68,
    "last_resort": 0.52,
}


@dataclass(frozen=True)
class MatchScoringConfig:
    exact_match_bonus: float = 0.16
    alias_match_bonus: float = 0.08
    canonical_identity_weight: float = 0.27
    family_weight: float = 0.12
    lexical_weight: float = 0.12
    semantic_weight: float = 0.12
    category_weight: float = 0.07
    attribute_weight: float = 0.13
    brand_weight: float = 0.04
    source_quality_weight: float = 0.04
    strong_penalty: float = 0.22
    soft_penalty: float = 0.06
    probably_valid_penalty: float = 0.03
    exact_threshold: float = 0.90
    high_threshold: float = 0.78
    medium_threshold: float = 0.62
    low_threshold: float = 0.45
    minimum_selection_score: float = 0.45
    ambiguity_margin: float = 0.06


@dataclass
class IngredientProfile:
    normalized_signature: str
    canonical: str | None
    family: str | None
    category: str | None
    form: str | None = None
    freshness: str | None = None
    fat_level: str | None = None
    fat_percent: str | None = None
    salted_status: str | None = None
    sweetened_status: str | None = None
    dairy_type: str | None = None
    milk_kind: str | None = None
    flour_type: str | None = None
    tomato_type: str | None = None
    broth_type: str | None = None
    broth_species: str | None = None
    soup_type: str | None = None
    produce_type: str | None = None
    meat_species: str | None = None
    meat_cut: str | None = None
    ground: bool = False
    bone_status: str | None = None
    skin_status: str | None = None
    flavor: str | None = None
    culinary_type: str | None = None
    dietary_requirements: set[str] = field(default_factory=set)
    brand: str | None = None
    raw_text: str = ""


@dataclass
class CompatibilitySignal:
    rule: str
    classification: str
    message: str


@dataclass
class RankedCandidate:
    product_id: str
    product_name: str
    normalized_name: str
    canonical_ingredient: str | None
    record_status: str | None
    confidence: str
    final_score: float
    score_breakdown: dict[str, float]
    conflicts: list[dict[str, str]]
    warnings: list[str]
    reason_codes: list[str]
    exact_match: bool
    alias_match: bool
    lexical_similarity: float
    semantic_similarity: float | None
    is_substitution: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatchResult:
    raw_ingredient: str
    parsed_ingredient: dict[str, Any]
    normalized_ingredient_signature: str
    selected_match: RankedCandidate | None
    compatible_alternatives: list[RankedCandidate]
    substitution_candidates: list[RankedCandidate]
    rejected_candidates: list[RankedCandidate]
    confidence: str
    final_score: float
    warnings: list[str]
    reason_codes: list[str]
    cache_hit: bool
    retrieval_timing_ms: float | None
    reranking_timing_ms: float
    total_timing_ms: float
    matcher_version: str
    product_index_version: str | None
    override_version: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("selected_match",):
            if payload[key] is not None:
                payload[key] = self.selected_match.to_dict()
        payload["compatible_alternatives"] = [item.to_dict() for item in self.compatible_alternatives]
        payload["substitution_candidates"] = [item.to_dict() for item in self.substitution_candidates]
        payload["rejected_candidates"] = [item.to_dict() for item in self.rejected_candidates]
        return payload


class MatchCache:
    def __init__(self, max_size: int = 2048):
        self.max_size = max_size
        self._items: OrderedDict[str, MatchResult] = OrderedDict()

    def get(self, key: str) -> MatchResult | None:
        item = self._items.get(key)
        if item is None:
            return None
        self._items.move_to_end(key)
        return item

    def set(self, key: str, value: MatchResult) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


class OverrideStore:
    def __init__(self, path: Path = DEFAULT_OVERRIDES_PATH):
        self.path = Path(path)
        self._data: dict[str, Any] | None = None
        self.load_error: str | None = None

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            self._data = self.load()
        return self._data

    @property
    def version(self) -> str:
        return str(self.data.get("version") or "missing")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return default_overrides()
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("override root must be an object")
            merged = default_overrides()
            merged.update(data)
            for key in default_overrides():
                if key != "version" and not isinstance(merged.get(key), list):
                    raise ValueError(f"override field {key} must be a list")
            return merged
        except Exception as exc:
            self.load_error = str(exc)
            return default_overrides()

    def normalized_alias(self, query: str) -> str:
        normalized = normalize_text(query)
        for item in self.data.get("aliases", []):
            if normalize_text(item.get("alias")) == normalized:
                return normalize_text(item.get("canonical") or normalized)
        for item in self.data.get("canonical_overrides", []):
            if normalize_text(item.get("query")) == normalized:
                return normalize_text(item.get("canonical") or normalized)
        return apply_alias(normalized)

    def matching_items(self, key: str, query: str) -> list[dict[str, Any]]:
        normalized = normalize_text(query)
        return [
            item
            for item in self.data.get(key, [])
            if normalize_text(item.get("query") or item.get("normalized_query") or "") == normalized
        ]


def default_overrides() -> dict[str, Any]:
    return {
        "version": "default-empty-overrides-v1",
        "forbidden_products": [],
        "forced_matches": [],
        "approved_matches": [],
        "canonical_overrides": [],
        "aliases": [],
        "substitutions": [],
        "incompatible_families": [],
    }


@lru_cache(maxsize=4096)
def compiled_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def text_has(text: str, *patterns: str) -> bool:
    return any(compiled_pattern(pattern).search(text) for pattern in patterns)


def normalize_fat(value: str | None, text: str) -> str | None:
    text = normalize_text(" ".join([value or "", text]))
    if text_has(text, r"\bfat-free\b", r"\bfat free\b", r"\bnon-fat\b", r"\bnonfat\b", r"\bskim\b", r"\b0 percent\b"):
        return "fat-free"
    if text_has(text, r"\blowfat\b", r"\blow-fat\b", r"\breduced-fat\b", r"\b2 percent\b", r"\b1 percent\b"):
        return "low-fat"
    if text_has(text, r"\bwhole milk\b", r"\bwhole\b"):
        return "whole"
    if text_has(text, r"\bheavy\b"):
        return "heavy"
    return value


def detect_fat_percent(text: str) -> str | None:
    if text_has(text, r"\b2 percent\b|\b2%\b"):
        return "2 percent"
    if text_has(text, r"\b1 percent\b|\b1%\b"):
        return "1 percent"
    return None


def detect_broth_species(text: str) -> str | None:
    for species in ("chicken", "beef", "vegetable", "seafood", "turkey"):
        if text_has(
            text,
            rf"\b{species}\s+(?:broth|stock|bouillon)\b|\b(?:broth|stock|bouillon)\s+{species}\b|\bbouillon\b.*\b{species}\b|\b{species}\s+flavo(?:r|u)r\s+bouillon\b",
        ):
            return species
    return None


def detect_yogurt_flavor(text: str) -> str | None:
    if text_has(text, r"\bplain\b"):
        return "plain"
    for flavor in ("vanilla", "guava", "mango", "papaya", "strawberry", "blueberry", "peach", "banana", "coconut"):
        if text_has(text, rf"\b{flavor}\b"):
            return flavor
    return None


def prepared_meat_product_text(text: str) -> bool:
    return text_has(
        text,
        r"\bstore prepared\b|\bsandwich(?:es)?\b|\bwraps?\b|\bdinners?\b|\bentr[eé]es?\b|\bfrozen entr[eé]es?\b|\bburritos?\b|\btaquitos?\b|\bempanadas?\b"
        r"|\b(?:beef|lamb|chicken)?\s*stew\s+soup\b|\bbeef stew with\b|\blamb stew with\b|\bbraised beef stew\b"
        r"|\bbeef\s+(?:and|&)\s+broccoli\b|\bsteak\b.*\b(?:canned\s+)?soup\b|\bdinty moore\b|\bmade for home\b.*\bbeef stew\b|\bprepared\b.*\bbeef\b|\bprepared\b.*\blamb\b|\bbeef\b.*\bpatties\b",
    )


def deli_processed_beef_text(text: str) -> bool:
    return text_has(
        text,
        r"\bcorned beef\b|\bpastrami\b|\bchipped beef\b|\bcreamed chipped beef\b|\blunch meat\b"
        r"|\bblack bear\b.*\broast beef\b|\broast beef\b.*\bblack bear\b"
        r"|\bboar'?s head\b.*\broast beef\b|\broast beef\b.*\bboar'?s head\b"
        r"|\broast beef\b.*\bsliced\b|\bsliced\b.*\broast beef\b|\bdeli\b.*\broast beef\b|\broast beef\b.*\bdeli\b",
    )


JUICE_PRODUCE_TYPES = {
    "apple",
    "carrot",
    "cranberry",
    "grape",
    "grapefruit",
    "lemon",
    "lime",
    "orange",
    "pineapple",
    "tomato",
}


BEEF_CUT_SUBSTITUTES = {
    "tenderloin": {"strip steak", "ribeye steak", "top sirloin"},
    "ribeye steak": {"strip steak", "top sirloin", "flat iron"},
    "strip steak": {"ribeye steak", "top sirloin", "flat iron"},
    "top sirloin": {"flat iron", "strip steak", "ribeye steak", "tri-tip"},
    "flat iron": {"top sirloin", "hanger steak", "flank steak"},
    "hanger steak": {"flat iron", "skirt steak", "flank steak"},
    "skirt steak": {"flank steak", "hanger steak", "flat iron"},
    "flank steak": {"skirt steak", "hanger steak", "flat iron"},
    "tri-tip": {"top sirloin", "sirloin tip roast"},
    "chuck roast": {"bottom round", "brisket", "shoulder clod", "stew meat", "chuck steak"},
    "brisket": {"chuck roast", "short ribs"},
    "short ribs": {"chuck roast", "brisket"},
    "bottom round": {"top round", "chuck roast", "eye of round"},
    "top round": {"bottom round", "eye of round"},
    "eye of round": {"top round", "bottom round"},
    "sirloin tip roast": {"tri-tip", "top round"},
    "shank": {"oxtail", "chuck roast"},
    "oxtail": {"shank", "short ribs"},
    "stew meat": {"chuck roast", "bottom round", "brisket", "chuck steak"},
    "ground chuck": {"ground beef", "ground sirloin"},
    "ground sirloin": {"ground chuck", "ground round"},
    "ground round": {"ground sirloin", "ground chuck"},
    "beef strips": {"flank steak", "skirt steak", "hanger steak", "flat iron", "strip steak", "shaved beef"},
}
ROAST_COMPATIBLE_BEEF_CUTS = {
    "ribeye steak",
    "chuck roast",
    "bottom round",
    "top round",
    "eye of round",
    "sirloin tip roast",
    "tri-tip",
}

BEEF_CUT_PATTERNS = [
    ("top round", r"\bround\s+or\s+flank\s+steak\b"),
    ("beef strips", r"\bbeef\b.*\b(?:strips|stir[-\s]?fry)\b|\b(?:strips|stir[-\s]?fry)\b.*\bbeef\b|\bpepper steak\b"),
    ("stew meat", r"\bbeef\s+(?:for\s+)?stew\b|\bbeef\s+stew(?:ing)?\s+meat\b|\bstew(?:ing)?\s+beef\b|\bbeef stew meat\b|\bstew beef\b|\bbeef\b.*\b(?:shoulder\s+)?stew\b|\bbeef\b.*\bsoup meat\b"),
    ("shank", r"\bbeef\s+(?:hind)?shank\b|\b(?:hind)?shank\b.*\bbeef\b"),
    ("oxtail", r"\boxtails?\b"),
    ("short ribs", r"\bshort ribs?\b|\bflanken\b"),
    ("brisket", r"\bbrisket\b"),
    ("chuck roast", r"\bchuck roast\b|\bchuck shoulder roast\b"),
    ("chuck steak", r"\bchuck steak\b|\bchuck filet steak\b|\bchuck shoulder steak\b|\b1st cut chuck steak\b"),
    ("bottom round", r"\bbottom round\b"),
    ("top round", r"\btop round\b|\blondon broil\b|\bbraciole\b|\bbracciole\b|\bcube steak\b"),
    ("eye of round", r"\beye (?:of )?round\b"),
    ("sirloin tip roast", r"\bsirloin tip roast\b"),
    ("tri-tip", r"\btri[-\s]?tip\b"),
    ("tenderloin", r"\btenderloin\b|\bfilet mignon\b|\bfilet\b|\bfillet\s+beef\b|\bbeef\s+fillet\b"),
    ("ribeye steak", r"\bribeye\b|\brib eye\b|\bstanding rib roast\b|\brib roast\b|\bprime rib\b|\brib steak\b"),
    ("strip steak", r"\bnew york strip\b|\bny strip\b|\bstrip steak\b|\bshell steak\b|\bclub steak\b"),
    ("top sirloin", r"\btop sirloin\b|\bsirloin steak\b|\bpalomilla\b"),
    ("flat iron", r"\bflat iron\b"),
    ("hanger steak", r"\bhanger\b"),
    ("skirt steak", r"\bskirt steak\b"),
    ("flank steak", r"\bflank steak\b"),
    ("porterhouse steak", r"\bporterhouse\b"),
    ("shaved beef", r"\b(shaved|thin sliced)\s+(?:steak\s+)?beef\b|\bsliced\s+steak\s+beef\b|\bbeef\s+(?:shaved|sliced)\s+steak\b|\bshaved steak beef\b"),
    ("steak", r"\bsteak\b"),
]


def add_pair(table: dict[tuple[str, str], float], left: str, right: str, tier: str, *, bidirectional: bool = True) -> None:
    table[(left, right)] = SUBSTITUTION_SCORES[tier]
    if bidirectional:
        table[(right, left)] = SUBSTITUTION_SCORES[tier]


CULINARY_SUBSTITUTION_PAIRS: dict[tuple[str, str], float] = {}
for left, right, tier in [
    ("neufchatel", "cream_cheese", "exact_equivalent"),
    ("mascarpone", "cream_cheese", "good_substitute"),
    ("mascarpone", "neufchatel", "good_substitute"),
    ("ricotta", "cream_cheese", "acceptable_substitute"),
    ("ricotta", "neufchatel", "acceptable_substitute"),
    ("ricotta", "mascarpone", "acceptable_substitute"),
    ("ricotta", "cottage_cheese", "strong_substitute"),
    ("ricotta", "farmer_cheese", "strong_substitute"),
    ("cottage_cheese", "farmer_cheese", "good_substitute"),
    ("monterey_jack", "colby", "strong_substitute"),
    ("monterey_jack", "mild_cheddar", "strong_substitute"),
    ("monterey_jack", "colby_jack", "strong_substitute"),
    ("monterey_jack", "low_moisture_mozzarella", "good_substitute"),
    ("colby", "mild_cheddar", "strong_substitute"),
    ("colby", "colby_jack", "strong_substitute"),
    ("mild_cheddar", "medium_cheddar", "strong_substitute"),
    ("medium_cheddar", "sharp_cheddar", "strong_substitute"),
    ("sharp_cheddar", "colby", "good_substitute"),
    ("low_moisture_mozzarella", "provolone", "strong_substitute"),
    ("fresh_mozzarella", "burrata", "good_substitute"),
    ("parmesan", "grana_padano", "exact_equivalent"),
    ("parmesan", "pecorino_romano", "strong_substitute"),
    ("parmesan", "aged_asiago", "good_substitute"),
    ("pecorino_romano", "aged_asiago", "good_substitute"),
    ("swiss", "emmental", "exact_equivalent"),
    ("swiss", "gruyere", "strong_substitute"),
    ("swiss", "jarlsberg", "strong_substitute"),
    ("gruyere", "emmental", "strong_substitute"),
    ("gruyere", "jarlsberg", "good_substitute"),
    ("feta", "goat_cheese", "good_substitute"),
    ("feta", "queso_fresco", "acceptable_substitute"),
    ("feta", "cotija", "acceptable_substitute"),
    ("cotija", "queso_fresco", "good_substitute"),
    ("blue_cheese", "gorgonzola", "strong_substitute"),
    ("blue_cheese", "roquefort", "strong_substitute"),
    ("blue_cheese", "stilton", "strong_substitute"),
    ("whole_milk", "2_percent_milk", "strong_substitute"),
    ("whole_milk", "1_percent_milk", "good_substitute"),
    ("whole_milk", "skim_milk", "acceptable_substitute"),
    ("2_percent_milk", "1_percent_milk", "strong_substitute"),
    ("2_percent_milk", "skim_milk", "good_substitute"),
    ("heavy_cream", "whipping_cream", "exact_equivalent"),
    ("heavy_cream", "half_and_half", "good_substitute"),
    ("heavy_cream", "evaporated_milk", "acceptable_substitute"),
    ("heavy_cream", "whole_milk", "last_resort"),
    ("half_and_half", "light_cream", "strong_substitute"),
    ("half_and_half", "evaporated_milk", "good_substitute"),
    ("plain_greek_yogurt", "plain_yogurt", "strong_substitute"),
    ("plain_greek_yogurt", "sour_cream", "strong_substitute"),
    ("plain_greek_yogurt", "creme_fraiche", "good_substitute"),
    ("plain_yogurt", "sour_cream", "good_substitute"),
    ("plain_yogurt", "plain_kefir", "good_substitute"),
    ("sour_cream", "creme_fraiche", "strong_substitute"),
    ("buttermilk", "plain_kefir", "good_substitute"),
    ("buttermilk", "plain_yogurt", "good_substitute"),
    ("butter", "margarine", "good_substitute"),
    ("butter", "plant_butter", "good_substitute"),
    ("butter", "neutral_oil", "acceptable_substitute"),
    ("olive_oil", "butter", "acceptable_substitute"),
    ("neutral_oil", "canola_oil", "exact_equivalent"),
    ("neutral_oil", "sunflower_oil", "strong_substitute"),
    ("neutral_oil", "grapeseed_oil", "strong_substitute"),
    ("neutral_oil", "avocado_oil", "strong_substitute"),
    ("olive_oil", "avocado_oil", "strong_substitute"),
    ("olive_oil", "neutral_oil", "good_substitute"),
    ("bread_flour", "high_gluten_flour", "strong_substitute"),
    ("bread_flour", "all_purpose_flour", "strong_substitute"),
    ("all_purpose_flour", "cake_flour", "acceptable_substitute"),
    ("all_purpose_flour", "bread_flour", "good_substitute"),
    ("cake_flour", "pastry_flour", "strong_substitute"),
    ("cake_flour", "all_purpose_flour", "good_substitute"),
    ("whole_wheat_flour", "white_whole_wheat_flour", "strong_substitute"),
    ("whole_wheat_flour", "all_purpose_flour", "acceptable_substitute"),
    ("cornstarch", "potato_starch", "strong_substitute"),
    ("cornstarch", "arrowroot", "strong_substitute"),
    ("cornstarch", "tapioca_starch", "good_substitute"),
    ("potato_starch", "arrowroot", "strong_substitute"),
    ("potato_starch", "tapioca_starch", "strong_substitute"),
    ("long_grain_white_rice", "jasmine_rice", "strong_substitute"),
    ("long_grain_white_rice", "basmati_rice", "strong_substitute"),
    ("jasmine_rice", "basmati_rice", "good_substitute"),
    ("arborio_rice", "carnaroli_rice", "strong_substitute"),
    ("arborio_rice", "long_grain_white_rice", "last_resort"),
    ("spaghetti", "linguine", "strong_substitute"),
    ("spaghetti", "fettuccine", "good_substitute"),
    ("spaghetti", "bucatini", "good_substitute"),
    ("penne", "rigatoni", "strong_substitute"),
    ("penne", "ziti", "strong_substitute"),
    ("penne", "mostaccioli", "strong_substitute"),
    ("elbow_macaroni", "small_shells", "strong_substitute"),
    ("elbow_macaroni", "ditalini", "good_substitute"),
    ("breadcrumbs", "panko", "strong_substitute"),
    ("breadcrumbs", "crushed_crackers", "good_substitute"),
    ("yellow_onion", "white_onion", "strong_substitute"),
    ("yellow_onion", "red_onion", "good_substitute"),
    ("yellow_onion", "shallot", "good_substitute"),
    ("white_onion", "red_onion", "good_substitute"),
    ("red_onion", "shallot", "good_substitute"),
    ("green_onion", "chives", "good_substitute"),
    ("green_onion", "shallot", "acceptable_substitute"),
    ("garlic_powder", "granulated_garlic", "strong_substitute"),
    ("tomato_sauce", "tomato_puree", "good_substitute"),
    ("tomato_sauce", "crushed_tomatoes", "good_substitute"),
    ("diced_tomatoes", "tomatoes", "strong_substitute"),
    ("diced_tomatoes", "crushed_tomatoes", "good_substitute"),
    ("crushed_tomatoes", "tomato_puree", "good_substitute"),
    ("fresh_tomatoes", "diced_tomatoes", "good_substitute"),
    ("black_beans", "pinto_beans", "good_substitute"),
    ("black_beans", "kidney_beans", "good_substitute"),
    ("kidney_beans", "pinto_beans", "good_substitute"),
    ("cannellini_beans", "great_northern_beans", "strong_substitute"),
    ("cannellini_beans", "navy_beans", "strong_substitute"),
    ("chickpeas", "garbanzo_beans", "exact_equivalent"),
    ("chickpeas", "white_beans", "acceptable_substitute"),
    ("brown_lentils", "green_lentils", "strong_substitute"),
    ("chicken_broth", "chicken_stock", "exact_equivalent"),
    ("chicken_broth", "vegetable_broth", "good_substitute"),
    ("chicken_broth", "beef_broth", "acceptable_substitute"),
    ("beef_broth", "beef_stock", "exact_equivalent"),
    ("beef_broth", "vegetable_broth", "good_substitute"),
    ("vegetable_broth", "vegetable_stock", "exact_equivalent"),
    ("white_wine_vinegar", "champagne_vinegar", "strong_substitute"),
    ("white_wine_vinegar", "rice_vinegar", "good_substitute"),
    ("white_wine_vinegar", "apple_cider_vinegar", "good_substitute"),
    ("apple_cider_vinegar", "rice_vinegar", "good_substitute"),
    ("lemon_juice", "lime_juice", "good_substitute"),
    ("granulated_sugar", "superfine_sugar", "exact_equivalent"),
    ("granulated_sugar", "light_brown_sugar", "good_substitute"),
    ("granulated_sugar", "raw_sugar", "good_substitute"),
    ("light_brown_sugar", "dark_brown_sugar", "strong_substitute"),
    ("honey", "maple_syrup", "good_substitute"),
    ("honey", "agave", "good_substitute"),
    ("fresh_oregano", "dried_oregano", "strong_substitute"),
    ("fresh_thyme", "dried_thyme", "strong_substitute"),
    ("fresh_rosemary", "dried_rosemary", "strong_substitute"),
    ("spinach", "chard", "good_substitute"),
    ("spinach", "kale", "good_substitute"),
    ("kale", "collard_greens", "good_substitute"),
    ("romaine", "green_leaf_lettuce", "strong_substitute"),
    ("romaine", "iceberg", "good_substitute"),
    ("arugula", "lettuce", "acceptable_substitute"),
    ("broccoli", "broccolini", "strong_substitute"),
    ("broccoli", "cauliflower", "good_substitute"),
    ("russet_potatoes", "yukon_gold_potatoes", "strong_substitute"),
    ("sweet_potatoes", "yams", "strong_substitute"),
    ("carrots", "parsnips", "acceptable_substitute"),
    ("red_bell_pepper", "yellow_bell_pepper", "strong_substitute"),
    ("red_bell_pepper", "orange_bell_pepper", "strong_substitute"),
    ("yellow_bell_pepper", "orange_bell_pepper", "strong_substitute"),
    ("green_bell_pepper", "red_bell_pepper", "good_substitute"),
    ("green_bell_pepper", "yellow_bell_pepper", "good_substitute"),
    ("white_mushrooms", "cremini_mushrooms", "strong_substitute"),
    ("cremini_mushrooms", "portobello_mushrooms", "strong_substitute"),
    ("shiitake_mushrooms", "white_mushrooms", "acceptable_substitute"),
]:
    add_pair(CULINARY_SUBSTITUTION_PAIRS, left, right, tier)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "low_moisture_mozzarella", "fresh_mozzarella", "good_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "fresh_garlic", "jarred_minced_garlic", "strong_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "fresh_garlic", "garlic_paste", "strong_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "fresh_garlic", "garlic_powder", "acceptable_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "garlic_powder", "fresh_garlic", "good_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "tomato_paste", "tomato_sauce", "acceptable_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "cornstarch", "all_purpose_flour", "acceptable_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "fresh_parsley", "dried_parsley", "good_substitute", bidirectional=False)
add_pair(CULINARY_SUBSTITUTION_PAIRS, "fresh_basil", "dried_basil", "good_substitute", bidirectional=False)


CULINARY_FAMILY_CEILINGS = {
    "cheese:fresh_spreadable": SUBSTITUTION_SCORES["acceptable_substitute"],
    "cheese:mild_melting": SUBSTITUTION_SCORES["acceptable_substitute"],
    "cheese:hard_grating": SUBSTITUTION_SCORES["acceptable_substitute"],
    "rice:short_medium": SUBSTITUTION_SCORES["good_substitute"],
    "pasta:long": SUBSTITUTION_SCORES["good_substitute"],
    "pasta:short_tubular": SUBSTITUTION_SCORES["good_substitute"],
    "pasta:small": SUBSTITUTION_SCORES["good_substitute"],
    "beans:white": SUBSTITUTION_SCORES["strong_substitute"],
    "vegetable:leafy_cooking": SUBSTITUTION_SCORES["good_substitute"],
    "vegetable:salad_greens": SUBSTITUTION_SCORES["acceptable_substitute"],
    "vegetable:cruciferous": SUBSTITUTION_SCORES["good_substitute"],
    "vegetable:bell_pepper": SUBSTITUTION_SCORES["good_substitute"],
    "vegetable:mushrooms": SUBSTITUTION_SCORES["acceptable_substitute"],
}


def detect_culinary_type(text: str, profile: IngredientProfile) -> None:
    if profile.family == "prepared meal" or profile.category in {"prepared", "bakery", "snacks", "beverage", "household", "baby", "pet"}:
        return
    if text_has(text, r"\bneufch[aâ]tel\b|\bneufchatel\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "neufchatel"
    elif text_has(text, r"\bcream cheese\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "cream_cheese"
    elif text_has(text, r"\bmascarpone\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "mascarpone"
    elif text_has(text, r"\bricotta\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "ricotta"
    elif text_has(text, r"\bcottage cheese\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "cottage_cheese"
    elif text_has(text, r"\bfarmer'?s? cheese\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "farmer_cheese"
    elif text_has(text, r"\bmonterey jack\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "monterey_jack"
    elif text_has(text, r"\bcolby jack\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "colby_jack"
    elif text_has(text, r"\bcolby\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "colby"
    elif text_has(text, r"\bsharp cheddar\b|\bextra sharp cheddar\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "sharp_cheddar"
    elif text_has(text, r"\bmedium cheddar\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "medium_cheddar"
    elif text_has(text, r"\bmild cheddar\b|\bcheddar\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "mild_cheddar"
    elif text_has(text, r"\bfresh mozzarella\b|\bmozzarella fresca\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "fresh_mozzarella"
    elif text_has(text, r"\blow[-\s]?moisture mozzarella\b|\bshredded mozzarella\b|\bmozzarella\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "low_moisture_mozzarella"
    elif text_has(text, r"\bprovolone\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "provolone"
    elif text_has(text, r"\bburrata\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "burrata"
    elif text_has(text, r"\bparmigiano(?: reggiano)?\b|\bparmesan\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "parmesan"
    elif text_has(text, r"\bgrana padano\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "grana_padano"
    elif text_has(text, r"\bpecorino(?: romano)?\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "pecorino_romano"
    elif text_has(text, r"\baged asiago\b|\basiago\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "aged_asiago"
    elif text_has(text, r"\bswiss\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "swiss"
    elif text_has(text, r"\bemmental\b|\bemmentaler\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "emmental"
    elif text_has(text, r"\bgruy[eè]re\b|\bgruyere\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "gruyere"
    elif text_has(text, r"\bjarlsberg\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "jarlsberg"
    elif text_has(text, r"\bfeta\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "feta"
    elif text_has(text, r"\bgoat cheese\b|\bchevre\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "goat_cheese"
    elif text_has(text, r"\bqueso fresco\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "queso_fresco"
    elif text_has(text, r"\bcotija\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"; profile.culinary_type = "cotija"
    elif text_has(text, r"\bblue cheese\b|\bgorgonzola\b|\broquefort\b|\bstilton\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"
        profile.culinary_type = "gorgonzola" if "gorgonzola" in text else "roquefort" if "roquefort" in text else "stilton" if "stilton" in text else "blue_cheese"

    if profile.family == "milk":
        if profile.milk_kind == "evaporated milk":
            profile.culinary_type = "evaporated_milk"
        elif profile.milk_kind == "condensed milk":
            profile.culinary_type = "sweetened_condensed_milk"
        elif profile.fat_percent == "2 percent":
            profile.culinary_type = "2_percent_milk"
        elif profile.fat_percent == "1 percent":
            profile.culinary_type = "1_percent_milk"
        elif profile.fat_level == "fat-free":
            profile.culinary_type = "skim_milk"
        elif profile.fat_level == "whole":
            profile.culinary_type = "whole_milk"
    if profile.family == "heavy cream":
        profile.culinary_type = "whipping_cream" if text_has(text, r"\bwhipping cream\b") else "heavy_cream"
    elif text_has(text, r"\blight cream\b"):
        profile.family = "half-and-half"; profile.category = profile.category or "dairy"; profile.culinary_type = "light_cream"
    elif profile.family == "half-and-half":
        profile.culinary_type = "half_and_half"
    elif text_has(text, r"\bcr[eè]me fra[iî]che\b|\bcreme fraiche\b"):
        profile.family = "sour cream"; profile.category = profile.category or "dairy"; profile.culinary_type = "creme_fraiche"
    elif profile.family == "sour cream":
        profile.culinary_type = "sour_cream"
    elif profile.family == "buttermilk":
        profile.culinary_type = "buttermilk"
    elif profile.family == "butter":
        profile.culinary_type = "butter"
    elif profile.family == "margarine":
        profile.culinary_type = "plant_butter" if text_has(text, r"\bplant\b|\bvegan\b") else "margarine"
    elif profile.family == "olive oil":
        profile.culinary_type = "olive_oil"
    elif profile.family == "cooking oil":
        if text_has(text, r"\bcanola\b"):
            profile.culinary_type = "canola_oil"
        elif text_has(text, r"\bsunflower\b"):
            profile.culinary_type = "sunflower_oil"
        elif text_has(text, r"\bgrapeseed\b"):
            profile.culinary_type = "grapeseed_oil"
        elif text_has(text, r"\bavocado\b"):
            profile.culinary_type = "avocado_oil"
        else:
            profile.culinary_type = "neutral_oil"
    elif profile.family == "yogurt":
        if profile.flavor in {None, "plain"}:
            profile.culinary_type = "plain_greek_yogurt" if text_has(text, r"\bgreek\b") else "plain_yogurt"
    elif profile.family == "kefir":
        profile.culinary_type = "plain_kefir" if text_has(text, r"\bplain\b") or not profile.flavor else None
    elif profile.family == "flour":
        profile.culinary_type = (profile.flour_type or "").replace("-", "_").replace(" ", "_") or None
        if text_has(text, r"\bap flour\b|\ba\.p\. flour\b"):
            profile.culinary_type = "all_purpose_flour"
        if text_has(text, r"\bpastry flour\b"):
            profile.culinary_type = "pastry_flour"
        elif text_has(text, r"\bself[-\s]?rising flour\b"):
            profile.culinary_type = "self_rising_flour"
        elif text_has(text, r"\bhigh[-\s]?gluten flour\b"):
            profile.culinary_type = "high_gluten_flour"
    elif profile.family == "corn starch":
        profile.culinary_type = "cornstarch"
    elif text_has(text, r"\bpotato starch\b|\barrowroot\b|\btapioca starch\b"):
        profile.family = "starch"; profile.category = profile.category or "pantry"
        profile.culinary_type = "potato_starch" if "potato" in text else "arrowroot" if "arrowroot" in text else "tapioca_starch"
    elif profile.family == "rice":
        for rice_type, pattern in {
            "jasmine_rice": r"\bjasmine\b",
            "basmati_rice": r"\bbasmati\b",
            "arborio_rice": r"\barborio\b|\brisotto rice\b",
            "carnaroli_rice": r"\bcarnaroli\b",
            "brown_rice": r"\bbrown rice\b",
            "short_medium_rice": r"\bshort[-\s]?grain\b|\bmedium[-\s]?grain\b|\bsushi rice\b",
            "long_grain_white_rice": r"\blong[-\s]?grain\b|\bwhite rice\b|\brice\b",
        }.items():
            if text_has(text, pattern):
                profile.culinary_type = rice_type
                break
    elif profile.family == "pasta":
        for pasta_type, pattern in {
            "spaghetti": r"\bspaghetti\b",
            "linguine": r"\blinguine\b",
            "fettuccine": r"\bfettuccine\b",
            "bucatini": r"\bbucatini\b",
            "penne": r"\bpenne\b",
            "rigatoni": r"\brigatoni\b",
            "ziti": r"\bziti\b",
            "mostaccioli": r"\bmostaccioli\b",
            "elbow_macaroni": r"\belbows?\b|\bmacaroni\b",
            "small_shells": r"\bsmall shells?\b",
            "ditalini": r"\bditalini\b",
            "lasagna_sheets": r"\blasagna\b",
            "stuffed_pasta": r"\bravioli\b|\btortellini\b|\btortelloni\b",
            "gnocchi": r"\bgnocchi\b",
            "fresh_pasta": r"\bfresh pasta\b",
        }.items():
            if text_has(text, pattern):
                profile.culinary_type = pasta_type
                break
    elif profile.family == "breadcrumbs":
        profile.culinary_type = "panko" if text_has(text, r"\bpanko\b") else "crushed_crackers" if text_has(text, r"\bcrushed crackers?\b") else "breadcrumbs"
    elif profile.family == "onion":
        if text_has(text, r"\bwhite onion\b"):
            profile.culinary_type = "white_onion"
        elif text_has(text, r"\bred onion\b"):
            profile.culinary_type = "red_onion"
        elif text_has(text, r"\bshallots?\b"):
            profile.culinary_type = "shallot"
        else:
            profile.culinary_type = "yellow_onion"
    elif profile.family == "green onion":
        profile.culinary_type = "green_onion"
    elif text_has(text, r"\bchives?\b"):
        profile.family = "green onion"; profile.category = profile.category or "produce"; profile.culinary_type = "chives"
    elif profile.family == "seasoning" and text_has(text, r"\bgarlic salt\b"):
        profile.culinary_type = "garlic_salt"
    elif profile.family == "seasoning" and text_has(text, r"\bgarlic powder\b|\bgranulated garlic\b"):
        profile.culinary_type = "granulated_garlic" if "granulated" in text else "garlic_powder"
    elif text_has(text, r"\bgarlic paste\b|\bjarred minced garlic\b|\bminced garlic\b|\bgarlic\b"):
        profile.family = "garlic"; profile.category = profile.category or "produce"
        profile.culinary_type = "garlic_paste" if "paste" in text else "jarred_minced_garlic" if "jarred" in text or "minced" in text else "fresh_garlic"
    elif profile.family == "tomato product":
        profile.culinary_type = (profile.tomato_type or "").replace(" ", "_") or None
        if text_has(text, r"\btomato puree\b"):
            profile.culinary_type = "tomato_puree"
        elif text_has(text, r"\bfresh tomatoes?\b|\bgrape tomatoes?\b|\bcherry tomatoes?\b") or profile.category == "produce":
            profile.family = "fresh tomato"; profile.category = profile.category or "produce"; profile.culinary_type = "fresh_tomatoes"
    elif profile.family == "fresh tomato":
        profile.culinary_type = "fresh_tomatoes"
    elif text_has(text, r"\bchickpeas?\b|\bgarbanzo\b"):
        profile.family = "beans"; profile.category = profile.category or "pantry"
        profile.culinary_type = "garbanzo_beans" if text_has(text, r"\bgarbanzo\b") else "chickpeas"
    elif profile.family == "beans":
        for bean_type, pattern in {
            "black_beans": r"\bblack beans?\b",
            "pinto_beans": r"\bpinto beans?\b",
            "kidney_beans": r"\bkidney beans?\b",
            "cannellini_beans": r"\bcannellini\b",
            "great_northern_beans": r"\bgreat northern\b",
            "navy_beans": r"\bnavy beans?\b",
            "chickpeas": r"\bchickpeas?\b",
            "garbanzo_beans": r"\bgarbanzo\b",
            "white_beans": r"\bwhite beans?\b",
        }.items():
            if text_has(text, pattern):
                profile.culinary_type = bean_type
                break
    elif text_has(text, r"\blentils?\b"):
        profile.family = "lentils"; profile.category = profile.category or "pantry"
        profile.culinary_type = "red_lentils" if text_has(text, r"\bred|yellow\b") else "green_lentils" if "green" in text else "brown_lentils" if "brown" in text else None
    elif profile.family == "broth":
        if profile.broth_species and profile.broth_type:
            profile.culinary_type = f"{profile.broth_species}_{profile.broth_type}"
    elif profile.family == "vinegar":
        for acid_type, pattern in {
            "white_wine_vinegar": r"\bwhite wine vinegar\b",
            "champagne_vinegar": r"\bchampagne vinegar\b",
            "rice_vinegar": r"\brice vinegar\b",
            "apple_cider_vinegar": r"\bapple cider vinegar\b",
            "distilled_white_vinegar": r"\bdistilled white vinegar\b|\bwhite vinegar\b",
        }.items():
            if text_has(text, pattern):
                profile.culinary_type = acid_type
                break
    elif profile.family in {"lemon juice", "lime juice"}:
        profile.culinary_type = profile.family.replace(" ", "_")
    elif profile.family in {"sugar", "brown sugar", "powdered sugar"}:
        if text_has(text, r"\bpowdered sugar\b|\bconfectioners'? sugar\b"):
            profile.family = "powdered sugar"; profile.culinary_type = "powdered_sugar"
        elif text_has(text, r"\bdark brown sugar\b"):
            profile.family = "brown sugar"; profile.culinary_type = "dark_brown_sugar"
        elif text_has(text, r"\blight brown sugar\b|\bbrown sugar\b"):
            profile.family = "brown sugar"; profile.culinary_type = "light_brown_sugar"
        elif text_has(text, r"\bcaster sugar\b|\bsuperfine sugar\b"):
            profile.family = "sugar"; profile.culinary_type = "superfine_sugar"
        else:
            profile.family = "sugar"; profile.culinary_type = "granulated_sugar"
    elif profile.family == "honey":
        profile.culinary_type = "honey"
    elif text_has(text, r"\bmaple syrup\b|\bagave\b"):
        profile.family = "sweetener"; profile.category = profile.category or "pantry"; profile.culinary_type = "maple_syrup" if "maple" in text else "agave"
    elif profile.family in {"parsley", "basil", "oregano", "thyme", "rosemary"}:
        prefix = "dried" if profile.freshness == "dried" else "fresh"
        profile.culinary_type = f"{prefix}_{profile.family}"
    elif profile.family in COMMON_PRODUCE_CANONICALS or profile.category == "produce":
        if text_has(text, r"\bfrozen\b|\bfrozen chopped\b"):
            profile.freshness = profile.freshness or "frozen"
        produce_patterns = {
            "spinach": r"\bspinach\b",
            "chard": r"\bchard\b|\bswiss chard\b",
            "kale": r"\bkale\b",
            "collard_greens": r"\bcollards?\b|\bcollard greens?\b",
            "romaine": r"\bromaine\b",
            "green_leaf_lettuce": r"\bgreen leaf lettuce\b",
            "iceberg": r"\biceberg\b",
            "arugula": r"\barugula\b|\brocket\b",
            "lettuce": r"\blettuce\b",
            "broccolini": r"\bbroccolini\b",
            "broccoli": r"\bbroccoli\b",
            "cauliflower": r"\bcauliflower\b",
            "russet_potatoes": r"\brusset\b",
            "yukon_gold_potatoes": r"\byukon gold\b",
            "sweet_potatoes": r"\bsweet potatoes?\b",
            "yams": r"\byams?\b",
            "potatoes": r"\bpotatoes?\b",
            "carrots": r"\bcarrots?\b",
            "parsnips": r"\bparsnips?\b",
            "red_bell_pepper": r"\bred (?:bell |sweet )?peppers?\b",
            "yellow_bell_pepper": r"\byellow (?:bell |sweet )?peppers?\b",
            "orange_bell_pepper": r"\borange (?:bell |sweet )?peppers?\b",
            "green_bell_pepper": r"\bgreen (?:bell |sweet )?peppers?\b",
            "bell_pepper": r"\bbell peppers?\b|\bsweet peppers?\b",
            "cremini_mushrooms": r"\bcremini\b|\bbaby bella\b",
            "portobello_mushrooms": r"\bportobello\b",
            "shiitake_mushrooms": r"\bshiitake\b",
            "white_mushrooms": r"\bwhite mushrooms?\b|\bbutton mushrooms?\b|\bmushrooms?\b",
            "leek": r"\bleeks?\b",
        }
        for produce_type, pattern in produce_patterns.items():
            if text_has(text, pattern):
                if produce_type in {"red_bell_pepper", "yellow_bell_pepper", "orange_bell_pepper", "green_bell_pepper", "bell_pepper"}:
                    profile.family = "bell pepper"; profile.produce_type = "bell pepper"
                elif produce_type == "leek":
                    profile.family = "leek"; profile.produce_type = "leek"
                elif produce_type == "broccolini":
                    profile.family = "broccoli"; profile.produce_type = "broccolini"
                elif produce_type in {"chard", "collard_greens"}:
                    profile.family = "greens"; profile.produce_type = produce_type
                elif produce_type in {"white_mushrooms", "cremini_mushrooms", "portobello_mushrooms", "shiitake_mushrooms"}:
                    profile.family = "mushrooms"; profile.produce_type = produce_type
                elif produce_type in {"russet_potatoes", "yukon_gold_potatoes", "sweet_potatoes", "yams", "potatoes"}:
                    profile.family = "potatoes"; profile.produce_type = produce_type
                elif produce_type in {"carrots", "parsnips"}:
                    profile.family = "root vegetable"; profile.produce_type = produce_type
                else:
                    profile.family = produce_type.split("_")[0] if produce_type in {"spinach", "kale", "arugula", "lettuce", "broccoli", "cauliflower"} else profile.family
                    profile.produce_type = produce_type
                profile.category = profile.category or "produce"
                profile.culinary_type = produce_type
                break


def detect_beef_cut(text: str) -> str | None:
    for cut, pattern in BEEF_CUT_PATTERNS:
        if text_has(text, pattern):
            return cut
    return None


def detect_juice_produce_type(text: str) -> str | None:
    if not text_has(text, r"\bjuice\b"):
        return None
    for produce_type in JUICE_PRODUCE_TYPES:
        if text_has(text, rf"\b{produce_type}\b"):
            return produce_type
    return None


def is_slow_cooking_beef_cut_substitution(query: IngredientProfile, product: IngredientProfile) -> bool:
    if query.family != "meat cut" or product.family != "meat cut":
        return False
    if (query.meat_species or product.meat_species) != "beef":
        return False
    if not query.meat_cut or not product.meat_cut or query.meat_cut == product.meat_cut:
        return False
    if query.meat_cut == "steak" and "steak" in product.meat_cut:
        return False
    if (
        text_has(query.raw_text, r"\broast\b")
        and query.meat_cut in ROAST_COMPATIBLE_BEEF_CUTS
        and product.meat_cut in ROAST_COMPATIBLE_BEEF_CUTS
    ):
        return True
    return product.meat_cut in BEEF_CUT_SUBSTITUTES.get(query.meat_cut, set())


def beef_cut_substitution_signal(query: IngredientProfile, product: IngredientProfile) -> CompatibilitySignal | None:
    if query.family != "meat cut" or product.family != "meat cut":
        return None
    if (query.meat_species or product.meat_species) != "beef":
        return None
    if not query.meat_cut or not product.meat_cut or query.meat_cut == product.meat_cut:
        return None
    if query.meat_cut == "steak" and "steak" in product.meat_cut:
        return None
    if is_slow_cooking_beef_cut_substitution(query, product):
        return CompatibilitySignal("meat_cut", STRONG_PENALTY, "raw beef slow-cooking cut differs")
    return CompatibilitySignal("meat_cut", HARD_REJECT, "meat cut differs")


def profile_from_query(ingredient_text: str, overrides: OverrideStore | None = None) -> tuple[IngredientProfile, dict[str, Any]]:
    parsed = parse_ingredient(ingredient_text)
    base_text = " ".join(
        part
        for part in (
            parsed.fat_level,
            parsed.salted_status,
            parsed.sweetened_status,
            parsed.freshness,
            parsed.form,
            parsed.bone_status,
            parsed.skin_status,
            " ".join(parsed.dietary_qualifiers),
            parsed.canonical_name,
        )
        if part
    )
    normalized = normalize_text(base_text)
    if overrides:
        normalized = overrides.normalized_alias(normalized)
    canonical = canonical_for_product(normalized) or apply_alias(parsed.canonical_name)
    profile = classify_identity(
        normalized,
        canonical=canonical,
        category=None,
        form=parsed.form,
        freshness=parsed.freshness,
        fat_level=parsed.fat_level,
        salted_status=parsed.salted_status,
        sweetened_status=parsed.sweetened_status,
        brand=parsed.brand,
        dietary=set(parsed.dietary_qualifiers),
        raw_text=ingredient_text,
    )
    if profile.tomato_type:
        profile.normalized_signature = profile.tomato_type
    elif profile.broth_species and profile.broth_type:
        profile.normalized_signature = f"{profile.broth_species} {profile.broth_type}"
    elif profile.culinary_type:
        profile.normalized_signature = profile.culinary_type.replace("_", " ")
    else:
        profile.normalized_signature = normalize_text(normalized)
    return profile, parsed.to_dict()


def profile_from_feature(feature: dict[str, Any]) -> IngredientProfile:
    text = feature.get("normalized_name") or ""
    return classify_identity(
        text,
        canonical=feature.get("canonical_name"),
        category=feature.get("category"),
        form=feature.get("form"),
        freshness=feature.get("freshness"),
        fat_level=feature.get("fat_level"),
        salted_status=feature.get("salted_status"),
        sweetened_status=feature.get("sweetened_status"),
        brand=feature.get("brand"),
        dietary=set(feature.get("dietary_attributes") or []),
        raw_text=feature.get("original_product_name") or text,
    )


def classify_identity(
    text: str,
    *,
    canonical: str | None,
    category: str | None,
    form: str | None = None,
    freshness: str | None = None,
    fat_level: str | None = None,
    salted_status: str | None = None,
    sweetened_status: str | None = None,
    brand: str | None = None,
    dietary: set[str] | None = None,
    raw_text: str = "",
) -> IngredientProfile:
    normalized = normalize_text(text)
    detection_text = normalize_text(" ".join(part for part in (normalized, raw_text) if part))
    normalized_raw_text = normalize_text(raw_text)
    canonical = canonical or canonical_for_product(normalized)
    canonical = normalize_text(canonical or "") or None
    family = canonical
    profile = IngredientProfile(
        normalized_signature=normalized,
        canonical=canonical,
        family=family,
        category=category,
        form=form,
        freshness=freshness,
        fat_level=normalize_fat(fat_level, normalized),
        fat_percent=detect_fat_percent(detection_text),
        salted_status=salted_status,
        sweetened_status=sweetened_status,
        brand=brand,
        dietary_requirements=set(dietary or set()),
        raw_text=raw_text,
    )
    if text_has(detection_text, r"\bno[-\s]?salt[-\s]?added\b"):
        profile.salted_status = "no-salt-added"
    elif text_has(detection_text, r"\breduced[-\s]?sodium\b|\blow[-\s]?sodium\b"):
        profile.salted_status = "reduced-sodium"
    if text_has(detection_text, r"\bno[-\s]?salt[-\s]?added\b") and text_has(detection_text, r"\bgreen beans?\b|\bbeans?\b"):
        profile.family = "beans"; profile.category = profile.category or "pantry"; profile.freshness = profile.freshness or "canned"
    if text_has(detection_text, r"\bpickles?\b|\bpickled\b"):
        profile.family = "pickles"; profile.category = profile.category or "pantry"; profile.freshness = "pickled"
    if text_has(detection_text, r"\bmilk chocolate\b|\bchocolate matzos?\b|\begg matzos?\b"):
        profile.family = "prepared meal"; profile.category = "prepared"
        profile.milk_kind = None

    if text_has(detection_text, r"\bkefir\b"):
        profile.family = "kefir"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\begg beaters?\b|\bliquid egg substitute\b|\begg substitute\b") and profile.family != "prepared meal":
        profile.family = "egg substitute"; profile.category = profile.category or "dairy"
    elif (text_has(detection_text, r"\beggs?\b|\begg yolks?\b|\begg whites?\b") or canonical == "eggs") and profile.family != "prepared meal":
        profile.family = "eggs"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\boat milk\b|\boatmilk\b"):
        profile.family = "milk"; profile.dairy_type = "plant"; profile.milk_kind = "oat milk"
    elif text_has(detection_text, r"\balmond milk\b|\balmondmilk\b"):
        profile.family = "milk"; profile.dairy_type = "plant"; profile.milk_kind = "almond milk"
    elif text_has(detection_text, r"\bsoy milk\b|\bsoymilk\b"):
        profile.family = "milk"; profile.dairy_type = "plant"; profile.milk_kind = "soy milk"
    elif text_has(detection_text, r"\bcoconut milk\b"):
        profile.family = "milk"; profile.dairy_type = "plant"; profile.milk_kind = "coconut milk"
    elif text_has(detection_text, r"\bevaporated(?:\s+[\w-]+){0,4}\s+milk\b"):
        profile.family = "milk"; profile.dairy_type = "dairy"; profile.milk_kind = "evaporated milk"
    elif text_has(detection_text, r"\bcondensed(?:\s+[\w-]+){0,4}\s+milk\b"):
        profile.family = "milk"; profile.dairy_type = "dairy"; profile.milk_kind = "condensed milk"
    elif text_has(detection_text, r"\bdry milk\b|\bpowdered milk\b"):
        profile.family = "milk"; profile.dairy_type = "dairy"; profile.milk_kind = "powdered milk"
    elif text_has(detection_text, r"\bmilk\b") and not text_has(detection_text, r"\bmilk chocolate\b"):
        profile.family = "milk"; profile.dairy_type = "dairy"; profile.milk_kind = "plain milk"
    if text_has(detection_text, r"\bchocolate milk\b|\bstrawberry milk\b|\bvanilla milk\b"):
        profile.form = "flavored"
    if "lactose-free" in detection_text or "lactaid" in detection_text:
        profile.dietary_requirements.add("lactose-free")
    if text_has(detection_text, r"\bmilk singles\b.*\bamerican\b|\bamerican\b.*\bmilk singles\b|\bamerican singles\b"):
        profile.family = "cheese"
        profile.category = "dairy"
        profile.milk_kind = None
        profile.dairy_type = None

    if text_has(detection_text, r"\bheavy cream\b"):
        profile.family = "heavy cream"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bhalf and half\b"):
        profile.family = "half-and-half"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bsour cream\b"):
        profile.family = "sour cream"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bice cream\b"):
        profile.family = "ice cream"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bwhipped topping\b|\breddi-wip\b"):
        profile.family = "whipped topping"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bmargarine\b|\bvegetable oil spread\b|\bplant butter\b|\bplant based oil spread\b|\bbuttery spread\b"):
        profile.family = "margarine"; profile.category = profile.category or "dairy"
        if text_has(detection_text, r"\bplant butter\b|\bplant based\b|\bvegan\b"):
            profile.dietary_requirements.add("vegan")
            profile.category = "pantry"
    elif text_has(detection_text, r"\bspreadable butter\b|\bbutter with .*oil\b"):
        profile.family = "butter blend"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bvegan butter\b"):
        profile.family = "margarine"; profile.category = "pantry"; profile.dietary_requirements.add("vegan")
    elif text_has(detection_text, r"\bbutter\b") and profile.family not in {"peanut butter", "pickles", "prepared meal"}:
        profile.family = "butter"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bbuttermilk\b"):
        profile.family = "buttermilk"; profile.category = profile.category or "dairy"

    if text_has(
        detection_text,
        r"\bsteak sauce\b|\bsteak house\b.*\bsauce\b|\bbeef marinade\b|\bbeef gravy\b|\bgravy granules\b|\bdressing\b|\bgravy\b",
    ) and not text_has(detection_text, r"\bsour cream\b"):
        profile.family = "sauce"; profile.category = profile.category or "pantry"
    if text_has(detection_text, r"\btoothpaste\b|\btoothbrush\b|\bmouthwash\b|\bdental\b|\bfloss\b"):
        profile.family = "oral care"; profile.category = "household"
    if text_has(detection_text, r"\bfacial tissues?\b|\btissues?\b|\bpaper towels?\b|\bnapkins?\b"):
        profile.family = "household"; profile.category = "household"
    if text_has(detection_text, r"\bgum\b|\bchewing gum\b|\bbreath mints?\b|\btic tac\b|\bice breakers\b"):
        profile.family = "candy"; profile.category = "snacks"
    if text_has(detection_text, r"\bdog food\b|\bcat food\b|\bdog treats?\b|\bcat treats?\b|\bmilk-bone\b|\bpurina\b|\bfriskies\b|\bfancy feast\b|\bmeow mix\b|\bpedigree\b|\bcesar\b"):
        profile.family = "pet food"; profile.category = "pet"
    if text_has(detection_text, r"\bsteak fries\b"):
        profile.family = "prepared meal"; profile.category = "prepared"
    if text_has(detection_text, r"\bhummus\b"):
        profile.family = "hummus"; profile.category = profile.category or "pantry"

    if text_has(detection_text, r"\balmond butter\b|\bcashew butter\b|\bsunflower butter\b"):
        profile.family = "nut butter"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bpeanut butter\b"):
        profile.family = "peanut butter"; profile.category = profile.category or "pantry"

    flour_patterns = {
        "corn flour": r"\bcorn\s+masa\s+flour\b|\bmasa\s+harina\b|\bmasa\s+flour\b|\bcorn flour\b",
        "all-purpose flour": r"\ball[-\s]?purpose flour\b|\bplain flour\b|\bap flour\b|\ba\.p\. flour\b",
        "bread flour": r"\bbread flour\b",
        "cake flour": r"\bcake flour\b",
        "almond flour": r"\balmond flour\b",
        "coconut flour": r"\bcoconut flour\b",
        "whole wheat flour": r"\bwhole wheat flour\b",
    }
    for flour_type, pattern in flour_patterns.items():
        if text_has(detection_text, pattern) or canonical == flour_type:
            profile.family = "corn flour" if flour_type == "corn flour" else "flour"
            profile.flour_type = flour_type
    if profile.family != "flour" and text_has(detection_text, r"\bflour\b"):
        profile.family = "flour"
        profile.category = profile.category or "pantry"
    if "gluten-free" in detection_text or "gluten free" in detection_text:
        profile.dietary_requirements.add("gluten-free")
    if "nut-free" in detection_text or "nut free" in detection_text:
        profile.dietary_requirements.add("nut-free")

    tomato_patterns = {
        "tomato paste": r"\btomato paste\b",
        "tomato sauce": r"\btomato sauce\b",
        "crushed tomatoes": r"\bcrushed tomatoes\b|\btomatoes crushed\b",
        "diced tomatoes": r"\bdiced tomatoes\b|\btomatoes diced\b",
        "stewed tomatoes": r"\bstewed tomatoes\b|\btomatoes stewed\b",
        "tomatoes": r"\bcanned tomatoes\b|\bwhole peeled tomatoes\b|\bcan\b.*\btomatoes\b|\btomatoes\b.*\bcan\b",
        "pasta sauce": r"\bpasta sauce\b|\bspaghetti sauce\b|\bmarinara\b",
    }
    for tomato_type, pattern in tomato_patterns.items():
        if (text_has(detection_text, pattern) or canonical == tomato_type) and (
            tomato_type != "tomatoes" or not profile.tomato_type
        ):
            profile.family = "tomato product"; profile.tomato_type = tomato_type

    broth_species = detect_broth_species(detection_text)
    if text_has(detection_text, r"\b(?:chicken|vegetable|beef|seafood|turkey) broth\b"):
        profile.family = "broth"; profile.broth_type = "broth"; profile.broth_species = broth_species
    elif text_has(detection_text, r"\b(?:chicken|vegetable|beef|seafood|turkey) stock\b"):
        profile.family = "broth"; profile.broth_type = "stock"; profile.broth_species = broth_species
    elif text_has(detection_text, r"\bbroth\b"):
        profile.family = "broth"; profile.broth_type = "broth"
    elif text_has(detection_text, r"\bstock\b"):
        profile.family = "broth"; profile.broth_type = "stock"
    elif text_has(detection_text, r"\bbouillon\b"):
        profile.family = "bouillon"; profile.broth_type = "bouillon"; profile.broth_species = broth_species
    elif text_has(detection_text, r"\bconsomm[eé]\b|\bconsomme\b"):
        profile.family = "broth"; profile.broth_type = "consomme"; profile.broth_species = broth_species
    elif text_has(detection_text, r"\bsoup\b") and not text_has(detection_text, r"\bsoup meat\b"):
        profile.family = "soup"; profile.broth_type = "soup"
        if text_has(detection_text, r"\bcream(?:y)? of chicken soup\b|\bcream of chicken\b"):
            profile.soup_type = "cream of chicken"
        elif text_has(detection_text, r"\bcream(?:y)? of mushroom soup\b|\bcream of mushroom\b"):
            profile.soup_type = "cream of mushroom"
        elif text_has(detection_text, r"\bcream(?:y)? tomato soup\b|\btomato soup\b"):
            profile.soup_type = "tomato"

    if text_has(detection_text, r"\bbacon\b") and not text_has(detection_text, r"\bbean with bacon\b"):
        profile.family = "bacon"; profile.category = profile.category or "meat"; profile.meat_species = "pork"
    elif prepared_meat_product_text(detection_text):
        profile.family = "prepared meal"; profile.category = "prepared"
    elif text_has(
        detection_text,
        r"\bbeef\s+(?:franks?|frankfurters?|hot dogs?|wieners?|knockwurst|bologna|salami)\b|\b(?:franks?|frankfurters?|hot dogs?|wieners?|knockwurst|bologna|salami)\b.*\bbeef\b",
    ):
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bbeef tongue\b|\btongue\b.*\bbeef\b"):
        profile.family = "organ meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"; profile.meat_cut = "tongue"
    elif text_has(detection_text, r"\bbeef jerky\b|\bjerky\b.*\bbeef\b"):
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif deli_processed_beef_text(detection_text) or normalized == "roast beef":
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bbeef liver\b|\bfresh beef liver\b"):
        profile.family = "organ meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"; profile.meat_cut = "liver"
    elif profile.family in {"sauce", "pet food", "prepared meal", "marinade"}:
        pass
    elif text_has(detection_text, r"\bbeef (?:feet|foot|marrow bones?|neck bones?|back bones?|bones\b(?!\s*in))\b|\b(?:feet|foot|marrow bones?|neck bones?|back bones?)\b.*\bbeef\b"):
        profile.family = "meat bones"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif (beef_cut := detect_beef_cut(detection_text)) and (
        text_has(detection_text, r"\bbeef\b|\bsteak\b|\bbrisket\b|\boxtails?\b|\bshort ribs?\b|\bflanken\b")
        or beef_cut in {"oxtail", "brisket", "short ribs"}
    ):
        profile.family = "meat cut"; profile.category = profile.category or "meat"; profile.meat_species = "beef"; profile.meat_cut = beef_cut
    elif text_has(detection_text, r"\blamb\s+(?:for\s+)?stew\b|\blamb\s+stew(?:ing)?\s+meat\b|\bstew(?:ing)?\s+lamb\b|\blamb stew meat\b|\bstew lamb\b"):
        profile.family = "meat cut"; profile.category = profile.category or "meat"; profile.meat_species = "lamb"; profile.meat_cut = "stew meat"
    elif text_has(detection_text, r"\bstew(?:ing)?\s+meat\b|\bstew meat\b"):
        profile.family = "meat cut"; profile.category = profile.category or "meat"; profile.meat_cut = "stew meat"
    elif text_has(detection_text, r"\bground beef\b|\bbeef,?\s+ground\b"):
        profile.family = "ground meat"; profile.meat_species = "beef"; profile.ground = True
    elif text_has(detection_text, r"\bbeef burgers?\b|\bground beef burgers?\b"):
        profile.family = "ground meat"; profile.meat_species = "beef"; profile.ground = True
    elif text_has(detection_text, r"\bbeef sausage\b"):
        profile.family = "sausage"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bpork sausage\b|\bpork sausages\b"):
        profile.family = "sausage"; profile.category = profile.category or "meat"; profile.meat_species = "pork"
    elif text_has(detection_text, r"\bchicken sausage\b|\bchicken sausages\b"):
        profile.family = "sausage"; profile.category = profile.category or "meat"; profile.meat_species = "chicken"
    elif text_has(detection_text, r"\bsausage\b"):
        profile.family = "sausage"; profile.category = profile.category or "meat"
    elif text_has(detection_text, r"\bground turkey\b"):
        profile.family = "ground meat"; profile.meat_species = "turkey"; profile.ground = True
    elif text_has(detection_text, r"\bpork\b"):
        profile.family = "pork"; profile.category = profile.category or "meat"; profile.meat_species = "pork"
    elif text_has(detection_text, r"\bham\b"):
        profile.family = "ham"; profile.category = profile.category or "meat"; profile.meat_species = "pork"
    elif text_has(detection_text, r"\bswordfish\b|\bsalmon\b|\bfish steak\b"):
        profile.family = "fish"; profile.category = profile.category or "meat"; profile.meat_species = "fish"
    elif text_has(detection_text, r"\bground lamb\b|\bminced lamb\b"):
        profile.family = "ground meat"; profile.category = profile.category or "meat"; profile.meat_species = "lamb"; profile.ground = True
    elif text_has(detection_text, r"\blamb\b"):
        profile.category = profile.category or "meat"; profile.meat_species = "lamb"
        if text_has(detection_text, r"\bchops?\b|\bsteaks?\b|\bshoulder\b|\bbreast\b|\briblets?\b|\bhindshank\b|\bshank\b"):
            profile.family = "meat cut"
            if text_has(detection_text, r"\bchops?\b"):
                profile.meat_cut = "chop"
            elif text_has(detection_text, r"\bsteaks?\b"):
                profile.meat_cut = "steak"
            elif text_has(detection_text, r"\bshank\b|\bhindshank\b"):
                profile.meat_cut = "shank"
            elif text_has(detection_text, r"\bbreast\b"):
                profile.meat_cut = "breast"
        else:
            profile.family = "lamb"
    elif text_has(detection_text, r"\bchicken breast\b"):
        profile.family = "meat cut"; profile.category = profile.category or "meat"; profile.meat_species = "chicken"; profile.meat_cut = "breast"
    elif text_has(detection_text, r"\bchicken thighs?\b"):
        profile.family = "meat cut"; profile.category = profile.category or "meat"; profile.meat_species = "chicken"; profile.meat_cut = "thigh"
    elif text_has(detection_text, r"\bchicken\b") and profile.family not in {"broth", "stock", "soup", "bouillon"}:
        profile.family = "chicken"; profile.category = profile.category or "meat"; profile.meat_species = "chicken"
    elif text_has(detection_text, r"\btuna\b") and text_has(detection_text, r"\bcan|canned\b"):
        profile.family = "tuna"; profile.meat_species = "tuna"; profile.freshness = profile.freshness or "canned"
    elif text_has(detection_text, r"\btuna\b"):
        profile.family = "tuna"; profile.meat_species = "tuna"
    elif text_has(detection_text, r"\bbeef\b") and profile.family not in {
        "broth",
        "stock",
        "soup",
        "bouillon",
        "sausage",
        "meat cut",
        "ground meat",
        "sauce",
        "processed meat",
        "organ meat",
        "meat bones",
        "prepared meal",
        "pet food",
    }:
        profile.family = "beef"; profile.category = profile.category or "meat"; profile.meat_species = "beef"

    if text_has(detection_text, r"\bfresh\b"):
        profile.freshness = "fresh"
    elif text_has(detection_text, r"\bdried\b|\bflakes\b"):
        profile.freshness = "dried"
    elif text_has(detection_text, r"\bfrozen\b|\bsteamfresh\b"):
        profile.freshness = "frozen"
    elif text_has(detection_text, r"\bcanned\b|\bcan\b"):
        profile.freshness = "canned"
    if profile.family in {"parsley", "basil", "oregano", "thyme", "rosemary"} and text_has(
        detection_text, r"\bmccormick\b|\bsimply organic\b|\bspice\b|\bflakes\b"
    ):
        profile.freshness = "dried"
    if profile.family == "tomato product" and text_has(
        detection_text, r"\bcanned tomatoes\b|\bwhole peeled tomatoes\b|\bcrushed tomatoes\b|\bdiced tomatoes\b|\bstewed tomatoes\b"
    ):
        profile.freshness = "canned"

    if text_has(normalized, r"\bactive dry yeast\b"):
        profile.family = "yeast"; profile.form = "active dry"
    elif text_has(normalized, r"\binstant yeast\b"):
        profile.family = "yeast"; profile.form = "instant"
    elif text_has(normalized, r"\bnutritional yeast\b"):
        profile.family = "nutritional yeast"; profile.form = "nutritional"
    elif canonical == "yeast":
        profile.family = "yeast"

    if text_has(detection_text, r"\bpuff pastry\b|\bpastry dough\b|\bfrozen sheets pastry dough\b|\bpastry sheets?\b"):
        profile.family = "puff pastry"; profile.category = profile.category or "pantry"
        if text_has(detection_text, r"\bfrozen\b"):
            profile.freshness = profile.freshness or "frozen"
    if text_has(normalized, r"\bpancake mix\b") and not text_has(normalized, r"\bpotato pancake\b|\blatkes?\b"):
        profile.family = "pancake mix"
    elif text_has(normalized, r"\bpotato pancake\b|\blatkes?\b"):
        profile.family = "potato pancake mix"

    if text_has(normalized, r"\bcurry powder\b"):
        profile.family = "curry powder"; profile.category = profile.category or "pantry"
    if text_has(detection_text, r"\btipo\s*[\"']?00[\"']?\b|\b00\b.*\bflour\b|\bextra fine flour\b"):
        profile.family = "flour"; profile.category = profile.category or "pantry"; profile.flour_type = "00 flour"
    if text_has(normalized, r"\bcorn starch\b|\bcornstarch\b|\bcornflour\b"):
        profile.family = "corn starch"; profile.category = "pantry"
    elif text_has(normalized, r"\bcorn\s+masa\s+flour\b|\bmasa\s+harina\b|\bmasa\s+flour\b|\bcorn flour\b"):
        profile.family = "corn flour"; profile.category = "pantry"
    if text_has(detection_text, r"\bwalnuts?\b"):
        profile.family = "walnuts"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bpecans?\b|\bpecan meats?\b"):
        profile.family = "pecans"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\balmonds?\b") and profile.family not in {"milk", "nut butter"}:
        profile.family = "almonds"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bolives?\b|\bkalamata\b") and profile.family not in {"tuna", "meat cut", "ground meat", "beef", "chicken", "pork", "ham", "sausage"}:
        profile.family = "olives"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bvanilla extract\b|\bpure vanilla\b|^vanilla$"):
        profile.family = "vanilla extract"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\blemon extract\b"):
        profile.family = "extract"; profile.category = profile.category or "pantry"; profile.flavor = "lemon"
    elif text_has(detection_text, r"\balmond extract\b"):
        profile.family = "extract"; profile.category = profile.category or "pantry"; profile.flavor = "almond"
    elif text_has(detection_text, r"\bmolasses\b"):
        profile.family = "molasses"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bcorn syrup\b"):
        profile.family = "corn syrup"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bcream of tartar\b"):
        profile.family = "cream of tartar"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bgelatin\b"):
        profile.family = "gelatin"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bbreadcrumbs?\b|\bbread crumbs?\b|\bpanko\b"):
        profile.family = "breadcrumbs"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bcocoa\b"):
        profile.family = "cocoa"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\blemon juice\b"):
        profile.family = "lemon juice"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\blime juice\b"):
        profile.family = "lime juice"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bworcestershire\b"):
        profile.family = "worcestershire sauce"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bsweet chili sauce\b|\bsweet chilli sauce\b"):
        profile.family = "chili sauce"; profile.category = profile.category or "pantry"; profile.flavor = "sweet chili"
    elif text_has(detection_text, r"\bchili sauce\b|\bchilli sauce\b"):
        profile.family = "chili sauce"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\btabasco\b|\bhot sauce\b|\bsriracha\b"):
        profile.family = "hot sauce"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bvinegar\b"):
        profile.family = "vinegar"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\brice\b") and profile.category not in {"prepared", "snacks"}:
        profile.family = "rice"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bquinoa\b"):
        profile.family = "quinoa"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\brolled oats\b|\boats\b|\boatmeal\b") and profile.category not in {"snacks", "prepared"}:
        profile.family = "oats"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bcornmeal\b|\bcorn meal\b"):
        profile.family = "cornmeal"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\braisins?\b") and profile.category not in {"dairy", "snacks", "prepared"}:
        profile.family = "raisins"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bpeas\b") and profile.category != "prepared":
        profile.family = "peas"; profile.category = profile.category or "produce"
    elif text_has(detection_text, r"\bmustard\b") and profile.category not in {"snacks", "prepared"}:
        profile.family = "mustard"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bhoney\b") and profile.category not in {"meat", "snacks", "prepared", "bakery"} and profile.family not in {"ham"}:
        profile.family = "honey"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bginger\b") and profile.category != "prepared":
        profile.family = "ginger"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bbay leaves?\b|\bbay leaf\b"):
        profile.family = "bay leaf"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bshortening\b"):
        profile.family = "shortening"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bsalt\b") and profile.family not in {"seasoning", "pickles", "prepared meal"} and not text_has(detection_text, r"\bno[-\s]?salt[-\s]?added\b|\bsalt[-\s]?free\b|\breduced[-\s]?sodium\b|\blow[-\s]?sodium\b"):
        profile.family = "salt"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bchili powder\b"):
        profile.family = "chili powder"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bpaprika\b"):
        profile.family = "paprika"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bcumin\b"):
        profile.family = "cumin"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bcinnamon\b"):
        profile.family = "cinnamon"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bnutmeg\b"):
        profile.family = "nutmeg"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\ballspice\b"):
        profile.family = "allspice"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bsage\b") and profile.category not in {"meat", "prepared"}:
        profile.family = "sage"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\btea\b") and text_has(detection_text, r"\bmint\b"):
        profile.family = "tea"; profile.category = profile.category or "beverage"
    elif text_has(detection_text, r"\bjelly\b") and text_has(detection_text, r"\bmint\b"):
        profile.family = "jelly"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bmint extract\b"):
        profile.family = "extract"; profile.category = profile.category or "pantry"; profile.flavor = "mint"
    elif text_has(detection_text, r"\bfresh\b.*\bmint\b|\bmint\b") and not text_has(
        detection_text,
        r"\btoothpaste\b|\btoothbrush\b|\bfloss\b|\btea\b|\bjelly\b|\bgum\b|\bchewing gum\b|\bbreath mints?\b|\btic tac\b|\bice cream\b|\bmint extract\b",
    ):
        profile.family = "mint"; profile.category = profile.category or "produce"; profile.freshness = profile.freshness or ("fresh" if "fresh" in detection_text else None)
    if text_has(normalized, r"\bbaking powder\b"):
        profile.family = "baking powder"
    elif text_has(normalized, r"\bbaking soda\b"):
        profile.family = "baking soda"
    elif text_has(normalized, r"\bpowdered sugar\b"):
        profile.family = "powdered sugar"
    elif text_has(normalized, r"\bbrown sugar\b"):
        profile.family = "brown sugar"
    elif text_has(normalized, r"\bsugar\b"):
        profile.family = "sugar"

    if text_has(normalized, r"\bsoy sauce\b"):
        profile.family = "soy sauce"
    if text_has(normalized, r"\bpeanut sauce\b"):
        profile.family = "peanut sauce"
    elif text_has(normalized, r"\bpeanut butter\b"):
        profile.family = "peanut butter"
    if text_has(normalized, r"\bcoconut water\b"):
        profile.family = "coconut water"
    if (
        text_has(normalized, r"\bolive oil\b")
        and not text_has(normalized, r"\bdressing\b|\bspread\b|\bin olive oil\b")
        and profile.family not in {"hummus", "tuna", "meat cut", "ground meat", "beef", "chicken", "pork", "ham", "sausage"}
    ):
        profile.family = "olive oil"
        if "extra virgin" in normalized:
            profile.form = "extra virgin"
    elif text_has(normalized, r"\bcooking spray\b"):
        profile.family = "cooking spray"
    elif text_has(normalized, r"\bsesame dressing\b"):
        profile.family = "sesame dressing"
    elif text_has(normalized, r"\bsesame oil\b"):
        profile.family = "sesame oil"
    elif text_has(normalized, r"\bcoconut oil\b"):
        profile.family = "coconut oil"
    elif text_has(normalized, r"\bcanola oil\b|\bcorn oil\b|\bvegetable oil\b|^oil$") and profile.family not in {"margarine", "butter blend"}:
        profile.family = "cooking oil"; profile.category = profile.category or "pantry"

    if text_has(detection_text, r"\byogurt\b"):
        profile.family = "yogurt"
        profile.category = profile.category or "dairy"
        profile.flavor = detect_yogurt_flavor(detection_text)
        if text_has(detection_text, r"\byogurt drink\b|\bdrinkable yogurt\b|\bsmoothie\b"):
            profile.family = "yogurt drink"

    if text_has(detection_text, r"\bpepper jack\b"):
        profile.family = "cheese"; profile.category = profile.category or "dairy"

    if text_has(detection_text, r"\bhummus\b"):
        profile.family = "hummus"; profile.category = profile.category or "pantry"
    if text_has(detection_text, r"\bpita chips?\b"):
        profile.family = "prepared meal"; profile.category = "prepared"
    elif text_has(detection_text, r"\bpita\b") and text_has(detection_text, r"\bbreads?\b|\bwhole wheat\b|\bwhole meal\b|\bwholemeal\b|^pita$"):
        profile.family = "pita bread"; profile.category = profile.category or "bakery"
        if text_has(detection_text, r"\bwhole wheat\b|\bwhole meal\b|\bwholemeal\b"):
            profile.form = "whole wheat"
    elif text_has(detection_text, r"\bpita flatbread pizza crust\b|\bpizza crust\b"):
        profile.family = "prepared meal"; profile.category = "prepared"

    if text_has(
        detection_text,
        r"\bpot pie\b|\bfrozen meal\b|\bfrozen dinners?\b|\bentr[eé]es?\b|\balfredo\b|\bmacaroni (?:and|&) (?:cheese|beef)\b|\bbeef\s+(?:and|&)\s+broccoli\b|\bbeef barley vegetable\b|\bbeef chili\b|\bchili\b.*\bbeef\b|\bbeef flavor\b|\bflavor noodles?\b|\bramen\b|\bpho bowl\b|\bgerber\b|\bcovered raisins\b|\bmashed potatoes\b|\bcakes?\b|\bcheesecake\b|\bcupcakes?\b|\bdips?\b|\bpizza\b|\bravioli\b|\btortelloni\b|\bpierogi\b|\btortillas?\b|\bwraps?\b|\bbaby food\b|\bpouch\b|\bbeef stew with\b|\bdinty moore\b|\bchicken parmesan\b|\btaquitos?\b|\bburritos?\b|\bempanadas?\b|\bbiryani\b|\bchallah\b|\brolls?\b|\bonion rings?\b|\bfunyuns?\b|\bfrench onion\b.*\bdip\b|\bdip\b.*\bfrench onion\b|\bonion dip\b|\bonion gravy\b|\bonion bagels?\b|\bpopcorn\b|\bcrackers?\b|\bchips?\b|\bmrs ts\b",
    ) and profile.family not in {"hummus", "pita bread", "bouillon", "broth"}:
        profile.family = "prepared meal"
        profile.category = "prepared"

    juice_produce_type = detect_juice_produce_type(detection_text)
    if juice_produce_type or text_has(detection_text, r"\bjuice drink\b|\bfruit juice\b|\bsnapple\b"):
        profile.family = "juice"; profile.category = "beverage"
        profile.produce_type = juice_produce_type
    elif text_has(detection_text, r"\bapples?\b"):
        profile.family = "apple"; profile.category = profile.category or "produce"; profile.produce_type = "apple"
    elif text_has(detection_text, r"\bpineapple\b") and profile.family not in {"prepared meal", "yogurt"}:
        profile.family = "pineapple"; profile.category = profile.category or "pantry"
        if text_has(detection_text, r"\btinned\b|\bcanned\b|\bcan\b|\bslices?\b|\bchunks?\b|\bcrushed\b"):
            profile.freshness = profile.freshness or "canned"

    measured_prepped_onion = text_has(
        normalized_raw_text,
        r"^\s*\d+(?:\s+\d+)?\s+(?:cups?|tablespoons?|teaspoons?|tbsp|tsp)\s+(?:minced|diced|chopped|sliced)\s+onions?\b",
        r"^\s*\d+(?:\s+\d+)?\s+(?:cups?|tablespoons?|teaspoons?|tbsp|tsp)\s+onions?\s+(?:minced|diced|chopped|sliced)\b",
        r"^\s*\d*\.?\d+(?:\s+\d+/\d+)?\s+(?:cups?|tablespoons?|teaspoons?|tbsp|tsp)\s+(?:minced|diced|chopped|sliced)\s+onions?\b",
        r"^\s*\d*\.?\d+(?:\s+\d+/\d+)?\s+(?:cups?|tablespoons?|teaspoons?|tbsp|tsp)\s+onions?\s+(?:minced|diced|chopped|sliced)\b",
    )
    if text_has(detection_text, r"\bcelery salt\b|\bcelery seed\b|\bgarlic powder\b|\bgranulated garlic\b|\bgarlic salt\b"):
        profile.family = "seasoning"; profile.category = "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bgranulated onion\b|\bonion powder\b|\bdried onion\b|\bonions? minced\b|\bminced onions?\b") and not measured_prepped_onion and not text_has(normalized_raw_text, r"\b\d+(?:\.\d+)?\s+onions?\b"):
        profile.family = "seasoning"; profile.category = "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bscallions?\b|\bgreen onions?\b"):
        profile.family = "green onion"; profile.category = profile.category or "produce"; profile.produce_type = "green onion"
    elif text_has(detection_text, r"\bonions?\b") and profile.family not in {"green onion", "prepared meal", "seasoning"}:
        profile.family = "onion"; profile.category = profile.category or "produce"; profile.produce_type = "onion"
        if text_has(normalized_raw_text, r"\b\d+(?:\.\d+)?\s+onions?\b"):
            profile.freshness = "fresh"

    measured_spice_pepper = text_has(
        normalized_raw_text,
        r"^\s*\d+(?:\s+\d+/\d+|\s+\d+|/\d+|\.\d+)?\s*(?:teaspoons?|tablespoons?|tsp|tbsp)\s+pepper\b",
    )
    generic_pepper = (
        canonical == "peppers"
        and text_has(normalized_raw_text, r"\bpepper\b")
        and (measured_spice_pepper or not text_has(normalized_raw_text, r"^\s*\d"))
        and not text_has(normalized_raw_text, r"\b(green|red|yellow|orange|bell|sweet|jalapeno|jalapeño|chili|chile)\s+pepper\b")
    )
    if text_has(detection_text, r"\bmarinade\b"):
        profile.family = "marinade"; profile.category = profile.category or "pantry"
    if profile.family in {"cheese", "prepared meal", "marinade", "hummus"}:
        pass
    elif text_has(detection_text, r"\bjalapeno(?:s)?\b|\bjalapeño(?:s)?\b|\bchili peppers?\b|\bchile peppers?\b|\bchipotle pepper\b|\bajicito\b|\bpepper paste\b|\bpepper sauce\b|\bhot sauce\b"):
        profile.family = "hot pepper"; profile.category = profile.category or "produce"; profile.produce_type = "hot pepper"
    elif text_has(normalized_raw_text, r"^\s*\d+(?:\.\d+)?(?:\s+\d+)?\s+peppers?\b"):
        profile.family = "bell pepper"; profile.category = "produce"; profile.produce_type = "bell pepper"
    elif measured_spice_pepper or generic_pepper or text_has(detection_text, r"\bcayenne pepper\b|\bblack pepper\b|\bcrushed red pepper\b|\bred pepper flakes\b|^pepper$|\bpeppercorns?\b"):
        profile.family = "pepper spice"; profile.category = profile.category or "pantry"
        if generic_pepper or text_has(detection_text, r"\bblack pepper\b|\bpeppercorns?\b"):
            profile.flavor = "black pepper"
        elif text_has(detection_text, r"\bcayenne pepper\b"):
            profile.flavor = "cayenne"
        elif text_has(detection_text, r"\bcrushed red pepper\b|\bred pepper flakes\b"):
            profile.flavor = "red pepper"
        profile.flavor = "cayenne" if "cayenne" in detection_text else profile.flavor
    elif text_has(detection_text, r"\blemon pepper seasoning\b|\bseasoning blend\b|\bseasoning\b"):
        profile.family = "seasoning"; profile.category = profile.category or "pantry"
        profile.flavor = "lemon pepper" if "lemon pepper" in detection_text else profile.flavor
    elif text_has(detection_text, r"\b(?:green|red|yellow|orange|sweet|bell)\s+peppers?\b|\bpeppers?,\s*(?:green|red|yellow|orange)\b"):
        profile.family = "bell pepper"; profile.category = profile.category or "produce"; profile.produce_type = "bell pepper"
        if text_has(detection_text, r"\bgreen\b"):
            profile.culinary_type = profile.culinary_type or "green_bell_pepper"
        if text_has(detection_text, r"\bb\s*(?:and|g)\s*g\b|\bb and g\b|\bpickled\b"):
            profile.family = "pickled pepper"; profile.category = "pantry"; profile.freshness = "pickled"

    if text_has(detection_text, r"\bgrape tomatoes\b|\bcherry tomatoes\b|\bfresh tomatoes\b"):
        profile.family = "fresh tomato"; profile.category = profile.category or "produce"; profile.produce_type = "tomato"
    if text_has(detection_text, r"\bcelery\b") and not text_has(detection_text, r"\bcelery salt\b|\bcelery seed\b"):
        profile.family = "celery"; profile.category = profile.category or "produce"; profile.produce_type = "celery"
        if text_has(detection_text, r"\bsticks?\b"):
            profile.form = "sticks"
        elif text_has(normalized_raw_text, r"\bdiced\b"):
            profile.form = "diced"
        elif text_has(normalized_raw_text, r"\bminced\b"):
            profile.form = "minced"
        elif text_has(normalized_raw_text, r"\bchopped\b"):
            profile.form = "chopped"
    if (
        profile.family in COMMON_PRODUCE_CANONICALS
        and text_has(detection_text, r"\bpasta\b|\blinguine\b|\bspaghetti\b|\bpenne\b|\bravioli\b|\btortelloni\b|\bpierogi\b|\bpizza\b|\bdips?\b|\bhummus\b|\bbaby food\b|\bpouch\b|\btortillas?\b|\bwraps?\b|\bbites?\b")
    ):
        profile.family = "prepared meal"; profile.category = "prepared"; profile.produce_type = None
    if profile.family in COMMON_PRODUCE_CANONICALS:
        profile.category = profile.category or "produce"
        profile.produce_type = profile.produce_type or profile.family
        if text_has(normalized_raw_text, r"^\s*\d") and not profile.freshness and profile.category == "produce":
            profile.freshness = "fresh"

    if profile.category is None:
        if profile.family in {"milk", "butter", "buttermilk", "cream", "heavy cream", "half-and-half", "sour cream", "ice cream", "butter blend", "margarine"}:
            profile.category = "dairy"
        elif profile.family in {"broth", "soup", "bouillon", "tomato product", "flour", "sugar", "baking powder", "baking soda", "yeast", "soy sauce", "olive oil"}:
            profile.category = "pantry"
    detect_culinary_type(detection_text, profile)
    return profile


def culinary_group(profile: IngredientProfile) -> str | None:
    if not profile.culinary_type:
        return None
    if profile.culinary_type in {"cream_cheese", "neufchatel", "mascarpone", "ricotta", "cottage_cheese", "farmer_cheese"}:
        return "cheese:fresh_spreadable"
    if profile.culinary_type in {"monterey_jack", "colby", "colby_jack", "mild_cheddar", "medium_cheddar", "sharp_cheddar", "low_moisture_mozzarella", "provolone"}:
        return "cheese:mild_melting"
    if profile.culinary_type in {"parmesan", "grana_padano", "pecorino_romano", "aged_asiago", "cotija"}:
        return "cheese:hard_grating"
    if profile.culinary_type in {"swiss", "emmental", "gruyere", "jarlsberg"}:
        return "cheese:swiss_style"
    if profile.culinary_type in {"feta", "goat_cheese", "queso_fresco"}:
        return "cheese:brined_crumbly"
    if profile.culinary_type in {"blue_cheese", "gorgonzola", "roquefort", "stilton"}:
        return "cheese:blue"
    if profile.culinary_type in {"short_medium_rice"}:
        return "rice:short_medium"
    if profile.culinary_type in {"spaghetti", "linguine", "fettuccine", "bucatini"}:
        return "pasta:long"
    if profile.culinary_type in {"penne", "rigatoni", "ziti", "mostaccioli"}:
        return "pasta:short_tubular"
    if profile.culinary_type in {"elbow_macaroni", "small_shells", "ditalini"}:
        return "pasta:small"
    if profile.culinary_type in {"cannellini_beans", "great_northern_beans", "navy_beans", "white_beans"}:
        return "beans:white"
    if profile.culinary_type in {"spinach", "chard", "kale", "collard_greens"}:
        return "vegetable:leafy_cooking"
    if profile.culinary_type in {"romaine", "green_leaf_lettuce", "iceberg", "lettuce", "arugula"}:
        return "vegetable:salad_greens"
    if profile.culinary_type in {"broccoli", "broccolini", "cauliflower"}:
        return "vegetable:cruciferous"
    if profile.culinary_type in {"red_bell_pepper", "yellow_bell_pepper", "orange_bell_pepper", "green_bell_pepper", "bell_pepper"}:
        return "vegetable:bell_pepper"
    if profile.culinary_type in {"white_mushrooms", "cremini_mushrooms", "portobello_mushrooms", "shiitake_mushrooms"}:
        return "vegetable:mushrooms"
    return None


def recipe_context_has(profile: IngredientProfile, *patterns: str) -> bool:
    return text_has(normalize_text(profile.raw_text), *patterns)


def culinary_substitution_score(query: IngredientProfile, product: IngredientProfile) -> float | None:
    if not query.culinary_type or not product.culinary_type or query.culinary_type == product.culinary_type:
        return None
    explicit = CULINARY_SUBSTITUTION_PAIRS.get((query.culinary_type, product.culinary_type))
    if explicit is not None:
        return explicit
    query_group = culinary_group(query)
    product_group = culinary_group(product)
    if query_group and query_group == product_group:
        return CULINARY_FAMILY_CEILINGS.get(query_group, SUBSTITUTION_SCORES["acceptable_substitute"])
    return None


def culinary_substitution_signal(query: IngredientProfile, product: IngredientProfile) -> CompatibilitySignal | None:
    score = culinary_substitution_score(query, product)
    if score is None:
        return None
    if score >= SUBSTITUTION_SCORES["good_substitute"]:
        classification = SOFT_PREFERENCE
    else:
        classification = STRONG_PENALTY
    return CompatibilitySignal(
        "culinary_substitution",
        classification,
        f"{product.culinary_type} can substitute for {query.culinary_type}",
    )


def compatibility_signals(query: IngredientProfile, product: IngredientProfile) -> list[CompatibilitySignal]:
    signals: list[CompatibilitySignal] = []
    substitution_signal = culinary_substitution_signal(query, product)

    if query.family and product.family:
        if query.family == product.family:
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, f"family {query.family} matches"))
        elif query.family == "chicken" and product.family == "meat cut" and product.meat_species == "chicken":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "chicken cut satisfies generic chicken"))
        elif query.family == "beef" and product.meat_species == "beef":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "beef meat satisfies generic beef"))
        elif query.family == "meat cut" and product.family == "beef" and product.meat_species == "beef" and product.category == "meat":
            signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, "raw beef with unspecified cut can satisfy beef cut"))
        elif query.family == "lamb" and product.meat_species == "lamb":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "lamb meat satisfies generic lamb"))
        elif query.family == "cooking oil" and product.family in {"olive oil", "sesame oil", "coconut oil"}:
            signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, f"{product.family} can satisfy generic cooking oil"))
        elif query.family == "cream" and product.family == "heavy cream":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "heavy cream satisfies generic cream"))
        elif {query.family, product.family} <= {"broth", "stock"}:
            signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, "broth and stock are close substitutions"))
        elif substitution_signal:
            signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, f"{product.family} is a functional substitute for {query.family}"))
        else:
            signals.append(CompatibilitySignal("base_family", HARD_REJECT, f"{product.family} is not {query.family}"))
    elif substitution_signal:
        signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, f"{product.family or 'unknown'} is a functional substitute for {query.family or 'unknown'}"))
    else:
        signals.append(CompatibilitySignal("base_family", UNKNOWN, "family is incomplete"))
    if substitution_signal:
        signals.append(substitution_signal)

    if query.family == "cheese" and product.family == "cheese" and query.culinary_type and product.culinary_type and query.culinary_type != product.culinary_type:
        if not substitution_signal:
            signals.append(CompatibilitySignal("cheese_function", HARD_REJECT, f"{product.culinary_type} is not a functional substitute for {query.culinary_type}"))
        if {query.culinary_type, product.culinary_type} == {"fresh_mozzarella", "low_moisture_mozzarella"}:
            signals.append(CompatibilitySignal("mozzarella_moisture", STRONG_PENALTY, "fresh and low-moisture mozzarella differ in texture and use"))
        if query.culinary_type == "blue_cheese" and product.culinary_type not in {"gorgonzola", "roquefort", "stilton"}:
            signals.append(CompatibilitySignal("blue_cheese_identity", HARD_REJECT, "ordinary mild cheese is not blue cheese"))

    if query.culinary_type == "sweetened_condensed_milk" and product.culinary_type != "sweetened_condensed_milk":
        signals.append(CompatibilitySignal("condensed_milk_identity", HARD_REJECT, "sweetened condensed milk requires a sweetened condensed equivalent"))
    if query.culinary_type == "self_rising_flour" and product.culinary_type != "self_rising_flour":
        signals.append(CompatibilitySignal("self_rising_flour", HARD_REJECT, "self-rising flour includes leavening and salt"))
    if query.culinary_type == "powdered_sugar" and product.culinary_type != "powdered_sugar":
        signals.append(CompatibilitySignal("powdered_sugar_identity", HARD_REJECT, "powdered sugar is not ordinary granulated sugar"))
    if query.family == "breadcrumbs" and product.family == "flour":
        signals.append(CompatibilitySignal("breadcrumb_flour_identity", HARD_REJECT, "breadcrumbs are not flour"))
    if query.family == "flour" and product.family == "breadcrumbs":
        signals.append(CompatibilitySignal("breadcrumb_flour_identity", HARD_REJECT, "breadcrumbs are not flour"))
    if query.family == "corn starch" and product.family in {"cornmeal", "corn flour"}:
        signals.append(CompatibilitySignal("corn_product_identity", HARD_REJECT, f"{product.family} is not cornstarch"))
    if query.family in {"cornmeal", "corn flour"} and product.family == "corn starch":
        signals.append(CompatibilitySignal("corn_product_identity", HARD_REJECT, "cornstarch is not cornmeal or corn flour"))
    if query.culinary_type == "fresh_garlic" and product.culinary_type in {"garlic_powder", "granulated_garlic", "garlic_salt"}:
        signals.append(CompatibilitySignal("garlic_conversion", HARD_REJECT, "dried garlic requires quantity or salt conversion"))
    if query.culinary_type == "cake_flour" and product.culinary_type == "bread_flour":
        signals.append(CompatibilitySignal("flour_protein", HARD_REJECT, "bread flour is too high-protein for cake flour"))
    if query.culinary_type == "bread_flour" and product.culinary_type == "cake_flour":
        signals.append(CompatibilitySignal("flour_protein", HARD_REJECT, "cake flour is too low-protein for bread flour"))
    if query.family == "flour" and not query.flour_type and product.flour_type == "00 flour":
        signals.append(CompatibilitySignal("flour_type", STRONG_PENALTY, "00 flour is a specialty flour, not the best generic flour match"))
    if query.culinary_type == "arborio_rice" and product.culinary_type == "long_grain_white_rice":
        signals.append(CompatibilitySignal("risotto_rice", STRONG_PENALTY, "ordinary long-grain rice is a poor risotto rice substitute"))
    if query.culinary_type == "brown_rice" and product.culinary_type and product.culinary_type != "brown_rice":
        signals.append(CompatibilitySignal("rice_cooking_time", HARD_REJECT, "brown rice has different cooking time and liquid requirements"))
    if query.culinary_type in {"spaghetti", "linguine", "fettuccine", "bucatini", "penne", "rigatoni", "ziti", "mostaccioli", "elbow_macaroni", "small_shells", "ditalini"} and product.culinary_type in {"lasagna_sheets", "stuffed_pasta", "gnocchi", "fresh_pasta"}:
        signals.append(CompatibilitySignal("pasta_shape_function", HARD_REJECT, f"{product.culinary_type} is not an ordinary dried pasta substitute"))
    if query.culinary_type in {"brown_lentils", "green_lentils"} and product.culinary_type == "red_lentils":
        signals.append(CompatibilitySignal("lentil_texture", HARD_REJECT, "red lentils do not hold shape like brown or green lentils"))
    if query.family == "tomato product" and text_has(product.normalized_signature, r"\bketchup\b"):
        signals.append(CompatibilitySignal("tomato_ketchup_identity", HARD_REJECT, "ketchup is not a general tomato product substitute"))
    if query.family == "tomato product" and query.tomato_type in {"pasta sauce", "tomato sauce"} and product.family == "pasta":
        signals.append(CompatibilitySignal("sauce_pasta_identity", HARD_REJECT, "dry pasta is not pasta sauce"))
    if query.family == "pasta" and product.family == "tomato product":
        signals.append(CompatibilitySignal("pasta_sauce_identity", HARD_REJECT, "pasta sauce is not dry pasta"))
    if query.culinary_type == "fresh_tomatoes" and product.family == "tomato product" and recipe_context_has(query, r"\bsalad\b|\braw\b|\bfresh\b"):
        signals.append(CompatibilitySignal("tomato_raw_context", HARD_REJECT, "canned tomatoes are not appropriate for raw tomato use"))
    if query.culinary_type in {"green_onion", "chives"} and product.culinary_type == "yellow_onion" and not recipe_context_has(query, r"\bcook(?:ed|ing)?\b|\bsaut[eé]\b|\bsoup\b|\bstew\b"):
        signals.append(CompatibilitySignal("allium_context", HARD_REJECT, "ordinary onion is not a fresh green onion substitute"))
    if query.family == "onion" and product.family == "seasoning":
        signals.append(CompatibilitySignal("allium_form", HARD_REJECT, "dried onion seasoning is not fresh onion"))
    if query.family == "bell pepper" and product.family == "pepper spice":
        signals.append(CompatibilitySignal("pepper_identity", HARD_REJECT, "pepper spice is not bell pepper"))
    if query.family == "bell pepper" and product.family in {"hot pepper", "pickled pepper", "pickles"}:
        signals.append(CompatibilitySignal("pepper_identity", HARD_REJECT, f"{product.family} is not bell pepper"))
    if query.family == "pepper spice" and product.family == "bell pepper":
        signals.append(CompatibilitySignal("pepper_identity", HARD_REJECT, "bell pepper is not pepper spice"))
    if query.family == "celery" and product.family == "celery" and query.form in {"diced", "minced", "chopped"} and product.form == "sticks":
        signals.append(CompatibilitySignal("celery_form", HARD_REJECT, "celery sticks are not the right pack for diced celery"))
    if query.family == "celery" and product.family == "celery" and text_has(product.normalized_signature, r"\bcarrot\b|\bonion\b"):
        signals.append(CompatibilitySignal("celery_mixed_pack", HARD_REJECT, "mixed celery packs are not plain celery"))
    if query.culinary_type in {"fresh_parsley", "fresh_basil"} and product.culinary_type in {"dried_parsley", "dried_basil"} and recipe_context_has(query, r"\bsalad\b|\bcaprese\b|\bgarnish\b|\bfresh\b"):
        signals.append(CompatibilitySignal("fresh_herb_context", STRONG_PENALTY, "dried herbs are weak substitutes when fresh herbs are central"))
    if query.category == "produce" and query.freshness == "fresh" and product.freshness == "frozen" and recipe_context_has(query, r"\bsalad\b|\braw\b"):
        signals.append(CompatibilitySignal("fresh_raw_produce_context", HARD_REJECT, "frozen produce is not appropriate for raw fresh use"))

    if query.family == "milk" and product.family == "milk":
        if query.dairy_type == "dairy" and product.dairy_type == "plant":
            signals.append(CompatibilitySignal("milk_dairy_type", HARD_REJECT, "plant milk is not dairy milk"))
        if query.dairy_type == "plant" and product.dairy_type == "dairy":
            signals.append(CompatibilitySignal("milk_dairy_type", HARD_REJECT, "dairy milk is not plant milk"))
        if query.dairy_type == "plant" and product.dairy_type == "plant" and query.milk_kind and product.milk_kind and query.milk_kind != product.milk_kind:
            signals.append(CompatibilitySignal("milk_kind", HARD_REJECT, f"{product.milk_kind} is not {query.milk_kind}"))
        if query.milk_kind == "plain milk" and product.milk_kind in {"evaporated milk", "condensed milk", "powdered milk"}:
            signals.append(CompatibilitySignal("milk_kind", HARD_REJECT, f"{product.milk_kind} is not ordinary milk"))
        if query.milk_kind in {"evaporated milk", "condensed milk", "powdered milk"} and product.milk_kind != query.milk_kind:
            signals.append(CompatibilitySignal("milk_kind", HARD_REJECT, f"{product.milk_kind} is not {query.milk_kind}"))
        if query.form != "flavored" and product.form == "flavored":
            signals.append(CompatibilitySignal("milk_flavor", HARD_REJECT, "flavored milk is not plain milk"))
        if query.fat_level and product.fat_level and query.fat_level != product.fat_level:
            severity = HARD_REJECT if query.fat_level in {"low-fat", "fat-free", "whole"} else STRONG_PENALTY
            signals.append(CompatibilitySignal("milk_fat_level", severity, f"{product.fat_level} does not satisfy {query.fat_level}"))
        if query.fat_percent and product.fat_percent and query.fat_percent != product.fat_percent:
            signals.append(CompatibilitySignal("milk_fat_percent", HARD_REJECT, f"{product.fat_percent} milk is not {query.fat_percent} milk"))
        if "lactose-free" in query.dietary_requirements and "lactose-free" not in product.dietary_requirements:
            signals.append(CompatibilitySignal("lactose_free", HARD_REJECT, "lactose-free requirement is not verified"))

    if query.family == "butter":
        if product.family in {"margarine", "butter blend"}:
            signals.append(CompatibilitySignal("butter_blend", STRONG_PENALTY, "spread or blend is not plain butter"))
        if text_has(product.normalized_signature, r"\bpickles?\b|\bpretzels?\b|\bbiscuits?\b|\bbuns?\b|\bpopcorn\b|\bcrackers?\b|\bsauc(?:e|ed)\b|\bfrozen side\b|\bfrozen vegetables?\b|\broasted red potatoes\b|\bpotatoes\b"):
            signals.append(CompatibilitySignal("butter_identity", HARD_REJECT, "butter-flavored prepared product is not plain butter"))
        if query.salted_status and product.salted_status and query.salted_status != product.salted_status:
            signals.append(CompatibilitySignal("salted_status", STRONG_PENALTY, f"{product.salted_status} does not satisfy {query.salted_status}"))
        if query.salted_status and not product.salted_status:
            signals.append(CompatibilitySignal("salted_status", UNKNOWN, "salted status is unavailable"))
    if query.family == "margarine" and text_has(product.normalized_signature, r"\bpickles?\b|\bpretzels?\b|\bbiscuits?\b|\bbuns?\b|\bpopcorn\b|\bcrackers?\b|\bsauc(?:e|ed)\b|\bfrozen side\b|\bfrozen vegetables?\b|\broasted red potatoes\b|\bpotatoes\b"):
        signals.append(CompatibilitySignal("margarine_identity", HARD_REJECT, "butter-flavored prepared product is not margarine"))

    if query.family == "heavy cream" and product.family in {"half-and-half", "whipped topping"}:
        if product.family == "half-and-half" and recipe_context_has(query, r"\bsauce\b|\bsoup\b|\bcook(?:ed|ing)?\b"):
            signals.append(CompatibilitySignal("cream_type", SOFT_PREFERENCE, "half-and-half can work in cooked cream applications"))
        else:
            signals.append(CompatibilitySignal("cream_type", HARD_REJECT, f"{product.family} is not heavy cream"))
    if query.family == "heavy cream" and product.family != "half-and-half" and text_has(product.normalized_signature, r"\bhalf and half\b|\bwhipped topping\b|\breddi-wip\b"):
        if text_has(product.normalized_signature, r"\bhalf and half\b") and recipe_context_has(query, r"\bsauce\b|\bsoup\b|\bcook(?:ed|ing)?\b"):
            signals.append(CompatibilitySignal("cream_type", SOFT_PREFERENCE, "half-and-half is weaker than heavy cream but usable in cooked cream applications"))
        else:
            signals.append(CompatibilitySignal("cream_type", HARD_REJECT, "cream substitute is not heavy cream"))
    if query.family == "heavy cream" and recipe_context_has(query, r"\bwhip(?:ped|ping)?\b") and product.culinary_type not in {"heavy_cream", "whipping_cream"}:
        signals.append(CompatibilitySignal("cream_whipping", HARD_REJECT, "only heavy or whipping cream can satisfy whipping use"))
    if query.family == "cream" and product.family in {"sour cream", "ice cream", "cream cheese", "whipped topping"}:
        signals.append(CompatibilitySignal("cream_type", HARD_REJECT, f"{product.family} is not pourable cream"))
    if query.family == "sour cream" and product.family != "sour cream" and product.culinary_type not in {"plain_yogurt", "plain_greek_yogurt"}:
        signals.append(CompatibilitySignal("sour_cream_identity", HARD_REJECT, f"{product.family or 'unknown'} is not sour cream"))

    if query.freshness == "fresh" and product.freshness in {"dried", "canned", "frozen"}:
        if query.category == "produce" and product.freshness == "frozen" and recipe_context_has(query, r"\bcook(?:ed|ing)?\b|\bsaut[eé]\b|\bsoup\b|\bstew\b|\bsauce\b"):
            severity = SOFT_PREFERENCE
        else:
            severity = HARD_REJECT if product.freshness == "dried" else STRONG_PENALTY
        signals.append(CompatibilitySignal("freshness", severity, f"{product.freshness} is not fresh"))
    if (
        query.freshness == "canned"
        and query.family == "tuna"
        and product.family == "tuna"
        and not product.freshness
        and product.category not in {"meat", "prepared"}
    ):
        signals.append(CompatibilitySignal("freshness_missing", UNKNOWN, "canned tuna metadata is unavailable"))
    elif query.freshness in {"dried", "frozen", "canned"} and not product.freshness:
        signals.append(CompatibilitySignal("freshness_missing", STRONG_PENALTY, f"{query.freshness} requirement is not verified"))
    if query.freshness and product.freshness and query.freshness != product.freshness:
        severity = SOFT_PREFERENCE if query.category == "produce" and query.freshness == "fresh" and product.freshness == "frozen" and recipe_context_has(query, r"\bcook(?:ed|ing)?\b|\bsaut[eé]\b|\bsoup\b|\bstew\b|\bsauce\b") else STRONG_PENALTY
        signals.append(CompatibilitySignal("freshness_specific", severity, f"{product.freshness} does not satisfy {query.freshness}"))

    if query.family == "ground meat":
        if product.family != "ground meat":
            signals.append(CompatibilitySignal("ground_meat", HARD_REJECT, "whole cuts are not ground meat"))
        elif query.meat_species and product.meat_species and query.meat_species != product.meat_species:
            signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
    if query.category == "meat" and product.category == "meat" and query.meat_species and product.meat_species and query.meat_species != product.meat_species:
        signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
    if query.category == "meat" and product.category and product.category != "meat":
        signals.append(CompatibilitySignal("meat_category", HARD_REJECT, f"{product.category} product is not meat"))
    if query.family == "beef" and product.family in {"sausage", "pork", "sauce", "processed meat", "broth", "stock", "soup", "bouillon", "prepared meal", "pet food", "organ meat", "meat bones"}:
        signals.append(CompatibilitySignal("beef_identity", HARD_REJECT, f"{product.family} is not beef"))
    if query.family == "beef" and product.category and product.category != "meat":
        signals.append(CompatibilitySignal("beef_identity", HARD_REJECT, f"{product.category} product is not beef meat"))
    if query.family == "beef" and product.family == "ground meat":
        signals.append(CompatibilitySignal("beef_form", STRONG_PENALTY, "ground or formed beef is not a whole beef cut"))
    if query.family == "beef" and product.family == "meat cut" and not text_has(product.normalized_signature, r"\bbeef\b"):
        signals.append(CompatibilitySignal("beef_name_specificity", STRONG_PENALTY, "raw beef cut does not explicitly name beef"))
    if query.family == "meat cut" and product.family == "meat cut":
        if query.meat_species and product.meat_species and query.meat_species != product.meat_species:
            signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
        cut_signal = beef_cut_substitution_signal(query, product)
        if cut_signal:
            signals.append(cut_signal)
    if query.family == "meat cut" and query.meat_cut and product.family == "beef" and product.meat_species == "beef" and not product.meat_cut:
        signals.append(CompatibilitySignal("meat_cut_missing", STRONG_PENALTY, f"{query.meat_cut} cut is not verified"))
    if query.family == "organ meat":
        if product.family != "organ meat":
            signals.append(CompatibilitySignal("organ_meat_identity", HARD_REJECT, f"{product.family} is not organ meat"))
        elif query.meat_species and product.meat_species and query.meat_species != product.meat_species:
            signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
        elif query.meat_cut and product.meat_cut and query.meat_cut != product.meat_cut:
            signals.append(CompatibilitySignal("organ_meat_cut", HARD_REJECT, f"{product.meat_cut} is not {query.meat_cut}"))
    if query.family == "chicken" and product.family in {"broth", "stock", "soup", "bouillon"}:
        signals.append(CompatibilitySignal("chicken_identity", HARD_REJECT, f"{product.family} is not chicken meat"))
    if query.family == "tuna" and text_has(product.normalized_signature, r"\bsalad\b|\bsandwich\b|\bwrap\b|\bpasta\b"):
        signals.append(CompatibilitySignal("tuna_identity", HARD_REJECT, "prepared tuna item is not plain tuna"))
    if query.family == "broth" and product.family in {"meat cut", "ground meat", "soup", "bouillon"}:
        severity = HARD_REJECT if product.family in {"meat cut", "ground meat", "soup"} else STRONG_PENALTY
        signals.append(CompatibilitySignal("broth_identity", severity, f"{product.family} is not broth"))
    if query.family == "broth" and product.family == "broth" and query.broth_species and product.broth_species and query.broth_species != product.broth_species:
        signals.append(CompatibilitySignal("broth_species", HARD_REJECT, f"{product.broth_species} stock does not satisfy {query.broth_species}"))
    if query.family == "bouillon" and product.family == "bouillon" and query.broth_species and product.broth_species and query.broth_species != product.broth_species:
        signals.append(CompatibilitySignal("bouillon_species", HARD_REJECT, f"{product.broth_species} bouillon does not satisfy {query.broth_species}"))
    if query.family == "soup" and query.soup_type and product.soup_type != query.soup_type:
        signals.append(CompatibilitySignal("soup_type", HARD_REJECT, f"{product.soup_type or 'generic soup'} is not {query.soup_type} soup"))
    if query.family == "juice":
        if product.family != "juice":
            signals.append(CompatibilitySignal("juice_identity", HARD_REJECT, f"{product.family or 'unknown'} is not juice"))
        elif query.produce_type and product.produce_type and query.produce_type != product.produce_type:
            signals.append(CompatibilitySignal("juice_type", HARD_REJECT, f"{product.produce_type} juice is not {query.produce_type} juice"))
    if product.family == "juice" and query.family != "juice":
        signals.append(CompatibilitySignal("juice_identity", HARD_REJECT, "juice is not the requested fruit or vegetable"))

    if query.family == "flour" and product.family == "flour" and query.flour_type and product.flour_type and query.flour_type != product.flour_type:
        severity = SOFT_PREFERENCE if substitution_signal else HARD_REJECT
        signals.append(CompatibilitySignal("flour_type", severity, f"{product.flour_type} is not {query.flour_type}"))
    if "gluten-free" in query.dietary_requirements and "gluten-free" not in product.dietary_requirements:
        signals.append(CompatibilitySignal("gluten_free", HARD_REJECT, "gluten-free requirement is not verified"))
    if query.family in {"baking powder", "baking soda"} and product.family != query.family:
        signals.append(CompatibilitySignal("leavener_identity", HARD_REJECT, f"{product.family} is not {query.family}"))
    if query.family == "yeast" and product.family == "nutritional yeast":
        signals.append(CompatibilitySignal("yeast_type", HARD_REJECT, "nutritional yeast is not baking yeast"))
    if query.family == "pancake mix" and product.family == "potato pancake mix":
        signals.append(CompatibilitySignal("pancake_mix_type", HARD_REJECT, "potato pancake mix is not pancake mix"))
    if query.family == "eggs" and product.family == "egg substitute":
        signals.append(CompatibilitySignal("egg_identity", HARD_REJECT, "egg substitute is not shell eggs"))
    if query.family == "eggs" and text_has(product.normalized_signature, r"\bno yolks\b|\bmacaroni\b|\bpasta\b|\bwraps?\b|\bsandwich\b|\bburrito\b"):
        signals.append(CompatibilitySignal("egg_identity", HARD_REJECT, "egg-containing prepared product is not shell eggs"))
    if query.family == "puff pastry" and text_has(product.normalized_signature, r"\bcrisps?\b|\bfranks?\b|\bparty size\b|\bsnacks?\b|\bcannoli\b|\bdanish\b|\bcinnamon rolls?\b"):
        signals.append(CompatibilitySignal("puff_pastry_identity", HARD_REJECT, "pastry-containing prepared product is not puff pastry sheets"))
    if query.family == "puff pastry" and product.category in {"snacks", "household", "prepared", "meat"}:
        signals.append(CompatibilitySignal("puff_pastry_identity", HARD_REJECT, f"{product.category} product is not puff pastry sheets"))
    if query.family == "puff pastry" and product.family != "puff pastry":
        signals.append(CompatibilitySignal("puff_pastry_identity", HARD_REJECT, f"{product.family or 'unknown'} is not puff pastry sheets"))
    if query.family == "mustard" and text_has(product.normalized_signature, r"\bmustard\s+(?:seed|powder)\b|\b(?:seed|powder)\s+mustard\b"):
        signals.append(CompatibilitySignal("mustard_form", HARD_REJECT, "mustard seed or powder is not prepared mustard"))

    if query.family == "tomato product" and product.family == "tomato product" and query.tomato_type and product.tomato_type and query.tomato_type != product.tomato_type:
        signals.append(CompatibilitySignal("tomato_type", HARD_REJECT, f"{product.tomato_type} is not {query.tomato_type}"))
    if query.family == "tomato product" and query.tomato_type and not product.tomato_type:
        signals.append(CompatibilitySignal("tomato_type_missing", STRONG_PENALTY, f"{query.tomato_type} identity is not verified"))
    if query.family == "soy sauce" and product.family != "soy sauce":
        signals.append(CompatibilitySignal("soy_sauce_identity", HARD_REJECT, "soy product is not soy sauce"))
    if query.family == "peanut butter" and product.family == "peanut sauce":
        signals.append(CompatibilitySignal("peanut_identity", HARD_REJECT, "peanut sauce is not peanut butter"))
    if query.family == "coconut milk" and product.family == "coconut water":
        signals.append(CompatibilitySignal("coconut_identity", HARD_REJECT, "coconut water is not coconut milk"))
    if query.family == "olive oil":
        if product.family in {"cooking spray", "sesame dressing"} or text_has(product.normalized_signature, r"\bin olive oil\b|\bdressing\b|\bspread\b"):
            signals.append(CompatibilitySignal("oil_identity", HARD_REJECT, "olive-oil-flavored or packed product is not bottled olive oil"))
        if query.form == "extra virgin" and product.form != "extra virgin":
            signals.append(CompatibilitySignal("olive_oil_form", STRONG_PENALTY, "extra virgin requested"))
    if query.family == "cooking oil" and product.family in {"olive oil", "sesame oil", "coconut oil"}:
        signals.append(CompatibilitySignal("generic_oil", SOFT_PREFERENCE, f"{product.family} can substitute for generic cooking oil"))
    if query.family in {"olive oil", "sesame oil"} and product.family == "cooking oil":
        signals.append(CompatibilitySignal("specific_oil", HARD_REJECT, f"generic cooking oil is not {query.family}"))
    if query.family == "quinoa" and text_has(product.normalized_signature, r"\bwith quinoa\b|\bsoup\b|\bsalad\b|\bchocolate\b|\bready-to-eat\b|\bmicrowaveable\b|\bcrispbread\b"):
        signals.append(CompatibilitySignal("quinoa_identity", HARD_REJECT, "quinoa-containing prepared product is not plain quinoa"))
    if query.family == "pepper spice" and product.family == "pepper spice" and query.flavor and product.flavor and query.flavor != product.flavor:
        signals.append(CompatibilitySignal("pepper_spice_type", HARD_REJECT, f"{product.flavor} is not {query.flavor}"))
    if query.family == "extract" and product.family == "extract" and query.flavor and product.flavor and query.flavor != product.flavor:
        signals.append(CompatibilitySignal("extract_flavor", HARD_REJECT, f"{product.flavor} extract is not {query.flavor} extract"))
    if query.family == "vanilla extract" and (product.category == "beverage" or text_has(product.normalized_signature, r"\bsyrup\b|\bseltzer\b|\btea\b|\bpuffs\b")):
        signals.append(CompatibilitySignal("extract_identity", HARD_REJECT, "vanilla-flavored product is not vanilla extract"))
    if query.family == "buttermilk" and text_has(product.normalized_signature, r"\bbiscuits?\b|\bwaffles?\b|\bpancake\b|\bmix\b|\bdressing\b|\bdip\b"):
        signals.append(CompatibilitySignal("buttermilk_identity", HARD_REJECT, "buttermilk-flavored prepared product is not buttermilk"))
    if query.family == "honey" and product.category in {"bakery", "snacks", "prepared", "meat"}:
        signals.append(CompatibilitySignal("honey_identity", HARD_REJECT, "honey-flavored or honey-containing product is not plain honey"))
    if query.family == "honey" and product.family != "honey":
        signals.append(CompatibilitySignal("honey_identity", HARD_REJECT, "honey-flavored or honey-containing product is not plain honey"))
    if query.family in {"walnuts", "pecans", "almonds"}:
        plain_nut_reject_patterns = (
            r"\bdressing\b|\bsauce\b|\bmarinade\b|\bvinaigrette\b|\bspread\b|\bbutter\b|\boil\b",
            r"\bcookies?\b|\bcakes?\b|\btart(?:e)?s?\b|\bbars?\b|\bcereal\b|\bgranola\b|\btrail mix\b",
            r"\bmilk\b|\bbeverage\b|\bice cream\b|\byogurt\b|\bhummus\b|\bsalad\b|\bprepared\b",
        )
        if product.family != query.family or product.category in {"bakery", "prepared"} or text_has(product.normalized_signature, *plain_nut_reject_patterns):
            signals.append(CompatibilitySignal("plain_nut_identity", HARD_REJECT, f"{product.family or 'unknown'} is not plain {query.family}"))

    if query.sweetened_status == "unsweetened" and product.sweetened_status == "sweetened":
        signals.append(CompatibilitySignal("sweetened_status", HARD_REJECT, "sweetened product conflicts with unsweetened request"))
    if query.salted_status == "no-salt-added" and product.salted_status != "no-salt-added":
        signals.append(CompatibilitySignal("salted_status", HARD_REJECT, "no-salt-added requirement is not verified"))
    if "vegan" in query.dietary_requirements and product.category in {"dairy", "meat"}:
        signals.append(CompatibilitySignal("vegan", HARD_REJECT, "animal-derived product conflicts with vegan request"))
    if "vegetarian" in query.dietary_requirements and product.category == "meat":
        signals.append(CompatibilitySignal("vegetarian", HARD_REJECT, "meat product conflicts with vegetarian request"))
    if "nut-free" in query.dietary_requirements and (
        product.flour_type in {"almond flour", "coconut flour"} or text_has(product.normalized_signature, r"\balmond\b|\bcoconut flour\b")
    ):
        signals.append(CompatibilitySignal("nut_free", HARD_REJECT, "nut flour conflicts with nut-free request"))
    if query.family == "yogurt" and product.family == "yogurt":
        if query.flavor == "plain" and product.flavor and product.flavor != "plain":
            signals.append(CompatibilitySignal("yogurt_flavor", HARD_REJECT, f"{product.flavor} yogurt is not plain"))
        if query.flavor == "plain" and not product.flavor:
            signals.append(CompatibilitySignal("yogurt_flavor_missing", STRONG_PENALTY, "plain yogurt flavor is not verified"))
        if query.flavor and query.flavor != "plain" and product.flavor and product.flavor != query.flavor:
            signals.append(CompatibilitySignal("yogurt_flavor", HARD_REJECT, f"{product.flavor} yogurt is not {query.flavor}"))
    if product.family == "prepared meal" and query.family != "prepared meal":
        signals.append(CompatibilitySignal("prepared_food", HARD_REJECT, "prepared food is not a raw grocery ingredient match"))
    if product.category == "prepared" and query.category != "prepared":
        signals.append(CompatibilitySignal("prepared_food", HARD_REJECT, "prepared food is not a raw grocery ingredient match"))

    if not signals:
        signals.append(CompatibilitySignal("default", UNKNOWN, "no specific compatibility rule applied"))
    return signals


def has_hard_reject(signals: list[CompatibilitySignal]) -> bool:
    return any(signal.classification == HARD_REJECT for signal in signals)


def has_strong_penalty(signals: list[CompatibilitySignal]) -> bool:
    return any(signal.classification == STRONG_PENALTY for signal in signals)


def is_substitution_candidate(query: IngredientProfile, product: IngredientProfile, signals: list[CompatibilitySignal]) -> bool:
    if query.freshness == "fresh" and product.freshness == "dried" and query.family == product.family:
        return True
    if query.family == "broth" and product.family in {"bouillon"}:
        return True
    if query.family == "butter" and product.family in {"butter blend", "margarine"}:
        return True
    return False


def query_tokens_present(query: IngredientProfile, product: IngredientProfile) -> bool:
    tokens = [
        token
        for token in query.normalized_signature.split()
        if token not in {"and", "or", "brand", "plain"}
    ]
    return bool(tokens) and all(token in product.normalized_signature.split() for token in tokens)


def explicit_attribute_bonus(query: IngredientProfile, product: IngredientProfile) -> float:
    bonus = 0.0
    if (
        query.family == "meat cut"
        and product.family == "meat cut"
        and query.meat_cut
        and query.meat_cut == product.meat_cut
        and (
            query.meat_species == product.meat_species
            or (query.meat_species is None and product.meat_species in {"beef", "lamb"})
        )
    ):
        bonus += 0.18
    elif is_slow_cooking_beef_cut_substitution(query, product):
        bonus += 0.08
    if query.freshness and query.freshness == product.freshness:
        patterns = {
            "dried": r"\bdried\b|\bflakes\b",
            "frozen": r"\bfrozen\b|\bsteamfresh\b",
            "canned": r"\bcanned\b|\bwhole peeled\b|\bcrushed\b|\bdiced\b|\bstewed\b",
        }
        if text_has(product.normalized_signature, patterns.get(query.freshness, rf"\b{query.freshness}\b")):
            bonus += 0.04
    if query.salted_status and query.salted_status == product.salted_status:
        bonus += 0.04
    if query.fat_percent and query.fat_percent == product.fat_percent:
        bonus += 0.04
    if query.flavor and query.flavor == product.flavor:
        bonus += 0.04
    if query.broth_species and query.broth_species == product.broth_species:
        bonus += 0.04
    return min(0.18, bonus)


def unrequested_attribute_penalty(query: IngredientProfile, product: IngredientProfile) -> float:
    penalty = 0.0
    if (
        query.family == "milk"
        and query.milk_kind in {"evaporated milk", "condensed milk", "powdered milk"}
        and not query.fat_level
        and product.fat_level
    ):
        penalty += 0.025
    return min(0.08, penalty)


def score_candidate(
    candidate: Candidate,
    feature: dict[str, Any],
    query_profile: IngredientProfile,
    product_profile: IngredientProfile,
    signals: list[CompatibilitySignal],
    config: MatchScoringConfig,
    override_approved: bool = False,
) -> RankedCandidate:
    substitution_score = culinary_substitution_score(query_profile, product_profile)
    canonical_match = bool(query_profile.canonical and query_profile.canonical == product_profile.canonical)
    family_match = bool(query_profile.family and query_profile.family == product_profile.family) or any(
        signal.rule == "base_family" and signal.classification in {COMPATIBLE, SOFT_PREFERENCE}
        for signal in signals
    )
    category_match = query_profile.category and product_profile.category and query_profile.category == product_profile.category
    brand_match = bool(query_profile.brand and product_profile.brand and normalize_text(query_profile.brand) == normalize_text(product_profile.brand))
    attribute_compatible = 1.0
    if has_strong_penalty(signals):
        attribute_compatible -= 0.45
    unknown_count = sum(1 for signal in signals if signal.classification == UNKNOWN)
    attribute_compatible -= min(0.25, unknown_count * 0.05)
    attribute_compatible = max(0.0, attribute_compatible)

    breakdown = {
        "exact_match": config.exact_match_bonus if candidate.exact_match else 0.0,
        "alias_match": config.alias_match_bonus if candidate.alias_match else 0.0,
        "canonical_identity": config.canonical_identity_weight if canonical_match else 0.0,
        "base_family": config.family_weight if family_match else 0.0,
        "lexical_similarity": candidate.lexical_similarity * config.lexical_weight,
        "semantic_similarity": (candidate.semantic_similarity or 0.0) * config.semantic_weight,
        "category_compatibility": config.category_weight if category_match else 0.0,
        "attribute_compatibility": attribute_compatible * config.attribute_weight,
        "specific_attribute_match": explicit_attribute_bonus(query_profile, product_profile),
        "culinary_substitution_quality": 0.25 * (substitution_score or 0.0),
        "unrequested_attribute_penalty": -unrequested_attribute_penalty(query_profile, product_profile),
        "query_token_presence": 0.06 if query_tokens_present(query_profile, product_profile) else 0.0,
        "brand": config.brand_weight if brand_match else 0.0,
        "source_quality": (float(feature.get("source_quality_score") or 0) / 100.0) * config.source_quality_weight,
        "approved_override": 0.12 if override_approved else 0.0,
        "probably_valid_penalty": -config.probably_valid_penalty if feature.get("record_status") == "probably_valid_grocery_product" else 0.0,
        "strong_conflict_penalty": -config.strong_penalty * sum(1 for signal in signals if signal.classification == STRONG_PENALTY),
        "soft_conflict_penalty": -config.soft_penalty * sum(1 for signal in signals if signal.classification == SOFT_PREFERENCE),
    }
    final_score = max(0.0, min(1.0, sum(breakdown.values())))
    if substitution_score is not None:
        cap = 0.93 if substitution_score >= 1.0 else 0.86 if substitution_score >= 0.9 else 0.78 if substitution_score >= 0.8 else 0.66
        final_score = min(final_score, cap)
    conflicts = [asdict(signal) for signal in signals if signal.classification in {STRONG_PENALTY, HARD_REJECT, UNKNOWN}]
    reason_codes = list(candidate.retrieval_reason_codes)
    if canonical_match:
        reason_codes.append("canonical_match")
    if family_match:
        reason_codes.append("family_match")
    if substitution_score is not None:
        reason_codes.append("culinary_substitute")
    if override_approved:
        reason_codes.append("approved_override")
    if has_hard_reject(signals):
        reason_codes.append("hard_reject")
    confidence = LOW
    return RankedCandidate(
        product_id=candidate.product_id,
        product_name=candidate.original_product_name,
        normalized_name=candidate.normalized_name,
        canonical_ingredient=candidate.canonical_ingredient,
        record_status=candidate.record_status,
        confidence=confidence,
        final_score=round(final_score, 4),
        score_breakdown={key: round(value, 4) for key, value in breakdown.items()},
        conflicts=conflicts,
        warnings=[signal.message for signal in signals if signal.classification == UNKNOWN],
        reason_codes=sorted(set(reason_codes)),
        exact_match=candidate.exact_match,
        alias_match=candidate.alias_match,
        lexical_similarity=candidate.lexical_similarity,
        semantic_similarity=candidate.semantic_similarity,
        is_substitution=False,
    )


def confidence_for(top: RankedCandidate | None, second: RankedCandidate | None, config: MatchScoringConfig) -> str:
    if top is None:
        return NO_SAFE_MATCH
    margin = top.final_score - (second.final_score if second else 0.0)
    identity_certain = "canonical_match" in top.reason_codes or "family_match" in top.reason_codes
    has_unknown = any(conflict["classification"] == UNKNOWN for conflict in top.conflicts)
    if top.exact_match and top.final_score >= config.exact_threshold and identity_certain and not has_unknown:
        return EXACT
    if top.final_score >= config.high_threshold and identity_certain and margin >= config.ambiguity_margin:
        return HIGH
    if top.final_score >= config.medium_threshold and identity_certain:
        return MEDIUM
    if top.final_score >= config.low_threshold:
        return LOW
    return NO_SAFE_MATCH


def culinary_substitution_queries(profile: IngredientProfile, limit: int = 6) -> list[tuple[str, float]]:
    if not profile.culinary_type:
        return []
    pairs: list[tuple[str, float]] = []
    seen = {profile.culinary_type}
    for (source, target), score in CULINARY_SUBSTITUTION_PAIRS.items():
        if source == profile.culinary_type and target not in seen:
            seen.add(target)
            pairs.append((target.replace("_", " "), score))
    group = culinary_group(profile)
    if group:
        for (source, target), score in CULINARY_SUBSTITUTION_PAIRS.items():
            if source in seen:
                continue
            probe = IngredientProfile(
                normalized_signature=source.replace("_", " "),
                canonical=None,
                family=profile.family,
                category=profile.category,
                culinary_type=source,
            )
            if culinary_group(probe) == group and source not in seen:
                seen.add(source)
                ceiling = CULINARY_FAMILY_CEILINGS.get(group, SUBSTITUTION_SCORES["acceptable_substitute"])
                pairs.append((source.replace("_", " "), min(score, ceiling)))
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return pairs[:limit]


def merge_retrieval_results(primary: CandidateRetrievalResult, expansions: list[tuple[CandidateRetrievalResult, float]]) -> CandidateRetrievalResult:
    by_id: dict[str, Candidate] = {}
    for candidate in primary.candidates:
        by_id[candidate.product_id] = copy.deepcopy(candidate)
    for retrieval, substitution_score in expansions:
        for candidate in retrieval.candidates:
            expanded = copy.deepcopy(candidate)
            expanded.lexical_similarity = min(expanded.lexical_similarity, substitution_score)
            if expanded.semantic_similarity is not None:
                expanded.semantic_similarity = min(expanded.semantic_similarity, substitution_score)
            expanded.exact_match = False
            expanded.alias_match = False
            expanded.retrieval_reason_codes = sorted(set(expanded.retrieval_reason_codes) | {"deterministic_substitution_query"})
            existing = by_id.get(expanded.product_id)
            if existing is None:
                by_id[expanded.product_id] = expanded
                continue
            existing.lexical_similarity = max(existing.lexical_similarity, expanded.lexical_similarity)
            if expanded.semantic_similarity is not None:
                existing.semantic_similarity = max(existing.semantic_similarity or -1, expanded.semantic_similarity)
            existing.retrieval_reason_codes = sorted(set(existing.retrieval_reason_codes) | set(expanded.retrieval_reason_codes))
            if existing.category_match_signal == "unknown":
                existing.category_match_signal = expanded.category_match_signal
    primary_ids = {candidate.product_id for candidate in primary.candidates}
    merged = sorted(
        by_id.values(),
        key=lambda item: (
            item.product_id not in primary_ids,
            -(item.lexical_similarity * 0.62 + (item.semantic_similarity or 0) * 0.38),
            item.source_rank or 999999,
            item.normalized_name,
        ),
    )
    return CandidateRetrievalResult(
        ingredient_text=primary.ingredient_text,
        parsed_query=primary.parsed_query,
        normalized_semantic_query=primary.normalized_semantic_query,
        candidates=merged,
        retrieval_latency_ms=round(primary.retrieval_latency_ms + sum(item.retrieval_latency_ms for item, _score in expansions), 2),
        lexical_latency_ms=round(primary.lexical_latency_ms + sum(item.lexical_latency_ms for item, _score in expansions), 2),
        semantic_latency_ms=primary.semantic_latency_ms,
        query_embedding_latency_ms=primary.query_embedding_latency_ms,
        embedding_index_available=primary.embedding_index_available,
        embedding_model_version=primary.embedding_model_version,
        index_version=primary.index_version,
        degraded_mode=primary.degraded_mode,
        errors=primary.errors + [error for item, _score in expansions for error in item.errors if "Semantic retrieval skipped" not in error],
    )


class ProductMatchService:
    def __init__(
        self,
        retriever: ProductCandidateRetriever | None = None,
        overrides: OverrideStore | None = None,
        config: MatchScoringConfig | None = None,
        cache: MatchCache | None = None,
    ):
        self.retriever = retriever or ProductCandidateRetriever()
        self.overrides = overrides or OverrideStore()
        self.config = config or MatchScoringConfig()
        self.cache = cache or MatchCache()
        self._feature_by_id: dict[str, dict[str, Any]] | None = None
        self._product_profile_cache: dict[str, IngredientProfile] = {}
        self._product_index_version_cache: str | None = None

    @property
    def feature_by_id(self) -> dict[str, dict[str, Any]]:
        if self._feature_by_id is None:
            self._feature_by_id = {feature.get("product_id"): feature for feature in self.retriever.features}
        return self._feature_by_id

    def product_index_version(self) -> str | None:
        if self._product_index_version_cache is not None:
            return self._product_index_version_cache
        if self.retriever._index_metadata:
            self._product_index_version_cache = self.retriever._index_metadata.get("index_version") or "no-index"
            return self._product_index_version_cache
        try:
            _embeddings, metadata = load_existing_index(self.retriever.index_dir)
            self._product_index_version_cache = (metadata or {}).get("index_version") or "no-index"
            return self._product_index_version_cache
        except Exception:
            self._product_index_version_cache = "no-index"
            return None

    def product_profile(self, feature: dict[str, Any]) -> IngredientProfile:
        product_id = str(feature.get("product_id") or "")
        cached = self._product_profile_cache.get(product_id)
        if cached is None:
            cached = profile_from_feature(feature)
            if product_id:
                self._product_profile_cache[product_id] = cached
        return cached

    def cache_key(self, profile: IngredientProfile, use_semantic: bool = True) -> str:
        index_version = self.product_index_version() or "no-index"
        return "|".join(
            [
                MATCHER_VERSION,
                "semantic" if use_semantic else "lexical",
                index_version,
                self.overrides.version,
                profile.normalized_signature,
                profile.fat_level or "",
                profile.salted_status or "",
                profile.freshness or "",
                ",".join(sorted(profile.dietary_requirements)),
            ]
        )

    def _retrieve_with_substitution_expansion(
        self,
        query_profile: IngredientProfile,
        candidate_limit: int,
        use_semantic: bool,
    ) -> CandidateRetrievalResult:
        try:
            retrieval = self.retriever.retrieve_product_candidates(
                query_profile.normalized_signature,
                limit=candidate_limit,
                use_semantic=use_semantic,
            )
        except TypeError as exc:
            if "use_semantic" not in str(exc):
                raise
            retrieval = self.retriever.retrieve_product_candidates(query_profile.normalized_signature, limit=candidate_limit)

        expansions = []
        for alternate_query, substitution_score in culinary_substitution_queries(query_profile):
            try:
                expanded = self.retriever.retrieve_product_candidates(
                    alternate_query,
                    limit=max(12, candidate_limit // 4),
                    use_semantic=False,
                )
            except TypeError:
                expanded = self.retriever.retrieve_product_candidates(alternate_query, limit=max(12, candidate_limit // 4))
            expansions.append((expanded, substitution_score))
        return merge_retrieval_results(retrieval, expansions) if expansions else retrieval

    def match_recipe_ingredient(
        self,
        ingredient_text: str,
        limit: int = 5,
        candidate_limit: int = 80,
        use_semantic: bool = True,
    ) -> MatchResult:
        started = time.perf_counter()
        query_profile, parsed = profile_from_query(ingredient_text, self.overrides)
        key = self.cache_key(query_profile, use_semantic=use_semantic)
        cached = self.cache.get(key)
        if cached and self._cached_selection_is_valid(cached):
            result = copy.deepcopy(cached)
            result.cache_hit = True
            result.total_timing_ms = round((time.perf_counter() - started) * 1000, 2)
            return result

        forced = self._forced_result(ingredient_text, query_profile, parsed, started)
        if forced:
            self.cache.set(key, forced)
            return forced

        retrieval = self._retrieve_with_substitution_expansion(query_profile, candidate_limit, use_semantic)
        result = self._match_from_retrieval(ingredient_text, query_profile, parsed, retrieval, started, limit, candidate_limit)
        self.cache.set(key, result)
        return result

    def _match_from_retrieval(
        self,
        ingredient_text: str,
        query_profile: IngredientProfile,
        parsed: dict[str, Any],
        retrieval: CandidateRetrievalResult,
        started: float,
        limit: int,
        candidate_limit: int,
    ) -> MatchResult:
        rerank_started = time.perf_counter()
        forbidden_ids = {
            item.get("product_id")
            for item in self.overrides.matching_items("forbidden_products", query_profile.normalized_signature)
        }
        approved_ids = {
            item.get("product_id")
            for item in self.overrides.matching_items("approved_matches", query_profile.normalized_signature)
        }
        substitution_ids = {
            item.get("product_id")
            for item in self.overrides.matching_items("substitutions", query_profile.normalized_signature)
        }
        incompatible_families = {
            normalize_text(item.get("family"))
            for item in self.overrides.matching_items("incompatible_families", query_profile.normalized_signature)
        }

        accepted: list[RankedCandidate] = []
        substitutions: list[RankedCandidate] = []
        rejected: list[RankedCandidate] = []
        for candidate in retrieval.candidates:
            feature = self.feature_by_id.get(candidate.product_id)
            if not feature or not feature.get("eligible_for_retrieval"):
                continue
            product_profile = self.product_profile(feature)
            signals = compatibility_signals(query_profile, product_profile)
            if candidate.product_id in forbidden_ids:
                signals.append(CompatibilitySignal("manual_forbidden", HARD_REJECT, "product is manually forbidden"))
            if product_profile.family and normalize_text(product_profile.family) in incompatible_families:
                signals.append(CompatibilitySignal("manual_incompatible_family", HARD_REJECT, "product family is manually incompatible"))
            ranked = score_candidate(
                candidate,
                feature,
                query_profile,
                product_profile,
                signals,
                self.config,
                override_approved=candidate.product_id in approved_ids,
            )
            if candidate.product_id in substitution_ids:
                ranked.is_substitution = True
                substitutions.append(ranked)
            elif has_hard_reject(signals):
                if is_substitution_candidate(query_profile, product_profile, signals):
                    ranked.is_substitution = True
                    ranked.confidence = SUBSTITUTION_ONLY
                    substitutions.append(ranked)
                else:
                    rejected.append(ranked)
            else:
                accepted.append(ranked)

        accepted.sort(key=lambda item: item.final_score, reverse=True)
        substitutions.sort(key=lambda item: item.final_score, reverse=True)
        rejected.sort(key=lambda item: item.final_score, reverse=True)
        selected = accepted[0] if accepted and accepted[0].final_score >= self.config.minimum_selection_score else None
        confidence = confidence_for(selected, accepted[1] if len(accepted) > 1 else None, self.config)
        if selected:
            selected.confidence = confidence
        elif substitutions:
            confidence = SUBSTITUTION_ONLY
        else:
            confidence = NO_SAFE_MATCH
        for item in accepted[1:limit]:
            item.confidence = confidence_for(item, None, self.config)

        result = MatchResult(
            raw_ingredient=ingredient_text,
            parsed_ingredient=parsed,
            normalized_ingredient_signature=query_profile.normalized_signature,
            selected_match=selected,
            compatible_alternatives=accepted[1:limit] if selected else accepted[:limit],
            substitution_candidates=substitutions[:limit],
            rejected_candidates=rejected[: min(20, candidate_limit)],
            confidence=confidence,
            final_score=selected.final_score if selected else 0.0,
            warnings=[] if selected else ["No safe exact match selected."],
            reason_codes=selected.reason_codes if selected else [confidence],
            cache_hit=False,
            retrieval_timing_ms=retrieval.retrieval_latency_ms,
            reranking_timing_ms=round((time.perf_counter() - rerank_started) * 1000, 2),
            total_timing_ms=round((time.perf_counter() - started) * 1000, 2),
            matcher_version=MATCHER_VERSION,
            product_index_version=retrieval.index_version or self.product_index_version(),
            override_version=self.overrides.version,
        )
        return result

    def _cached_selection_is_valid(self, result: MatchResult) -> bool:
        if result.selected_match is None:
            return True
        feature = self.feature_by_id.get(result.selected_match.product_id)
        return bool(feature and feature.get("eligible_for_retrieval"))

    def _forced_result(
        self,
        ingredient_text: str,
        query_profile: IngredientProfile,
        parsed: dict[str, Any],
        started: float,
    ) -> MatchResult | None:
        forbidden = {
            item.get("product_id")
            for item in self.overrides.matching_items("forbidden_products", query_profile.normalized_signature)
        }
        for item in self.overrides.matching_items("forced_matches", query_profile.normalized_signature):
            product_id = item.get("product_id")
            if not product_id or product_id in forbidden:
                continue
            feature = self.feature_by_id.get(product_id)
            if not feature or not feature.get("eligible_for_retrieval"):
                continue
            candidate = Candidate(
                product_id=product_id,
                original_product_name=feature.get("original_product_name") or feature.get("normalized_name"),
                normalized_name=feature.get("normalized_name"),
                record_status=feature.get("record_status"),
                canonical_ingredient=feature.get("canonical_name"),
                lexical_similarity=1.0,
                semantic_similarity=None,
                exact_match=True,
                retrieval_reason_codes=["manual_forced"],
            )
            product_profile = profile_from_feature(feature)
            ranked = score_candidate(candidate, feature, query_profile, product_profile, [], self.config, override_approved=True)
            ranked.confidence = EXACT
            return MatchResult(
                raw_ingredient=ingredient_text,
                parsed_ingredient=parsed,
                normalized_ingredient_signature=query_profile.normalized_signature,
                selected_match=ranked,
                compatible_alternatives=[],
                substitution_candidates=[],
                rejected_candidates=[],
                confidence=EXACT,
                final_score=ranked.final_score,
                warnings=[],
                reason_codes=["manual_forced"],
                cache_hit=False,
                retrieval_timing_ms=None,
                reranking_timing_ms=0.0,
                total_timing_ms=round((time.perf_counter() - started) * 1000, 2),
                matcher_version=MATCHER_VERSION,
                product_index_version=self.product_index_version(),
                override_version=self.overrides.version,
            )
        return None

    def match_recipe_ingredients(
        self,
        ingredients: list[str | dict[str, Any]],
        limit: int = 5,
        use_semantic: bool = True,
    ) -> list[MatchResult]:
        texts = []
        for ingredient in ingredients:
            if isinstance(ingredient, dict):
                text = ingredient.get("raw") or ingredient.get("display") or ingredient.get("name") or ""
            else:
                text = str(ingredient)
            if text:
                texts.append(text)
        if not texts:
            return []

        started_by_text = {text: time.perf_counter() for text in texts}
        profiles: dict[str, tuple[IngredientProfile, dict[str, Any], str]] = {}
        unique_queries: dict[str, str] = {}
        results_by_key: dict[str, MatchResult] = {}
        misses: list[tuple[str, IngredientProfile, dict[str, Any], str]] = []
        for text in texts:
            query_profile, parsed = profile_from_query(text, self.overrides)
            key = self.cache_key(query_profile, use_semantic=use_semantic)
            profiles[text] = (query_profile, parsed, key)
            cached = self.cache.get(key)
            if cached and self._cached_selection_is_valid(cached):
                result = copy.deepcopy(cached)
                result.cache_hit = True
                result.total_timing_ms = round((time.perf_counter() - started_by_text[text]) * 1000, 2)
                results_by_key[key] = result
                continue
            forced = self._forced_result(text, query_profile, parsed, started_by_text[text])
            if forced:
                self.cache.set(key, copy.deepcopy(forced))
                results_by_key[key] = forced
                continue
            if key not in unique_queries:
                unique_queries[key] = query_profile.normalized_signature
                misses.append((text, query_profile, parsed, key))

        if misses:
            miss_texts = [query_profile.normalized_signature for _text, query_profile, _parsed, _key in misses]
            try:
                retrievals = self.retriever.retrieve_product_candidates_batch(
                    miss_texts,
                    limit=80,
                    use_semantic=use_semantic,
                )
            except (AttributeError, TypeError):
                retrievals = [
                    self._retrieve_with_substitution_expansion(query_profile, 80, use_semantic)
                    for _text, query_profile, _parsed, _key in misses
                ]
            for (text, query_profile, parsed, key), retrieval in zip(misses, retrievals):
                result = self._match_from_retrieval(text, query_profile, parsed, retrieval, started_by_text[text], limit, 80)
                if (
                    result.selected_match is None
                    and culinary_substitution_queries(query_profile)
                    and not any("deterministic_substitution_query" in candidate.retrieval_reason_codes for candidate in retrieval.candidates)
                ):
                    expanded_retrieval = self._retrieve_with_substitution_expansion(query_profile, 80, use_semantic)
                    result = self._match_from_retrieval(text, query_profile, parsed, expanded_retrieval, started_by_text[text], limit, 80)
                self.cache.set(key, copy.deepcopy(result))
                results_by_key[key] = result

        ordered = []
        emitted_keys = set()
        for text in texts:
            _profile, _parsed, key = profiles[text]
            result = results_by_key[key]
            if key in emitted_keys:
                ordered.append(copy.deepcopy(result))
            else:
                ordered.append(result)
                emitted_keys.add(key)
        return ordered


_match_service_singleton: ProductMatchService | None = None


def get_product_match_service() -> ProductMatchService:
    global _match_service_singleton
    if _match_service_singleton is None:
        _match_service_singleton = ProductMatchService()
    return _match_service_singleton


def match_recipe_ingredient(ingredient_text: str, limit: int = 5) -> MatchResult:
    return get_product_match_service().match_recipe_ingredient(ingredient_text, limit=limit)


def match_recipe_ingredients(ingredients: list[str | dict[str, Any]], limit: int = 5) -> list[MatchResult]:
    return get_product_match_service().match_recipe_ingredients(ingredients, limit=limit)
