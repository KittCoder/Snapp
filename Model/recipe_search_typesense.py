from __future__ import annotations

import json
import os
import re
import hashlib
import time
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_PATH = REPO_ROOT / "data" / "snapp_search_corpus.jsonl"
DEFAULT_EXPORT_PATH = REPO_ROOT / "data" / "snapp_typesense_documents.jsonl"
DEFAULT_REVIEW_PATH = REPO_ROOT / "typesense_recipe_search_review.json"

DEFAULT_TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "localhost")
DEFAULT_TYPESENSE_PORT = os.getenv("TYPESENSE_PORT", "8108")
DEFAULT_TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
DEFAULT_TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY", "")
DEFAULT_TYPESENSE_COLLECTION = os.getenv("TYPESENSE_COLLECTION", "snapp_recipes")

MAX_QUERY_CHARS = 300
MAX_LIMIT = 50
DEFAULT_LIMIT = 10
EMBEDDING_MODEL = "ts/all-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384
DEFAULT_ALPHA = 0.7
KEYWORD_FIELDS = "title,normalized_title,ingredient_names,categories,search_text"


@lru_cache(maxsize=1)
def ingredient_vocabulary() -> dict[str, int]:
    # Derived from the existing corpus; never read or mutate recipe facts at query time.
    return json.loads(Path(__file__).with_name("ingredient_vocabulary.json").read_text())


def singular(word: str) -> str:
    return {"tomatoes": "tomato", "potatoes": "potato"}.get(word, word[:-1] if word.endswith("s") and not word.endswith("ss") else word)


@lru_cache(maxsize=512)
def ingredient_variants(term: str) -> tuple[str, ...]:
    tokens = [singular(w) for w in term.split()]
    variants = []
    for name in ingredient_vocabulary():
        words = [singular(w) for w in re.findall(r"[a-z]+", name)]
        if any(words[i:i + len(tokens)] == tokens for i in range(len(words))):
            variants.append(name)
    return tuple(sorted(set(variants + [term])))


@lru_cache(maxsize=1)
def implicit_ingredient_pattern():
    # Only complete, frequent ingredient names; never arbitrary tokens from names
    # such as "warm" (warm milk) or "ground" (ground beef).
    ambiguous = {"water", "ice", "half", "hot", "cold", "mixed", "all", "red", "green", "sweet", "meal", "dinner", "breakfast", "lunch", "quick", "light", "plain", "white", "mexican", "savory", "n", "sec", "extract", "cupchopped", "jalape", "cheesecloth", "skewers", "toothpicks"} | SUBJECTIVE_TERMS_TO_KEEP_AS_QUERY
    terms = {name for name, count in ingredient_vocabulary().items()
             if count >= 5 and name not in ambiguous and re.fullmatch(r"[a-z]+(?: [a-z]+){0,2}", name)}
    # Common ingredient heads can be rare as standalone corpus names (e.g.
    # beans vs black beans). Require observed compound-name evidence.
    for head in ("beans", "fish", "tofu", "lentils", "oats"):
        if len(ingredient_variants(head)) > 1:
            terms.add(head)
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in sorted(terms, key=lambda t: (-len(t), t))) + r")\b", re.I)


TIME_PATTERNS = (
    re.compile(r"\b(?:under|less than|fewer than|within|in|quick|maximum|max)\s+(\d{1,4})\s*(?:minutes?|mins?|min)\b", re.I),
    re.compile(r"\b(\d{1,4})\s*(?:minutes?|mins?|min)\s+or\s+less\b", re.I),
)
MIN_TIME_PATTERNS = (
    re.compile(r"\b(?:at least|over|more than|longer than|minimum|min)\s+(\d{1,4})\s*(?:minutes?|mins?|min)\b", re.I),
)
FORGET_TIME_PATTERN = re.compile(r"\b(?:forget|remove|clear|drop|ignore)\s+(?:the\s+)?(?:time|minute|duration|quick)\s*(?:limit|constraint|filter)?\b", re.I)
INCLUDE_PATTERNS = (
    re.compile(r"\b(?:with|using|use|has|have)\s+([a-z][a-z\s-]{1,40})(?=$|\b(?:under|less|without|no|and|for|dinner|lunch|breakfast)\b)", re.I),
)
EXCLUDE_PATTERNS = (
    re.compile(r"\b(?:without|no|exclude|hold|skip)\s+([a-z][a-z\s-]{1,40})(?=$|\b(?:under|less|with|and|for|dinner|lunch|breakfast)\b)", re.I),
)
ACTUALLY_PATTERN = re.compile(r"\bactually\s+([a-z][a-z\s-]{1,40})\b", re.I)

