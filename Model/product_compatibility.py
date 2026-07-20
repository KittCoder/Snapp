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


MATCHER_VERSION = "ingredient-product-matcher-v1.4"
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
        if text_has(text, rf"\b{species}\s+(?:broth|stock)\b"):
            return species
    return None


def detect_yogurt_flavor(text: str) -> str | None:
    if text_has(text, r"\bplain\b"):
        return "plain"
    for flavor in ("vanilla", "guava", "mango", "papaya", "strawberry", "blueberry", "peach", "banana", "coconut"):
        if text_has(text, rf"\b{flavor}\b"):
            return flavor
    return None


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

    if text_has(detection_text, r"\bkefir\b"):
        profile.family = "kefir"; profile.category = profile.category or "dairy"
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
    elif text_has(detection_text, r"\bbutter\b") and profile.family != "peanut butter":
        profile.family = "butter"; profile.category = profile.category or "dairy"
    elif text_has(detection_text, r"\bbuttermilk\b"):
        profile.family = "buttermilk"; profile.category = profile.category or "dairy"

    if text_has(
        detection_text,
        r"\bsteak sauce\b|\bbeef marinade\b|\bbeef gravy\b|\bgravy granules\b|\bdressing\b|\bgravy\b",
    ):
        profile.family = "sauce"; profile.category = profile.category or "pantry"
    if text_has(detection_text, r"\bdog food\b|\bcat food\b|\bdog treats?\b|\bcat treats?\b|\bmilk-bone\b|\bpurina\b|\bfriskies\b|\bfancy feast\b|\bmeow mix\b|\bpedigree\b|\bcesar\b"):
        profile.family = "pet food"; profile.category = "pet"
    if text_has(detection_text, r"\bsteak fries\b"):
        profile.family = "prepared meal"; profile.category = "prepared"

    if text_has(detection_text, r"\balmond butter\b|\bcashew butter\b|\bsunflower butter\b"):
        profile.family = "nut butter"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bpeanut butter\b"):
        profile.family = "peanut butter"; profile.category = profile.category or "pantry"

    flour_patterns = {
        "all-purpose flour": r"\ball[-\s]?purpose flour\b|\bplain flour\b",
        "bread flour": r"\bbread flour\b",
        "cake flour": r"\bcake flour\b",
        "almond flour": r"\balmond flour\b",
        "coconut flour": r"\bcoconut flour\b",
        "whole wheat flour": r"\bwhole wheat flour\b",
    }
    for flour_type, pattern in flour_patterns.items():
        if text_has(detection_text, pattern) or canonical == flour_type:
            profile.family = "flour"; profile.flour_type = flour_type
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
        "pasta sauce": r"\bpasta sauce\b|\bmarinara\b",
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
        profile.family = "bouillon"; profile.broth_type = "bouillon"
    elif text_has(detection_text, r"\bconsomm[eé]\b|\bconsomme\b"):
        profile.family = "broth"; profile.broth_type = "consomme"; profile.broth_species = broth_species
    elif text_has(detection_text, r"\bsoup\b"):
        profile.family = "soup"; profile.broth_type = "soup"
        if text_has(detection_text, r"\bcream(?:y)? of chicken soup\b|\bcream of chicken\b"):
            profile.soup_type = "cream of chicken"
        elif text_has(detection_text, r"\bcream(?:y)? of mushroom soup\b|\bcream of mushroom\b"):
            profile.soup_type = "cream of mushroom"
        elif text_has(detection_text, r"\bcream(?:y)? tomato soup\b|\btomato soup\b"):
            profile.soup_type = "tomato"

    if text_has(
        detection_text,
        r"\bbeef\s+(?:franks?|hot dogs?|wieners?|knockwurst|bologna|salami)\b|\b(?:franks?|hot dogs?|wieners?|knockwurst|bologna|salami)\b.*\bbeef\b",
    ):
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bbeef jerky\b|\bjerky\b.*\bbeef\b"):
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bcorned beef\b|\bpastrami\b|\broast beef\b.*\bsliced\b|\bsliced\b.*\broast beef\b|\blunch meat\b") or normalized == "roast beef":
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bchipped beef\b|\bcreamed chipped beef\b"):
        profile.family = "processed meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif text_has(detection_text, r"\bbeef liver\b|\bfresh beef liver\b"):
        profile.family = "organ meat"; profile.category = profile.category or "meat"; profile.meat_species = "beef"; profile.meat_cut = "liver"
    elif text_has(detection_text, r"\bbeef (?:feet|foot|bones?|marrow bones?|neck bones?|back bones?|hindshank)\b|\b(?:feet|foot|bones?|marrow bones?|neck bones?|back bones?|hindshank)\b.*\bbeef\b"):
        profile.family = "meat bones"; profile.category = profile.category or "meat"; profile.meat_species = "beef"
    elif profile.family in {"sauce", "pet food", "prepared meal"}:
        pass
    elif text_has(detection_text, r"\bbeef\s+(?:for\s+)?stew\b|\bstew(?:ing)?\s+(?:beef|meat)\b|\bbeef stew meat\b|\bstew meat\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "stew meat"
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
    elif text_has(detection_text, r"\b(shaved|sliced|thin sliced)\s+(?:steak\s+)?beef\b|\b(?:beef\s+)?(shaved|sliced)\s+steak\b|\bshaved steak beef\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "shaved beef"
    elif text_has(detection_text, r"\bground turkey\b"):
        profile.family = "ground meat"; profile.meat_species = "turkey"; profile.ground = True
    elif text_has(detection_text, r"\bpork\b"):
        profile.family = "pork"; profile.category = profile.category or "meat"; profile.meat_species = "pork"
    elif text_has(detection_text, r"\bham\b"):
        profile.family = "ham"; profile.category = profile.category or "meat"; profile.meat_species = "pork"
    elif text_has(detection_text, r"\bswordfish\b|\bsalmon\b|\bfish steak\b"):
        profile.family = "fish"; profile.category = profile.category or "meat"; profile.meat_species = "fish"
    elif text_has(detection_text, r"\bchicken breast\b"):
        profile.family = "meat cut"; profile.meat_species = "chicken"; profile.meat_cut = "breast"
    elif text_has(detection_text, r"\bchicken thighs?\b"):
        profile.family = "meat cut"; profile.meat_species = "chicken"; profile.meat_cut = "thigh"
    elif text_has(detection_text, r"\bchicken\b") and profile.family not in {"broth", "stock", "soup", "bouillon"}:
        profile.family = "chicken"; profile.category = profile.category or "meat"; profile.meat_species = "chicken"
    elif text_has(detection_text, r"\bskirt steak\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "skirt steak"
    elif text_has(detection_text, r"\bribeye\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "ribeye steak"
    elif text_has(detection_text, r"\bsirloin\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "sirloin steak"
    elif text_has(detection_text, r"\bhanger\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "hanger steak"
    elif text_has(detection_text, r"\bsteak\b"):
        profile.family = "meat cut"; profile.meat_species = "beef"; profile.meat_cut = "steak"
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

    if text_has(normalized, r"\bpancake mix\b") and not text_has(normalized, r"\bpotato pancake\b|\blatkes?\b"):
        profile.family = "pancake mix"
    elif text_has(normalized, r"\bpotato pancake\b|\blatkes?\b"):
        profile.family = "potato pancake mix"

    if text_has(normalized, r"\bcurry powder\b"):
        profile.family = "curry powder"; profile.category = profile.category or "pantry"
    if text_has(normalized, r"\bcorn starch\b|\bcornflour\b|\bcorn flour\b"):
        profile.family = "corn starch"; profile.category = "pantry"
    if text_has(detection_text, r"\bwalnuts?\b"):
        profile.family = "walnuts"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bpecans?\b|\bpecan meats?\b"):
        profile.family = "pecans"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\balmonds?\b") and profile.family != "milk":
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
    elif text_has(detection_text, r"\btabasco\b|\bhot sauce\b|\bsriracha\b"):
        profile.family = "hot sauce"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bvinegar\b"):
        profile.family = "vinegar"; profile.category = profile.category or "pantry"
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
    elif text_has(detection_text, r"\bhoney\b") and profile.category not in {"meat", "snacks", "prepared"} and profile.family not in {"ham"}:
        profile.family = "honey"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bginger\b") and profile.category != "prepared":
        profile.family = "ginger"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bbay leaves?\b|\bbay leaf\b"):
        profile.family = "bay leaf"; profile.category = profile.category or "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bshortening\b"):
        profile.family = "shortening"; profile.category = profile.category or "pantry"
    elif text_has(detection_text, r"\bsalt\b") and profile.family not in {"seasoning"}:
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
        and profile.family not in {"tuna", "meat cut", "ground meat", "beef", "chicken", "pork", "ham", "sausage"}
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

    if text_has(
        detection_text,
        r"\bpot pie\b|\bfrozen meal\b|\bfrozen dinners?\b|\balfredo\b|\bmacaroni (?:and|&) (?:cheese|beef)\b|\bbeef barley vegetable\b|\bbeef chili\b|\bchili\b.*\bbeef\b|\bbeef flavor\b|\bflavor noodles?\b|\bramen\b|\bpho bowl\b|\bgerber\b|\bcovered raisins\b|\bmashed potatoes\b|\bcakes?\b|\bcheesecake\b|\bcupcakes?\b|\bdips?\b|\bpizza\b|\bravioli\b|\btortelloni\b|\bpierogi\b|\btortillas?\b|\bwraps?\b|\bbaby food\b|\bpouch\b|\bbeef stew with\b|\bdinty moore\b|\bchicken parmesan\b|\btaquitos?\b|\bchallah\b|\brolls?\b|\bonion rings?\b|\bfunyuns?\b|\bfrench onion\b.*\bdip\b|\bdip\b.*\bfrench onion\b|\bonion dip\b|\bonion gravy\b|\bonion bagels?\b|\bhummus\b|\bpopcorn\b|\bcrackers?\b|\bchips?\b|\bmrs ts\b",
    ):
        profile.family = "prepared meal"
        profile.category = "prepared"

    if text_has(detection_text, r"\bapple juice\b|\bjuice drink\b|\bfruit juice\b|\bsnapple\b"):
        profile.family = "juice"; profile.category = profile.category or "beverage"
        if text_has(detection_text, r"\bapple\b"):
            profile.produce_type = "apple"
    elif text_has(detection_text, r"\bapples?\b"):
        profile.family = "apple"; profile.category = profile.category or "produce"; profile.produce_type = "apple"
    elif text_has(detection_text, r"\bpineapple\b") and profile.family not in {"prepared meal", "yogurt"}:
        profile.family = "pineapple"; profile.category = profile.category or "pantry"
        if text_has(detection_text, r"\btinned\b|\bcanned\b|\bcan\b|\bslices?\b|\bchunks?\b|\bcrushed\b"):
            profile.freshness = profile.freshness or "canned"

    if text_has(detection_text, r"\bcelery salt\b|\bcelery seed\b|\bgarlic powder\b|\bgranulated garlic\b|\bgarlic salt\b"):
        profile.family = "seasoning"; profile.category = "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bgranulated onion\b|\bonion powder\b|\bdried onion\b|\bonions? minced\b|\bminced onions?\b") and not text_has(normalized_raw_text, r"\b\d+(?:\.\d+)?\s+onions?\b"):
        profile.family = "seasoning"; profile.category = "pantry"; profile.freshness = "dried"
    elif text_has(detection_text, r"\bscallions?\b|\bgreen onions?\b"):
        profile.family = "green onion"; profile.category = profile.category or "produce"; profile.produce_type = "green onion"
    elif text_has(detection_text, r"\bonions?\b") and profile.family not in {"green onion", "prepared meal"}:
        profile.family = "onion"; profile.category = profile.category or "produce"; profile.produce_type = "onion"
        if text_has(normalized_raw_text, r"\b\d+(?:\.\d+)?\s+onions?\b"):
            profile.freshness = "fresh"

    generic_pepper = (
        canonical == "peppers"
        and text_has(normalized_raw_text, r"\bpepper\b")
        and not text_has(normalized_raw_text, r"^\s*\d")
        and not text_has(normalized_raw_text, r"\b(green|red|yellow|orange|bell|sweet|jalapeno|jalapeño|chili|chile)\s+pepper\b")
    )
    if text_has(detection_text, r"\bmarinade\b"):
        profile.family = "marinade"; profile.category = profile.category or "pantry"
    if profile.family in {"cheese", "prepared meal", "marinade"}:
        pass
    elif text_has(detection_text, r"\bjalapeno(?:s)?\b|\bjalapeño(?:s)?\b|\bchili peppers?\b|\bchile peppers?\b|\bchipotle pepper\b|\bajicito\b|\bpepper paste\b|\bpepper sauce\b|\bhot sauce\b"):
        profile.family = "hot pepper"; profile.category = profile.category or "produce"; profile.produce_type = "hot pepper"
    elif text_has(normalized_raw_text, r"^\s*\d+(?:\.\d+)?(?:\s+\d+)?\s+peppers?\b"):
        profile.family = "bell pepper"; profile.category = "produce"; profile.produce_type = "bell pepper"
    elif generic_pepper or text_has(detection_text, r"\bcayenne pepper\b|\bblack pepper\b|\bcrushed red pepper\b|\bred pepper flakes\b|^pepper$|\bpeppercorns?\b"):
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

    if text_has(detection_text, r"\bgrape tomatoes\b|\bcherry tomatoes\b|\bfresh tomatoes\b"):
        profile.family = "fresh tomato"; profile.category = profile.category or "produce"; profile.produce_type = "tomato"
    if text_has(detection_text, r"\bcelery\b") and not text_has(detection_text, r"\bcelery salt\b|\bcelery seed\b"):
        profile.family = "celery"; profile.category = profile.category or "produce"; profile.produce_type = "celery"
    if (
        profile.family in COMMON_PRODUCE_CANONICALS
        and text_has(detection_text, r"\bpasta\b|\blinguine\b|\bspaghetti\b|\bpenne\b|\bravioli\b|\btortelloni\b|\bpierogi\b|\bpizza\b|\bdips?\b|\bhummus\b|\bbaby food\b|\bpouch\b|\btortillas?\b|\bwraps?\b")
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
    return profile


def compatibility_signals(query: IngredientProfile, product: IngredientProfile) -> list[CompatibilitySignal]:
    signals: list[CompatibilitySignal] = []

    if query.family and product.family:
        if query.family == product.family:
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, f"family {query.family} matches"))
        elif query.family == "chicken" and product.family == "meat cut" and product.meat_species == "chicken":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "chicken cut satisfies generic chicken"))
        elif query.family == "beef" and product.meat_species == "beef":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "beef meat satisfies generic beef"))
        elif query.family == "cooking oil" and product.family in {"olive oil", "sesame oil", "coconut oil"}:
            signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, f"{product.family} can satisfy generic cooking oil"))
        elif query.family == "cream" and product.family == "heavy cream":
            signals.append(CompatibilitySignal("base_family", COMPATIBLE, "heavy cream satisfies generic cream"))
        elif {query.family, product.family} <= {"broth", "stock"}:
            signals.append(CompatibilitySignal("base_family", SOFT_PREFERENCE, "broth and stock are close substitutions"))
        else:
            signals.append(CompatibilitySignal("base_family", HARD_REJECT, f"{product.family} is not {query.family}"))
    else:
        signals.append(CompatibilitySignal("base_family", UNKNOWN, "family is incomplete"))

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
        if query.salted_status and product.salted_status and query.salted_status != product.salted_status:
            signals.append(CompatibilitySignal("salted_status", STRONG_PENALTY, f"{product.salted_status} does not satisfy {query.salted_status}"))
        if query.salted_status and not product.salted_status:
            signals.append(CompatibilitySignal("salted_status", UNKNOWN, "salted status is unavailable"))

    if query.family == "heavy cream" and product.family in {"half-and-half", "whipped topping"}:
        signals.append(CompatibilitySignal("cream_type", HARD_REJECT, f"{product.family} is not heavy cream"))
    if query.family == "heavy cream" and text_has(product.normalized_signature, r"\bhalf and half\b|\bwhipped topping\b|\breddi-wip\b"):
        signals.append(CompatibilitySignal("cream_type", HARD_REJECT, "cream substitute is not heavy cream"))
    if query.family == "cream" and product.family in {"sour cream", "ice cream", "cream cheese", "whipped topping"}:
        signals.append(CompatibilitySignal("cream_type", HARD_REJECT, f"{product.family} is not pourable cream"))

    if query.freshness == "fresh" and product.freshness in {"dried", "canned", "frozen"}:
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
        signals.append(CompatibilitySignal("freshness_specific", STRONG_PENALTY, f"{product.freshness} does not satisfy {query.freshness}"))

    if query.family == "ground meat":
        if product.family != "ground meat":
            signals.append(CompatibilitySignal("ground_meat", HARD_REJECT, "whole cuts are not ground meat"))
        elif query.meat_species and product.meat_species and query.meat_species != product.meat_species:
            signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
    if query.category == "meat" and product.category == "meat" and query.meat_species and product.meat_species and query.meat_species != product.meat_species:
        signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
    if query.family == "beef" and product.family in {"sausage", "pork", "sauce", "processed meat", "broth", "stock", "soup", "bouillon", "prepared meal", "pet food", "organ meat", "meat bones"}:
        signals.append(CompatibilitySignal("beef_identity", HARD_REJECT, f"{product.family} is not beef"))
    if query.family == "beef" and product.category and product.category != "meat":
        signals.append(CompatibilitySignal("beef_identity", HARD_REJECT, f"{product.category} product is not beef meat"))
    if query.family == "beef" and product.family == "ground meat":
        signals.append(CompatibilitySignal("beef_form", STRONG_PENALTY, "ground or formed beef is not a whole beef cut"))
    if query.family == "meat cut" and product.family == "meat cut":
        if query.meat_species and product.meat_species and query.meat_species != product.meat_species:
            signals.append(CompatibilitySignal("meat_species", HARD_REJECT, "meat species differs"))
        if query.meat_cut and product.meat_cut and query.meat_cut != product.meat_cut:
            signals.append(CompatibilitySignal("meat_cut", HARD_REJECT, "meat cut differs"))
    if query.family == "chicken" and product.family in {"broth", "stock", "soup", "bouillon"}:
        signals.append(CompatibilitySignal("chicken_identity", HARD_REJECT, f"{product.family} is not chicken meat"))
    if query.family == "tuna" and text_has(product.normalized_signature, r"\bsalad\b|\bsandwich\b|\bwrap\b|\bpasta\b"):
        signals.append(CompatibilitySignal("tuna_identity", HARD_REJECT, "prepared tuna item is not plain tuna"))
    if query.family == "broth" and product.family in {"meat cut", "ground meat", "soup", "bouillon"}:
        severity = HARD_REJECT if product.family in {"meat cut", "ground meat", "soup"} else STRONG_PENALTY
        signals.append(CompatibilitySignal("broth_identity", severity, f"{product.family} is not broth"))
    if query.family == "broth" and product.family == "broth" and query.broth_species and product.broth_species and query.broth_species != product.broth_species:
        signals.append(CompatibilitySignal("broth_species", HARD_REJECT, f"{product.broth_species} stock does not satisfy {query.broth_species}"))
    if query.family == "soup" and query.soup_type and product.soup_type != query.soup_type:
        signals.append(CompatibilitySignal("soup_type", HARD_REJECT, f"{product.soup_type or 'generic soup'} is not {query.soup_type} soup"))

    if query.family == "flour" and product.family == "flour" and query.flour_type and product.flour_type and query.flour_type != product.flour_type:
        signals.append(CompatibilitySignal("flour_type", HARD_REJECT, f"{product.flour_type} is not {query.flour_type}"))
    if "gluten-free" in query.dietary_requirements and "gluten-free" not in product.dietary_requirements:
        signals.append(CompatibilitySignal("gluten_free", HARD_REJECT, "gluten-free requirement is not verified"))
    if query.family in {"baking powder", "baking soda"} and product.family != query.family:
        signals.append(CompatibilitySignal("leavener_identity", HARD_REJECT, f"{product.family} is not {query.family}"))
    if query.family == "yeast" and product.family == "nutritional yeast":
        signals.append(CompatibilitySignal("yeast_type", HARD_REJECT, "nutritional yeast is not baking yeast"))
    if query.family == "pancake mix" and product.family == "potato pancake mix":
        signals.append(CompatibilitySignal("pancake_mix_type", HARD_REJECT, "potato pancake mix is not pancake mix"))

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
    return min(0.12, bonus)


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
    canonical_match = bool(query_profile.canonical and query_profile.canonical == product_profile.canonical)
    family_match = bool(query_profile.family and query_profile.family == product_profile.family) or any(
        signal.rule == "base_family" and signal.classification == COMPATIBLE
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
    conflicts = [asdict(signal) for signal in signals if signal.classification in {STRONG_PENALTY, HARD_REJECT, UNKNOWN}]
    reason_codes = list(candidate.retrieval_reason_codes)
    if canonical_match:
        reason_codes.append("canonical_match")
    if family_match:
        reason_codes.append("family_match")
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

    def cache_key(self, profile: IngredientProfile) -> str:
        index_version = self.product_index_version() or "no-index"
        return "|".join(
            [
                MATCHER_VERSION,
                index_version,
                self.overrides.version,
                profile.normalized_signature,
                profile.fat_level or "",
                profile.salted_status or "",
                profile.freshness or "",
                ",".join(sorted(profile.dietary_requirements)),
            ]
        )

    def match_recipe_ingredient(self, ingredient_text: str, limit: int = 5, candidate_limit: int = 50) -> MatchResult:
        started = time.perf_counter()
        query_profile, parsed = profile_from_query(ingredient_text, self.overrides)
        key = self.cache_key(query_profile)
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

        retrieval = self.retriever.retrieve_product_candidates(query_profile.normalized_signature, limit=candidate_limit)
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

    def match_recipe_ingredients(self, ingredients: list[str | dict[str, Any]], limit: int = 5) -> list[MatchResult]:
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
            key = self.cache_key(query_profile)
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
                self.cache.set(key, forced)
                results_by_key[key] = forced
                continue
            if key not in unique_queries:
                unique_queries[key] = query_profile.normalized_signature
                misses.append((text, query_profile, parsed, key))

        if misses:
            retrievals = self.retriever.retrieve_product_candidates_batch(
                [query for _text, query_profile, _parsed, _key in misses for query in [query_profile.normalized_signature]],
                limit=50,
            )
            for (text, query_profile, parsed, key), retrieval in zip(misses, retrievals):
                result = self._match_from_retrieval(text, query_profile, parsed, retrieval, started_by_text[text], limit, 50)
                self.cache.set(key, result)
                results_by_key[key] = result

        ordered = []
        for text in texts:
            _profile, _parsed, key = profiles[text]
            ordered.append(copy.deepcopy(results_by_key[key]))
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
