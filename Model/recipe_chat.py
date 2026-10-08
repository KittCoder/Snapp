"""Local, stateless conversation orchestration over the frozen Typesense search.

Model outputs are suggestions, never recipe facts or user-visible free-form text.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from functools import lru_cache
import importlib
import math
import os
import re
import time
from typing import Any, Protocol

import recipe_search_typesense as retrieval
import recipe_chat_language as language


class Intent(str, Enum):
    NEW_SEARCH = "NEW_SEARCH"
    REFINE_SEARCH = "REFINE_SEARCH"
    SELECT_RESULT = "SELECT_RESULT"
    QUESTION_ABOUT_SELECTED_RECIPE = "QUESTION_ABOUT_SELECTED_RECIPE"
    COMPARE_RESULTS = "COMPARE_RESULTS"
    CLEAR_CONSTRAINT = "CLEAR_CONSTRAINT"
    GENERAL_FOLLOWUP = "GENERAL_FOLLOWUP"


LIST_FIELDS = ("include_ingredients", "exclude_ingredients", "categories", "dietary")
FACT_FIELDS = ("id", "title", "ingredient_names", "ingredients_text", "total_time_minutes",
               "cook_time_minutes", "categories", "servings", "instructions", "equipment")
ORDINAL = re.compile(r"\b(first|second|third|fourth|fifth|last)\b|\b(?:number\s*|#\s*)(\d+)\b", re.I)
PROTEINS = {"beef", "chicken", "turkey", "pork", "lamb", "fish", "salmon", "shrimp", "tofu"}
LIMITATION = "Dietary tags are incomplete; ingredient filters can match broth or sauce derivatives and are not dietary guarantees."


@dataclass
class RecipeChatState(retrieval.SearchState):
    semantic_query: str = ""
    last_result_ids: list[str] = field(default_factory=list)
    selected_recipe_id: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_value(cls, value):
        if value is None:
            return cls()
        if isinstance(value, cls):
            value = value.to_dict()
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise ValueError("state must be an object containing only supported state fields.")
        state = cls()
        for key in LIST_FIELDS + ("last_result_ids",):
            items = value.get(key, [])
            limit = 5 if key == "last_result_ids" else 20
            if not isinstance(items, list) or len(items) > limit or any(
                not isinstance(x, str) or not x.strip() or len(x) > 160 for x in items
            ):
                raise ValueError(f"state.{key} must be a bounded list of nonempty strings.")
            setattr(state, key, list(dict.fromkeys(items)) if key == "last_result_ids" else retrieval.clean_terms(items))
        for key in ("max_time", "min_time"):
            number = value.get(key)
            if number is not None and (type(number) is not int or not 1 <= number <= 10000):
                raise ValueError(f"state.{key} must be null or a positive integer up to 10000.")
            setattr(state, key, number)
        query = value.get("semantic_query", "")
        if not isinstance(query, str) or len(query) > retrieval.MAX_QUERY_CHARS:
            raise ValueError("state.semantic_query must be a string of at most 300 characters.")
        state.semantic_query = query.strip()
        selected = value.get("selected_recipe_id")
        if selected is not None and (not isinstance(selected, str) or selected not in state.last_result_ids):
            raise ValueError("selected_recipe_id must belong to last_result_ids.")
        state.selected_recipe_id = selected
        if state.max_time and state.min_time and state.min_time > state.max_time:
            raise ValueError("min_time cannot exceed max_time.")
        return state

    def has_search(self):
        return bool(self.semantic_query or self.last_result_ids or self.max_time or self.min_time
                    or any(getattr(self, key) for key in LIST_FIELDS))


class RecipeChatModel(Protocol):
    """Adapters must bound network timeouts and return JSON-compatible dictionaries.

    interpret: {"semantic_query": "soft preference"}, only for unresolved turns.
    compose: {"ordered_recipe_ids": [...]}, an exact permutation of supplied IDs.
    No prose, facts, new IDs, or constraint updates are accepted from a model.
    """
    def interpret(self, message: str, context: dict[str, Any]) -> dict[str, Any]: ...
    def compose(self, context: dict[str, Any]) -> dict[str, Any]: ...


@lru_cache(maxsize=4)
def load_model(factory_path: str):
    if not factory_path:
        return None
    try:
        module, factory = factory_path.split(":", 1)
        model = getattr(importlib.import_module(module), factory)()
        return model if callable(getattr(model, "interpret", None)) and callable(getattr(model, "compose", None)) else None
    except Exception:
        # Never surface adapter exceptions, which can contain provider secrets.
        return None


def configured_service():
    config = retrieval.TypesenseConfig(
        host=os.getenv("TYPESENSE_HOST", "localhost"), port=os.getenv("TYPESENSE_PORT", "8108"),
        protocol=os.getenv("TYPESENSE_PROTOCOL", "http"), api_key=os.getenv("TYPESENSE_API_KEY", ""),
        collection=os.getenv("TYPESENSE_COLLECTION", "snapp_recipes"),
    )
    return RecipeChatService(config=config, model=load_model(os.getenv("SNAPP_RECIPE_CHAT_MODEL_FACTORY", "")))


def public_recipe(document):
    return {key: deepcopy(document[key]) for key in FACT_FIELDS if key in document}


def compact_context(recipes):
    return [{"id": r["id"], "title": r.get("title", "")[:160],
             "key_ingredients": [x[:80] for x in r.get("ingredient_names", [])[:8]],
             "total_time_minutes": r.get("total_time_minutes"),
             "cook_time_minutes": r.get("cook_time_minutes"),
             "categories": r.get("categories", [])[:8], "servings": r.get("servings")}
            for r in recipes[:5]]


def semantic_text(text):
    return language.semantic_text(text)


def ordinal_index(message, length):
    match = ORDINAL.search(message)
    if not match:
        return None
    if match.group(2):
        return int(match.group(2)) - 1
    return {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "last": length - 1}[match.group(1).lower()]


def recipe_line(recipe):
    title = recipe.get("title") or "Untitled indexed recipe"
    total = recipe.get("total_time_minutes")
    cook = recipe.get("cook_time_minutes")
    timing = f"{total:g} minutes total" if isinstance(total, (int, float)) else (
        f"{cook:g} minutes cooking; total time not recorded" if isinstance(cook, (int, float)) else "time not recorded")
    return f"{title} — {timing}"


class RecipeChatService:
    def __init__(self, config=None, model: RecipeChatModel | None = None):
        self.config = config or retrieval.TypesenseConfig()
        self.model = model

    def fetch_recipe(self, recipe_id):
        document = retrieval.get_recipe_by_id(recipe_id, self.config)
        return public_recipe(document) if document is not None else None

    def search(self, state, limit=5):
        # The existing parser, filters, deduplication and keyword fallback stay intact.
        return retrieval.search_recipes(state.semantic_query or "*", limit=limit,
                                        state=retrieval.SearchState.from_value(state.to_dict()),
                                        config=self.config, mode="hybrid", alpha=0.7, allow_fallback=True)

    def select_result(self, message, state, fetch):
        index = ordinal_index(message, len(state.last_result_ids))
        if index is None or not 0 <= index < len(state.last_result_ids):
            return None, "That result is not in the last result list. Choose an available number or start a search."
        recipe = fetch(state.last_result_ids[index])
        if recipe is None:
            return None, "That recipe is no longer available. Please run a new search."
        state.selected_recipe_id = recipe["id"]
        return recipe, recipe_line(recipe)

    def answer_recipe_question(self, message, recipe):
        if recipe is None:
            return "Select a recipe first, for example: show me the second one."
        lower = message.lower()
        if re.search(r"\b(?:how long|time|minutes)\b", lower):
            return recipe_line(recipe)
        if re.search(r"\b(?:how (?:do|can) i (?:make|cook)|instructions|steps|method)\b", lower):
            steps = recipe.get("instructions")
            if isinstance(steps, list) and steps and all(isinstance(x, str) for x in steps):
                return "Stored instructions:\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(steps, 1))
            if isinstance(steps, str) and steps.strip():
                return "Stored instructions:\n" + steps
            return "The indexed recipe does not contain cooking instructions."
        if re.search(r"\b(?:servings|serves|people|portions)\b", lower):
            return f"Stored servings: {recipe['servings']}." if recipe.get("servings") is not None else "Servings are not recorded for this recipe."
        names = recipe.get("ingredient_names")
        if re.search(r"\b(?:what ingredients|list (?:the )?ingredients)\b", lower):
            return "Stored ingredients: " + "; ".join(recipe.get("ingredients_text") or names) + "." if names else "Ingredients are not recorded for this recipe."
        ingredient = re.search(r"\b(?:have|has|use|uses|contain|contains|include|includes)\s+(.+?)[?.!]*$", lower)
        if ingredient:
            term = re.sub(r"^(?:any|some)\s+", "", ingredient.group(1)).strip(" .?!")
            if not names:
                return "Ingredients are not recorded for this recipe."
            tokens = set(retrieval.ingredient_filter_tokens([term]))
            matches = [name for name in names if tokens and tokens <= set(retrieval.ingredient_filter_tokens([name]))]
            if matches:
                return "The stored ingredient list names: " + "; ".join(matches) + ". This does not establish allergen safety."
            return f"The stored ingredient list does not name {term}. That does not establish that the recipe is free of it."
        if re.search(r"\b(?:vegan|vegetarian|dairy.free|healthy|healthiest|safe|allerg|cost|cheap|price)\b", lower):
            return "The stored data cannot establish that claim. " + LIMITATION
        if "categor" in lower:
            return "Stored categories: " + ", ".join(recipe.get("categories") or []) + "."
        return "I can answer from stored ingredients, times, servings, categories, or cooking instructions when available."

    def compare_results(self, message, state, fetch):
        if not state.last_result_ids:
            return "Run a search first so there are results to compare."
        ids = state.last_result_ids
        if re.search(r"first\s+(?:two|2)\b", message, re.I):
            if len(ids) < 2:
                return "There are fewer than two results to compare."
            ids = ids[:2]
        elif ORDINAL.search(message):
            indexes = [ordinal_index(m.group(), len(ids)) for m in ORDINAL.finditer(message)]
            if any(i is None or not 0 <= i < len(ids) for i in indexes):
                return "One of those result numbers is not in the last result list."
            ids = list(dict.fromkeys(ids[i] for i in indexes))
        recipes = [fetch(recipe_id) for recipe_id in ids]
        if any(r is None for r in recipes):
            return "A referenced recipe is no longer available. Please run a new search."
        lower = message.lower()
        if re.search(r"health|cheap|cost|best|people", lower):
            return "The available data cannot reliably rank these recipes by health, cost, or suitability for a household."
        metric = "total_time_minutes" if re.search(r"fast|quick|time", lower) else "ingredient_names" if "fewer ingredients" in lower else None
        if metric:
            if any(r.get(metric) is None for r in recipes):
                return "Some recipes lack the stored data needed for a complete comparison."
            values = [(len(r[metric]) if metric == "ingredient_names" else r[metric], r) for r in recipes]
            best = min(v for v, _ in values)
            winners = [r for v, r in values if v == best]
            label = "Fewest listed ingredients" if metric == "ingredient_names" else "Shortest recorded total time"
            unit = "ingredients" if metric == "ingredient_names" else "minutes"
            return f"{label}: " + "; ".join(r.get("title") or r["id"] for r in winners) + f" — {best:g} {unit}."
        return "Stored recipe comparison:\n" + "\n".join(
            recipe_line(r) + (f"; {len(r['ingredient_names'])} listed ingredients" if r.get("ingredient_names") is not None else "; ingredient count not recorded")
            for r in recipes)

    def update_state(self, state, message, fetch):
        """Interpret conversation operations without modifying retrieval rules."""
        state = RecipeChatState.from_value(state)
        preference, parsed = language.parse_message(message)
        if parsed.get("unsupported_negative_category"):
            return state, parsed, "I can filter for meal or dietary categories, but cannot reliably exclude that category. Which ingredient or meal would you prefer?", False
        clear = parsed.get("operation") == "clear" or parsed.get("clear_time", False)
        if parsed.get("operation") == "clear":
            target = parsed["clear_target"]
            if target in {"time", "time limit", "minute", "duration"}:
                state.max_time = state.min_time = None
            elif target in {"ingredients", "ingredient", "ingredient inclusions"}:
                state.include_ingredients = []
            elif target in {"exclusions", "ingredient exclusions"}:
                state.exclude_ingredients = []
            elif target in {"category", "categories", "meal", "meal category"}:
                state.categories = []
            elif target in {"dietary", "diet", "dietary restrictions"}:
                state.dietary = []
            elif target in {"preferences", "semantic preferences"}:
                state.semantic_query = ""
            elif target in retrieval.MEAL_TERMS:
                state.categories = [x for x in state.categories if x != retrieval.MEAL_TERMS[target]]
            elif target in retrieval.DIETARY_CATEGORY_TERMS or target in {"dairy", "dairy-free"}:
                dietary = retrieval.DIETARY_CATEGORY_TERMS.get(target, "dairy_free")
                state.dietary = [x for x in state.dietary if x != dietary]
            else:
                negative = re.fullmatch(r"(?:no|without) (.+)", target)
                term = negative.group(1) if negative else target
                # Natural "restriction"/"fine" clearing favors an exclusion;
                # explicit "remove chicken" still clears its active inclusion.
                keys = ("exclude_ingredients",) if negative or parsed.get("allowance") else ("exclude_ingredients", "include_ingredients")
                removed = False
                for key in keys:
                    old = getattr(state, key)
                    matches = [x for x in old if retrieval.singular(x) == retrieval.singular(term)]
                    if matches:
                        setattr(state, key, [x for x in old if x not in matches])
                        removed = True
                        break
                if not removed:
                    return state, parsed, "I could not identify that constraint. Name an ingredient, time limit, category, or dietary restriction to remove.", False
            parsed["removed_constraint"] = target
            return state, parsed, None, True

        incoming = parsed["include_ingredients"]
        if parsed.get("replace_ingredients") and incoming:
            old = state.include_ingredients
            target = parsed.get("replace_target")
            if target:
                if target not in old:
                    return state, parsed, "That ingredient is not an active inclusion. Name the ingredient you want to replace.", False
                state.include_ingredients = [x for x in old if x != target]
            elif any(x in PROTEINS for x in incoming):
                state.include_ingredients = [x for x in old if x not in PROTEINS]
            elif len(old) <= 1:
                state.include_ingredients = []
            elif not parsed["exclude_ingredients"]:
                return state, parsed, "Which ingredient should I replace? Try: replace rice with pasta.", False
        if parsed.get("clear_time"):
            state.max_time = state.min_time = None
        for key in ("max_time", "min_time"):
            if parsed.get(key) is not None:
                setattr(state, key, parsed[key])
        # A new exclusion removes its conflicting inclusion, retaining unrelated
        # ingredients and all previous exclusions. Positive reversals need undo.
        excluded_tokens = set(retrieval.ingredient_filter_tokens(parsed["exclude_ingredients"]))
        state.include_ingredients = [x for x in state.include_ingredients
                                    if not excluded_tokens.intersection(retrieval.ingredient_filter_tokens([x]))]
        for key in LIST_FIELDS:
            incoming = parsed[key]
            if incoming:
                setattr(state, key, list(incoming) if key == "categories" else list(dict.fromkeys(getattr(state, key) + incoming)))
        if parsed.get("relative_time"):
            baseline = state.max_time
            if baseline is None:
                ids = [state.selected_recipe_id] if state.selected_recipe_id else state.last_result_ids
                times = [(fetch(i) or {}).get("total_time_minutes") for i in ids]
                known = [t for t in times if isinstance(t, (int, float)) and t > 0]
                baseline = min(known) if known else None
            if baseline is None or baseline <= 1:
                return state, parsed, "What maximum total time in minutes would you like?", False
            # Existing documented heuristic: 75% of cap/shortest result time.
            # Explicit numeric limits in the same message take precedence.
            if parsed.get("max_time") is None:
                state.max_time = max(1, math.floor(baseline * 0.75))
                parsed["relative_max_time"] = state.max_time
        if state.min_time and state.max_time and state.min_time > state.max_time:
            return state, parsed, "That time limit conflicts with the minimum time. Remove or change one of the time limits.", clear
        conflict = set(retrieval.ingredient_filter_tokens(state.include_ingredients)) & set(retrieval.ingredient_filter_tokens(state.exclude_ingredients))
        if conflict:
            return state, parsed, "That conflicts with an active ingredient exclusion. Remove the exclusion explicitly before including that ingredient.", clear
        if preference:
            state.semantic_query = retrieval.normalize_text(" ".join(dict.fromkeys((state.semantic_query + " " + preference).split())))[:300]
        return state, parsed, None, clear

    def compose_response(self, results, state):
        if self.model and results:
            try:
                output = self.model.compose({"recipes": compact_context(results)})
                ids = output.get("ordered_recipe_ids") if isinstance(output, dict) and set(output) == {"ordered_recipe_ids"} else None
                originals = [r["id"] for r in results]
                if isinstance(ids, list) and len(ids) == len(originals) and all(isinstance(i, str) for i in ids) and set(ids) == set(originals):
                    by_id = {r["id"]: r for r in results}
                    results = [by_id[i] for i in ids]
            except Exception:
                pass
        state.last_result_ids = [r["id"] for r in results]
        if not results:
            return results, "No matches for the current constraints. You can change an ingredient or remove a time limit."
        message = "Here are a few matches:\n" + "\n".join(f"{i}. {recipe_line(r)}" for i, r in enumerate(results, 1))
        message += '\nYou can say “something quicker”, “no cheese”, or “show me the second one”.'
        return results, message

    def handle_message(self, message, state=None):
        started = time.perf_counter()
        if not isinstance(message, str) or not message.strip() or len(message) > 300:
            raise ValueError("message must be a nonempty string of at most 300 characters.")
        state = RecipeChatState.from_value(state)
        message = retrieval.normalize_text(message)
        lower = language.normalize(message)
        results, selected, parsed = [], None, {}
        metadata = {"typesense_latency_ms": 0.0, "typesense_server_latency_ms": 0,
                    "mode": None, "fallback": False, "alpha": None, "typesense_query": None,
                    "recipe_lookup_ids": []}
        cache = {}

        def fetch(recipe_id):
            if recipe_id not in cache:
                ts_start = time.perf_counter()
                cache[recipe_id] = self.fetch_recipe(recipe_id)
                metadata["recipe_lookup_ids"].append(recipe_id)
                metadata["typesense_latency_ms"] += (time.perf_counter() - ts_start) * 1000
            return cache[recipe_id]

        question = bool(re.search(r"^(?:does|do|is|are|can|how|what|list)\b", lower)) and not language.SEARCH_REQUEST.search(lower)
        compare = bool(re.search(r"\bcompare\b|^which\b", lower))
        reset = bool(re.match(r"^(?:new search|start over|reset)(?:\b|$)", lower))
        if compare:
            intent = Intent.COMPARE_RESULTS
            reply = self.compare_results(message, state, fetch)
        elif ORDINAL.search(message) and not question:
            intent = Intent.SELECT_RESULT
            selected, reply = self.select_result(message, state, fetch)
        elif question:
            intent = Intent.QUESTION_ABOUT_SELECTED_RECIPE
            if ORDINAL.search(message):
                selected, reply = self.select_result(message, state, fetch)
                if selected:
                    reply = self.answer_recipe_question(message, selected)
            else:
                selected = fetch(state.selected_recipe_id) if state.selected_recipe_id else None
                reply = self.answer_recipe_question(message, selected)
                if state.selected_recipe_id and selected is None:
                    state.selected_recipe_id = None
                    reply = "That recipe is no longer available. Please select another result or search again."
        else:
            if reset:
                state = RecipeChatState()
                message = re.sub(r"^(?:new search|start over|reset)(?:\s+for)?[:\s]*", "", message, flags=re.I)
            new_state, parsed, clarification, cleared = self.update_state(state, message, fetch)
            changed = new_state.to_dict() != state.to_dict()
            intent = Intent.CLEAR_CONSTRAINT if cleared else Intent.REFINE_SEARCH if state.has_search() else Intent.NEW_SEARCH
            general = lower in language.GENERAL
            alternatives = parsed.get("operation") == "alternatives"
            if alternatives and not state.has_search():
                intent = Intent.GENERAL_FOLLOWUP
                clarification = "Search for an ingredient or meal first, then I can show alternatives."
            if not clarification and (general or (not changed and not cleared and not alternatives)):
                intent = Intent.GENERAL_FOLLOWUP
                reply = "Tell me an ingredient, meal, or time limit, or select a result by number."
                if self.model and not reset and not general and not parsed.get("neutral_ingredients"):
                    try:
                        suggestion = self.model.interpret(message, {"state": state.to_dict()})
                        soft = suggestion.get("semantic_query") if isinstance(suggestion, dict) and set(suggestion) == {"semantic_query"} else None
                        if isinstance(soft, str) and 0 < len(soft.strip()) <= 120:
                            _, constraints = retrieval.parse_natural_language_query(soft)
                            if not any(constraints.values()):
                                new_state.semantic_query = (state.semantic_query + " " + soft.strip()).strip()[:300]
                                changed, general = True, False
                                intent = Intent.REFINE_SEARCH if state.has_search() else Intent.NEW_SEARCH
                    except Exception:
                        pass
            if clarification:
                reply = clarification
            elif (changed and not general) or cleared or alternatives:
                previous_ids = list(state.last_result_ids)
                state = new_state
                state.selected_recipe_id = None
                payload = self.search(state, limit=50 if alternatives else 5)
                candidates = [public_recipe(r) for r in payload["results"]]
                if alternatives:
                    candidates = [r for r in candidates if r["id"] not in previous_ids]
                results = candidates[:5]
                if alternatives and not results:
                    # No hidden reset or repeated rejected recipes when exhausted.
                    state.last_result_ids = list(previous_ids)
                    reply = "No more alternatives match the current constraints. You can change an ingredient or remove a time limit."
                else:
                    results, reply = self.compose_response(results, state)
                metadata.update({key: payload[key] for key in ("mode", "fallback", "alpha", "typesense_server_latency_ms")})
                metadata["typesense_latency_ms"] += payload["typesense_latency_ms"]
                metadata["typesense_query"] = {"q": payload["effective_query"], "filter_by": payload["filter_by"], "mode": payload["mode"], "alpha": payload["alpha"]}
                if parsed.get("relative_max_time"):
                    reply = f"Using a maximum total time of {state.max_time} minutes.\n" + reply
                if state.dietary:
                    reply += "\n" + LIMITATION
                if re.search(r"\b(?:cheap\w*|health\w*|best for|for (?:\d+|four) people)\b", lower):
                    reply += "\nCost, health ranking, and household suitability cannot be guaranteed from the available data."
        metadata["typesense_latency_ms"] = round(metadata["typesense_latency_ms"], 2)
        metadata["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return {"message": reply, "intent": intent.value, "state": state.to_dict(), "results": results,
                "selected_recipe": selected, "search_metadata": metadata, "parsed_constraints": parsed}