MEAL_TERMS = {
    "breakfast": "breakfast",
    "brunch": "breakfast",
    "lunch": "lunch_dinner",
    "dinner": "lunch_dinner",
    "supper": "lunch_dinner",
    "dessert": "dessert",
    "side": "side_dish",
    "snack": "snack",
    "appetizer": "appetizer",
    "drink": "drink",
}

DIETARY_CATEGORY_TERMS = {
    "vegetarian": "vegetarian",
    "vegan": "vegan",
}

SUBJECTIVE_TERMS_TO_KEEP_AS_QUERY = {
    "healthy",
    "cheap",
    "comfort",
    "winter",
    "warm",
    "easy",
    "creamy",
}


@dataclass(frozen=True)
class TypesenseConfig:
    host: str = DEFAULT_TYPESENSE_HOST
    port: str = DEFAULT_TYPESENSE_PORT
    protocol: str = DEFAULT_TYPESENSE_PROTOCOL
    api_key: str = field(default=DEFAULT_TYPESENSE_API_KEY, repr=False)
    collection: str = DEFAULT_TYPESENSE_COLLECTION
    timeout_seconds: float = 3.0

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


@dataclass
class SearchState:
    max_time: int | None = None
    min_time: int | None = None
    include_ingredients: list[str] = field(default_factory=list)
    exclude_ingredients: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    dietary: list[str] = field(default_factory=list)

    @classmethod
    def from_value(cls, value: Any) -> "SearchState":
        if isinstance(value, SearchState):
            return value
        if not isinstance(value, dict):
            return cls()
        return cls(
            max_time=coerce_positive_int(value.get("max_time")),
            min_time=coerce_positive_int(value.get("min_time")),
            include_ingredients=clean_terms(value.get("include_ingredients")),
            exclude_ingredients=clean_terms(value.get("exclude_ingredients")),
            categories=clean_terms(value.get("categories")),
            dietary=clean_terms(value.get("dietary")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_time": self.max_time,
            "min_time": self.min_time,
            "include_ingredients": self.include_ingredients,
            "exclude_ingredients": self.exclude_ingredients,
            "categories": self.categories,
            "dietary": self.dietary,
        }


class TypesenseUnavailable(RuntimeError):
    pass


class EmbeddingUnavailable(TypesenseUnavailable):
    pass


def coerce_positive_int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_token(value: Any) -> str:
    return normalize_text(value).casefold()


def clean_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        return []
    cleaned = []
    seen = set()
    for item in raw_values:
        term = normalize_token(item)
        term = re.sub(r"[^a-z0-9 _-]+", "", term).strip(" _-")
        if term and term not in seen:
            cleaned.append(term)
            seen.add(term)
    return cleaned


def stable_document_id(recipe: dict[str, Any]) -> str:
    source_id = normalize_text(recipe.get("source_id"))
    if source_id:
        return source_id
    source_index = recipe.get("source_index")
    if source_index is not None:
        return f"source-index-{source_index}"
    title = normalize_text(recipe.get("title"))
    digest = f"{title}|{json.dumps(recipe.get('ingredients') or [], sort_keys=True, ensure_ascii=True)}"
    return "recipe-" + hashlib.sha256(digest.encode("utf-8")).hexdigest()[:24]


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", normalize_token(title)).strip()


def ingredient_name(ingredient: Any) -> str:
    if isinstance(ingredient, dict):
        return normalize_text(ingredient.get("name"))
    return normalize_text(ingredient)


def ingredient_display(ingredient: Any) -> str:
    if not isinstance(ingredient, dict):
        return normalize_text(ingredient)
    pieces = [
        normalize_text(ingredient.get("quantity_text") or ingredient.get("quantity")),
        normalize_text(ingredient.get("unit")),
        normalize_text(ingredient.get("name")),
        normalize_text(ingredient.get("state")),
        normalize_text(ingredient.get("preparation")),
        normalize_text(ingredient.get("notes")),
    ]
    return normalize_text(" ".join(piece for piece in pieces if piece))


def number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    return None


def recipe_to_typesense_document(recipe: dict[str, Any]) -> dict[str, Any]:
    title = normalize_text(recipe.get("title"))
    meal_categories = clean_terms(recipe.get("meal_categories"))
    dish_categories = clean_terms(recipe.get("dish_categories"))
    categories = list(dict.fromkeys(meal_categories + dish_categories))
    ingredient_names = [name for name in (ingredient_name(item) for item in recipe.get("ingredients") or []) if name]
    ingredients_text = [text for text in (ingredient_display(item) for item in recipe.get("ingredients") or []) if text]
    equipment = clean_terms(recipe.get("equipment"))
    total_time = number_or_none(recipe.get("total_time_min"))
    cook_time = number_or_none(recipe.get("cook_time_min"))
    servings = number_or_none(recipe.get("servings"))
    document = {
        "id": stable_document_id(recipe),
        "source_id": normalize_text(recipe.get("source_id")),
        "source_index": int(recipe.get("source_index")) if isinstance(recipe.get("source_index"), int) else None,
        "title": title,
        "normalized_title": normalized_title(title),
        "ingredient_names": ingredient_names,
        "ingredients_text": ingredients_text,
        "ingredients": deepcopy(recipe.get("ingredients") or []),
        "instructions": deepcopy(recipe.get("instructions")),
        "categories": categories,
        "meal_categories": meal_categories,
        "dish_categories": dish_categories,
        "equipment": equipment,
        "accepted_stage": normalize_text(recipe.get("accepted_stage")),
        "total_time_minutes": total_time,
        "cook_time_minutes": cook_time,
        "servings": servings,
    }
    document["search_text"] = deterministic_search_text(document)
    return {key: value for key, value in document.items() if value is not None}


def deterministic_search_text(document: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "title",
        "normalized_title",
        "ingredient_names",
        "categories",
        "meal_categories",
        "dish_categories",
        "equipment",
        "accepted_stage",
    ):
        value = document.get(key)
        if isinstance(value, list):
            values.extend(normalize_text(item) for item in value if normalize_text(item))
        elif normalize_text(value):
            values.append(normalize_text(value))
    return normalize_text(" ".join(values))


def iter_corpus(path: Path | str = DEFAULT_CORPUS_PATH):
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                recipe = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on corpus line {line_number}") from exc
            if not isinstance(recipe, dict):
                raise ValueError(f"Corpus line {line_number} is not a JSON object")
            yield recipe


def export_documents(corpus_path=DEFAULT_CORPUS_PATH, export_path=DEFAULT_EXPORT_PATH) -> dict[str, Any]:
    processed = 0
    duplicate_ids = []
    seen_ids = set()
    export_path = Path(export_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", encoding="utf-8") as handle:
        for recipe in iter_corpus(corpus_path):
            processed += 1
            document = recipe_to_typesense_document(recipe)
            document_id = document["id"]
            if document_id in seen_ids:
                duplicate_ids.append(document_id)
            seen_ids.add(document_id)
            handle.write(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "processed": processed,
        "unique_document_ids": len(seen_ids),
        "duplicate_ids": duplicate_ids,
        "export_path": str(export_path),
    }


def typesense_collection_schema(collection_name: str = DEFAULT_TYPESENSE_COLLECTION) -> dict[str, Any]:
    return {
        "name": collection_name,
        "enable_nested_fields": False,
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "source_id", "type": "string", "facet": True},
            {"name": "source_index", "type": "int32", "optional": True},
            {"name": "title", "type": "string", "sort": True},
            {"name": "normalized_title", "type": "string"},
            {"name": "ingredient_names", "type": "string[]", "facet": True},
            {"name": "ingredients_text", "type": "string[]"},
            # Stored facts only: neither keyword nor vector search indexes these.
            {"name": "instructions", "type": "auto", "index": False, "optional": True},
            {"name": "categories", "type": "string[]", "facet": True},
            {"name": "meal_categories", "type": "string[]", "facet": True},
            {"name": "dish_categories", "type": "string[]", "facet": True},
            {"name": "equipment", "type": "string[]", "facet": True},
            {"name": "accepted_stage", "type": "string", "facet": True},
            {"name": "total_time_minutes", "type": "float", "optional": True, "facet": True},
            {"name": "cook_time_minutes", "type": "float", "optional": True, "facet": True},
            {"name": "servings", "type": "float", "optional": True, "facet": True},
            {"name": "search_text", "type": "string"},
            {"name": "ingredient_filter_tokens", "type": "string[]", "facet": True, "optional": True},
            {"name": "has_named_dairy", "type": "bool", "facet": True, "optional": True},
            {"name": "embedding", "type": "float[]", "num_dim": EMBEDDING_DIMENSION,
             "embed": {"from": KEYWORD_FIELDS.split(","),
                       "model_config": {"model_name": EMBEDDING_MODEL}}},
        ],
    }


def redact_secret(value: str) -> str:
    return "[redacted]" if value else ""


def typesense_request(config: TypesenseConfig, method: str, path: str, body: Any = None, query: dict[str, Any] | None = None, raw_response: bool = False):
    query_string = f"?{urlencode(query)}" if query else ""
    url = f"{config.base_url}{path}{query_string}"
    data = None
    headers = {"X-TYPESENSE-API-KEY": config.api_key}
    if body is not None:
        if isinstance(body, bytes):
            data = body
            headers["Content-Type"] = "text/plain"
        else:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
    request_object = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request_object, timeout=config.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            if raw_response:
                return payload
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404 and "embedding" not in payload.lower():
            raise
        error_type = EmbeddingUnavailable if exc.code in {400, 404, 422, 500, 503} and any(
            word in payload.lower() for word in ("embedding", "vector", "model")) else TypesenseUnavailable
        # Server payloads can echo credentials or documents: never expose them.
        raise error_type(f"Typesense request failed with HTTP {exc.code}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise TypesenseUnavailable(f"Typesense is unavailable at {config.base_url}") from exc


def get_recipe_by_id(recipe_id: str, config: TypesenseConfig | None = None):
    """Fetch one exact stored document, without search or an ID fallback."""
    config = config or TypesenseConfig()
    try:
        document = typesense_request(
            config, "GET",
            f"/collections/{quote(config.collection, safe='')}/documents/{quote(recipe_id, safe='')}",
            query={"exclude_fields": "embedding,search_text,ingredient_filter_tokens"})
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise TypesenseUnavailable("Recipe lookup is temporarily unavailable.") from None
    if not isinstance(document, dict) or document.get("id") != recipe_id:
        return None
    return document


def recreate_collection(config: TypesenseConfig):
    try:
        typesense_request(config, "DELETE", f"/collections/{config.collection}")
    except HTTPError as exc:
        if exc.code != 404:
            raise
    return typesense_request(config, "POST", "/collections", typesense_collection_schema(config.collection))


def import_documents(config: TypesenseConfig, documents_path: Path | str) -> dict[str, Any]:
    # Derived index metadata, never written back to canonical recipe facts.
    dairy_names = set(dairy_ingredient_names())
    documents = []
    for line in Path(documents_path).read_text().splitlines():
        if not line.strip():
            continue
        document = json.loads(line)
        document["ingredient_filter_tokens"] = ingredient_filter_tokens(document["ingredient_names"])
        document["has_named_dairy"] = bool(dairy_names.intersection(normalize_token(v) for v in document["ingredient_names"]))
        documents.append(json.dumps(document))
    body = "\n".join(documents).encode()
    started = time.perf_counter()
    response = typesense_request(
        config,
        "POST",
        f"/collections/{config.collection}/documents/import",
        body=body,
        query={"action": "upsert"},
        raw_response=True,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    lines = response.splitlines() if isinstance(response, str) else []
    failures = []
    successes = 0
    for index, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            failures.append({"line": index, "error": line[:240]})
            continue
        if item.get("success"):
            successes += 1
        else:
            failures.append({"line": index, "error": item.get("error"), "document": item.get("document")})
    return {"successes": successes, "failures": failures, "elapsed_ms": elapsed_ms}


def remove_matched(pattern: re.Pattern, query: str, callback):
    matches = list(pattern.finditer(query))
    for match in matches:
        callback(match)
    return pattern.sub(" ", query)


def parse_natural_language_query(query: str) -> tuple[str, dict[str, Any]]:
    remaining = normalize_text(query)[:MAX_QUERY_CHARS]
    constraints: dict[str, Any] = {
        "max_time": None,
        "min_time": None,
        "include_ingredients": [],
        "exclude_ingredients": [],
        "categories": [],
        "dietary": [],
        "clear_time": False,
        "replace_include_ingredients": False,
    }
    if FORGET_TIME_PATTERN.search(remaining):
        constraints["clear_time"] = True
        remaining = FORGET_TIME_PATTERN.sub(" ", remaining)

    for pattern in TIME_PATTERNS:
        def set_max(match):
            constraints["max_time"] = coerce_positive_int(match.group(1))
        remaining = remove_matched(pattern, remaining, set_max)

    for pattern in MIN_TIME_PATTERNS:
        def set_min(match):
            constraints["min_time"] = coerce_positive_int(match.group(1))
        remaining = remove_matched(pattern, remaining, set_min)

    def add_actual(match):
        term = clean_ingredient_phrase(match.group(1))
        if term:
            constraints["include_ingredients"] = [term]
            constraints["replace_include_ingredients"] = True
    remaining = remove_matched(ACTUALLY_PATTERN, remaining, add_actual)

    dairy_pattern = re.compile(r"\b(?:dairy[ -]free|without dairy)\b", re.I)
    if dairy_pattern.search(remaining):
        constraints["dietary"].append("dairy_free")
        remaining = dairy_pattern.sub(" ", remaining)

    # Match complete vocabulary names following a constraint marker, preserving
    # subjective trailing language and allowing lists ("with rice and beans").
    ingredient_pattern = implicit_ingredient_pattern()
    marker = re.compile(r"\b(without|no|exclude|hold|skip|with|using|use|has|have)\s+", re.I)
    spans = []
    for match in marker.finditer(remaining):
        pos = match.end()
        terms = []
        while True:
            item = ingredient_pattern.match(remaining, pos)
            if not item:
                break
            terms.append(normalize_token(item.group()))
            pos = item.end()
            separator = re.match(r"(?:\s+and\s+|,\s*)", remaining[pos:])
            if not separator or not ingredient_pattern.match(remaining, pos + separator.end()):
                break
            pos += separator.end()
        if terms:
            key = "exclude_ingredients" if match.group(1).lower() in {"without", "no", "exclude", "hold", "skip"} else "include_ingredients"
            constraints[key].extend(terms)
            spans.append((match.start(), pos))
    for start, end in reversed(spans):
        remaining = remaining[:start] + " " + remaining[end:]

    def implicit(match):
        constraints["include_ingredients"].append(normalize_token(match.group()))
        return " "
    remaining = ingredient_pattern.sub(implicit, remaining)

    lower_remaining = f" {normalize_token(remaining)} "
    for term, category in MEAL_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", lower_remaining):
            constraints["categories"].append(category)
    for term, dietary in DIETARY_CATEGORY_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", lower_remaining):
            constraints["dietary"].append(dietary)

    constraints["include_ingredients"] = clean_terms(constraints["include_ingredients"])
    constraints["exclude_ingredients"] = clean_terms(constraints["exclude_ingredients"])
    constraints["categories"] = clean_terms(constraints["categories"])
    constraints["dietary"] = clean_terms(constraints["dietary"])
    remaining = re.sub(r"\b(?:with|using|and|but)\s*$", " ", remaining, flags=re.I)
    cleaned_query = normalize_text(remaining)
    return cleaned_query, constraints


def clean_ingredient_phrase(value: str) -> str:
    value = normalize_token(value)
    value = re.sub(r"\b(?:recipe|recipes|meal|meals|dish|dishes|food|foods|something)\b", " ", value)
    value = re.sub(r"\b(?:under|less|than|for|that|is|are|but|and|or)\b.*$", " ", value)
    words = [word for word in re.findall(r"[a-z0-9-]+", value) if word not in SUBJECTIVE_TERMS_TO_KEEP_AS_QUERY]
    return normalize_text(" ".join(words[-3:]))


def merge_search_state(previous: Any, parsed_constraints: dict[str, Any], explicit: dict[str, Any] | None = None) -> SearchState:
    state = SearchState.from_value(previous)
    if parsed_constraints.get("clear_time"):
        state.max_time = None
        state.min_time = None
    if parsed_constraints.get("max_time") is not None:
        state.max_time = parsed_constraints["max_time"]
    if parsed_constraints.get("min_time") is not None:
        state.min_time = parsed_constraints["min_time"]
    if parsed_constraints.get("replace_include_ingredients"):
        state.include_ingredients = []
    state.include_ingredients = merge_terms(state.include_ingredients, parsed_constraints.get("include_ingredients"))
    state.exclude_ingredients = merge_terms(state.exclude_ingredients, parsed_constraints.get("exclude_ingredients"))
    state.categories = merge_terms(state.categories, parsed_constraints.get("categories"))
    state.dietary = merge_terms(state.dietary, parsed_constraints.get("dietary"))

    explicit = explicit or {}
    if explicit.get("max_time") is not None:
        state.max_time = coerce_positive_int(explicit.get("max_time"))
    if explicit.get("min_time") is not None:
        state.min_time = coerce_positive_int(explicit.get("min_time"))
    state.include_ingredients = merge_terms(state.include_ingredients, explicit.get("include_ingredients"))
    state.exclude_ingredients = merge_terms(state.exclude_ingredients, explicit.get("exclude_ingredients"))
    state.categories = merge_terms(state.categories, explicit.get("categories"))
    state.dietary = merge_terms(state.dietary, explicit.get("dietary"))
    return state


def merge_terms(existing: list[str], incoming: Any) -> list[str]:
    return list(dict.fromkeys(clean_terms(existing) + clean_terms(incoming)))


def quote_filter_value(value: str) -> str:
    return "`" + value.replace("`", "") + "`"


def ingredient_filter_tokens(names: list[str]) -> list[str]:
    # Explicit tokenization keeps tomato-basil distinct from tomatobasil and
    # gives inclusion/exclusion identical semantics, regardless of server defaults.
    return sorted({singular(token) for name in names for token in re.findall(r"[a-z]+", normalize_token(name))})


def ingredient_filter(term: str, exclude: bool = False) -> str:
    if re.fullmatch(r"[a-z]+", term):
        return f"ingredient_filter_tokens:{'!=' if exclude else '='}{quote_filter_value(singular(term))}"
    values = ",".join(quote_filter_value(v) for v in ingredient_variants(term))
    return f"ingredient_names:{'!=' if exclude else '='}[{values}]"


@lru_cache(maxsize=1)
def dairy_ingredient_names() -> tuple[str, ...]:
    # Conservative name-based exclusion only; not a certified dietary label.
    dairy_words = re.compile(r"\b(?:milk|cheese|cream|butter|yogurt|yoghurt|buttermilk|whey|ghee|cheddar|mozzarella|parmesan|feta|ricotta|mascarpone|brie|gouda|gruyere|provolone|half.and.half)\b")
    alternatives = re.compile(r"\b(?:almond|coconut|soy|soya|oat|cashew|peanut|apple|pumpkin|sunflower|vegan|nondairy|non.dairy|dairy.free|cocoa|cacao)\b|butter (?:beans|lettuce)")
    return tuple(name for name in ingredient_vocabulary()
                 if dairy_words.search(name) and not alternatives.search(name))


def recipe_signature(document: dict[str, Any]) -> tuple:
    return (normalize_text(normalized_title(document.get("title", ""))),
            tuple(sorted({normalize_text(normalized_title(v)) for v in document.get("ingredient_names", [])})))


def build_typesense_filter(state: SearchState) -> str:
    filters = []
    if state.max_time is not None:
        filters.append(f"total_time_minutes:<={state.max_time}")
    if state.min_time is not None:
        filters.append(f"total_time_minutes:>={state.min_time}")
    for ingredient in state.include_ingredients:
        filters.append(ingredient_filter(ingredient))
    for ingredient in state.exclude_ingredients:
        filters.append(ingredient_filter(ingredient, exclude=True))
    for category in state.categories:
        filters.append(f"categories:={quote_filter_value(category)}")
    for dietary in state.dietary:
        if dietary == "dairy_free":
            filters.append("has_named_dairy:=false")
        else:
            filters.append(f"categories:={quote_filter_value(dietary)}")
    return " && ".join(filters)


def search_recipes(
    query: str,
    limit: int = DEFAULT_LIMIT,
    max_time: int | None = None,
    min_time: int | None = None,
    include_ingredients: list[str] | None = None,
    exclude_ingredients: list[str] | None = None,
    categories: list[str] | None = None,
    dietary: list[str] | None = None,
    state: dict[str, Any] | SearchState | None = None,
    config: TypesenseConfig | None = None,
    mode: str = "hybrid",
    alpha: float = DEFAULT_ALPHA,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    request_started = time.perf_counter()
    config = config or TypesenseConfig()
    cleaned_query, parsed = parse_natural_language_query(query)
    merged_state = merge_search_state(
        state,
        parsed,
        {
            "max_time": max_time,
            "min_time": min_time,
            "include_ingredients": include_ingredients,
            "exclude_ingredients": exclude_ingredients,
            "categories": categories,
            "dietary": dietary,
        },
    )
    if mode not in {"keyword", "hybrid"} or not 0 <= alpha <= 1:
        raise ValueError("Expected keyword/hybrid mode and alpha between 0 and 1")
    effective_query = cleaned_query or "*"
    unique_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    candidate_limit = min(250, max(50, unique_limit * 5))
    search_params = {
        "q": effective_query[:MAX_QUERY_CHARS],
        "query_by": KEYWORD_FIELDS,
        "query_by_weights": "8,6,5,4,1",
        "num_typos": "2,1,1,1,2",
        "prefix": "true,false,true,true,false",
        "per_page": candidate_limit,
        "page": 1,
        "exhaustive_search": "false",
        "include_fields": "id,source_id,title,ingredient_names,categories,meal_categories,dish_categories,equipment,total_time_minutes,cook_time_minutes,servings",
    }
    filter_by = build_typesense_filter(merged_state)
    if filter_by:
        search_params["filter_by"] = filter_by
    active_mode = mode if effective_query != "*" else "keyword"
    fallback = False
    def set_hybrid_params():
        search_params.update(query_by=KEYWORD_FIELDS + ",embedding",
                             query_by_weights="8,6,5,4,1,0", num_typos="2,1,1,1,2,0",
                             prefix="true,false,true,true,false,false",
                             vector_query=f"embedding:([], k:250, alpha:{alpha})",
                             drop_tokens_threshold=0)
    if active_mode == "hybrid":
        set_hybrid_params()
    typesense_started = time.perf_counter()
    results, seen = [], set()
    duplicates_removed = 0
    server_latency = 0
    while True:
        try:
            payload = typesense_request(config, "POST", "/multi_search",
                                        body={"searches": [{"collection": config.collection, **search_params}]})
            response = payload["results"][0]
            if "error" in response:
                error = str(response["error"]).lower()
                error_type = EmbeddingUnavailable if any(word in error for word in ("embedding", "vector", "model")) else TypesenseUnavailable
                raise error_type("Typesense recipe search failed")
        except EmbeddingUnavailable:
            if active_mode != "hybrid" or not allow_fallback:
                raise
            active_mode, fallback = "keyword", True
            results, seen, duplicates_removed = [], set(), 0
            search_params["page"] = 1
            search_params.update(query_by=KEYWORD_FIELDS, query_by_weights="8,6,5,4,1",
                                 num_typos="2,1,1,1,2", prefix="true,false,true,true,false")
            search_params.pop("vector_query", None)
            search_params.pop("drop_tokens_threshold", None)
            continue
        except TypesenseUnavailable:
            raise
        except Exception as exc:
            raise TypesenseUnavailable(f"Typesense recipe search failed ({type(exc).__name__})") from None
        server_latency += response.get("search_time_ms", 0)
        hits = response.get("hits") or []
        for hit in hits:
            signature = recipe_signature(hit.get("document") or {})
            if signature in seen:
                duplicates_removed += 1
                continue
            seen.add(signature)
            results.append(format_search_hit(len(results) + 1, hit))
            if len(results) == unique_limit:
                break
        if len(results) >= unique_limit or len(hits) < candidate_limit or search_params["page"] * candidate_limit >= response.get("found", 0):
            break
        search_params["page"] += 1
    typesense_latency_ms = round((time.perf_counter() - typesense_started) * 1000, 2)
    return {
        "mode": active_mode,
        "requested_mode": mode,
        "alpha": alpha if active_mode == "hybrid" else None,
        "fallback": fallback,
        "duplicates_removed": duplicates_removed,
        "typesense_server_latency_ms": server_latency,
        "query": query,
        "effective_query": effective_query,
        "parsed_constraints": {key: value for key, value in parsed.items() if key not in {"clear_time", "replace_include_ingredients"}},
        "state": merged_state.to_dict(),
        "results": results,
        "typesense_latency_ms": typesense_latency_ms,
        "total_latency_ms": round((time.perf_counter() - request_started) * 1000, 2),
        "found": response.get("found", len(results)),
        "out_of": response.get("out_of"),
        "filter_by": filter_by,
    }


def format_search_hit(rank: int, hit: dict[str, Any]) -> dict[str, Any]:
    document = hit.get("document") or {}
    ingredients = document.get("ingredient_names") or []
    return {
        "rank": rank,
        "id": document.get("id"),
        "source_id": document.get("source_id"),
        "title": document.get("title"),
        "key_ingredients": ingredients[:8],
        "ingredient_names": ingredients,
        "time": document.get("total_time_minutes") or document.get("cook_time_minutes"),
        "total_time_minutes": document.get("total_time_minutes"),
        "cook_time_minutes": document.get("cook_time_minutes"),
        "servings": document.get("servings"),
        "categories": document.get("categories") or [],
        "meal_categories": document.get("meal_categories") or [],
        "dish_categories": document.get("dish_categories") or [],
        "equipment": document.get("equipment") or [],
        "relevance": {
            "vector_distance": hit.get("vector_distance"),
            "hybrid_search_info": hit.get("hybrid_search_info"),
            "text_match": hit.get("text_match"),
            "text_match_info": hit.get("text_match_info"),
            "highlights": hit.get("highlights") or [],
        },
    }
