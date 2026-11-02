# Local recipe conversation service

`recipe_chat.py` wraps the existing `recipe_search_typesense.search_recipes` function. It does not build or change the index, generate recipes, call the old `/chat` flow, or require a conversational model. The existing `/api/recipes/search` route remains independent.

## Run locally

Use the backend's Python environment and existing dependencies. Configure `TYPESENSE_HOST`, `TYPESENSE_PORT`, `TYPESENSE_PROTOCOL`, `TYPESENSE_API_KEY`, and `TYPESENSE_COLLECTION` in the process environment. Defaults are `localhost`, `8108`, `http`, and `snapp_recipes`; the API key has no default. No environment file is loaded automatically.

Start the existing Flask app from the repository root:

```sh
PYTHONPATH=Model python -m flask --app model run --port 5000
```

Send requests to `POST /api/recipes/chat`:

```json
{"message": "I want chicken for dinner", "state": null}
```

For every subsequent turn, send the complete `state` returned by the previous response:

```json
{
  "message": "under 30 minutes",
  "state": {
    "semantic_query": "",
    "include_ingredients": ["chicken"],
    "exclude_ingredients": [],
    "categories": ["lunch_dinner"],
    "dietary": [],
    "max_time": null,
    "min_time": null,
    "last_result_ids": [],
    "selected_recipe_id": null
  }
}
```

The empty result-ID array above is for illustration; preserve actual returned IDs when continuing a conversation. State is JSON serializable, bounded and validated, and never mutated in place. State is carried by the caller, not a server conversation database or authenticated history. A selected ID must belong to the supplied last-result list, and every selection/question/comparison refetches the authoritative document from Typesense. Unknown or deleted IDs cannot produce a recipe.

## Response

Responses have these keys:

| Field | Meaning |
| --- | --- |
| `request_id` | Existing Flask request correlation ID |
| `message` | Deterministically rendered response |
| `intent` | Intent name below |
| `state` | Updated complete state |
| `results` | Up to five retrieved recipes, in displayed order; empty for non-search turns |
| `selected_recipe` | Authoritative selected document fields, or null |
| `parsed_constraints` | Existing deterministic parser output plus applied conversational operation details |
| `search_metadata` | `latency_ms`, `typesense_latency_ms`, `typesense_server_latency_ms`, `mode`, `fallback`, `alpha`, `typesense_query`, `recipe_lookup_ids` |

Recipe objects expose only stored fields: ID, title, ingredient names/text, total/cook time, categories, servings, and instructions if present. They do not contain embeddings, search text, or raw search relevance internals. A missing field remains missing. `typesense_query` is null on non-search turns; `recipe_lookup_ids` records document reads. Wall-clock Typesense latency includes document reads; server search latency is only the server-reported search time. `alpha` is 0.7 for hybrid searches and null for keyword/filter-only searches or non-search turns.

Invalid messages/state return 400, oversized payloads use the backend's existing 413 behavior, and unavailable search/document reads return sanitized 503 errors. Messages are limited to 300 characters to match the retrieval parser. OPTIONS returns 204. This endpoint is exempt from unrelated product matcher warmup.

## Deterministic conversation behavior

Supported intents: `NEW_SEARCH`, `REFINE_SEARCH`, `SELECT_RESULT`, `QUESTION_ABOUT_SELECTED_RECIPE`, `COMPARE_RESULTS`, `CLEAR_CONSTRAINT`, `GENERAL_FOLLOWUP`.

- Ingredient inclusions/exclusions, categories, dietary terms and explicit minute limits use the existing parser first. Follow-ups preserve existing constraints and semantic preferences.
- `actually beef instead` replaces an existing simple protein inclusion while retaining rice and exclusions. `replace rice with pasta` and `beef instead of chicken` name the exact replacement. Ambiguous replacements ask for clarification. New meal categories replace the previous meal category.
- `forget the time limit` clears both bounds. `remove chicken` removes an inclusion; `remove no cheese` removes an exclusion. `remove category`, `remove dietary restrictions`, and `remove preferences` clear the corresponding constraint group. Conflicting inclusions/exclusions or time bounds ask for clarification and preserve the previous state.
- `something quicker` sets the maximum time to 75% of the active maximum, rounded down, or 75% of the shortest known total time in the last results. The response states the chosen limit. It asks for an explicit maximum if no total time is known. It does not substitute cook time for total time.
- `the first one`, `the second one`, `number 3`, and `the last one` resolve against the displayed `last_result_ids`. Out-of-range references never invent IDs. A new search/refinement clears the previous selection and replaces the reference list, even when it returns no results.
- Selected-recipe questions read stored ingredients, total/cook time, servings, categories, or instructions. Missing instructions/servings are reported as missing. Named-ingredient checks describe what is listed and do not infer allergen safety or assert an ingredient-free guarantee.
- Comparisons support shortest total time, fewest listed ingredients, first two results, and explicitly numbered results. Missing comparison fields prevent a complete ranking. Unsupported health/cost/household rankings are declined.
- `new search for ...`, `start over`, and `reset` clear conversation state. Ordinary short greetings/acknowledgements preserve it.

Examples exercised against the live index:

1. `I want chicken for dinner` → `under 30 minutes` → `no cheese` → `actually beef instead`: ends with beef + lunch/dinner + maximum 30 minutes + cheese exclusion.
2. `I want a warm winter meal` → `with beef` → `something quicker`: preserves the warm/winter preference and beef inclusion; the inspected result set produced a 26-minute maximum.
3. `breakfast with eggs` → `show me the second one` → `does it use milk?`: resolves the second returned ID and checks its stored ingredient names. Cooking instructions and servings are explicitly reported missing when absent from that document.

## Optional model interface

`RecipeChatModel` is a provider-independent protocol. Leave `SNAPP_RECIPE_CHAT_MODEL_FACTORY` blank for deterministic mode. To plug in a local adapter, set it to `package.module:create_model`; the no-argument factory must return an object implementing both methods. Adapters own their vendor configuration and secrets in environment variables and must set bounded request timeouts/retries. This implementation ships no vendor adapter and no external model is needed or tested live.

- `interpret(message, context)` is used only for an unresolved/general turn. The only accepted output is `{"semantic_query": "short soft preference"}`. Outputs containing parser-recognized hard constraints or additional keys are ignored. It cannot change exclusions, times, categories, IDs, or selection.
- `compose(context)` receives at most five small records: ID, clipped title, up to eight clipped ingredient names, recorded times, categories and servings. The only accepted output is `{"ordered_recipe_ids": [...]}`, an exact permutation of the retrieved IDs. Order is reflected in both rendered text and ordinal state.
- Neither hook can provide user-visible free text or recipe facts. Unsupported/malformed output and adapter exceptions fall back to deterministic behavior. Recipe titles, times and other factual text always come from stored data. The context is a copy, so a model adapter cannot mutate returned facts.

This intentionally constrained composition interface favors grounding over fluent free-form model prose. More expressive composition would need a separate factual validation design.

## Review and tests

```sh
python -m unittest discover -s Model/tests -p 'test_recipe_chat.py'
python -m unittest discover -s Model/tests -p 'test_recipe_search*.py'
python scripts/review_recipe_chat.py
```

The review script uses the same environment configuration, reads the live index only, and writes the ignored `recipe_chat_review.json`. It records each turn's input, intent, before/after state, parser audit, search query, returned IDs/titles, selected recipe, response and latency. It never writes the API key, raw server errors, embeddings, or a recipe corpus. The default 12 conversations contain 44 turns; failed live requests are marked incomplete, not replaced with fixture output. An alternate output location is available via `--output`.

The chat tests use the real parser/search function with a fixture Typesense transport. They exercise multi-turn state and grounding, including hostile model outputs, authoritative document refetches, API validation, alpha 0.7 and embedding-error keyword fallback. They do not require a local server.

## Current limitations

The deterministic grammar is intentionally limited; ambiguous or unfamiliar phrasings may need an explicit ingredient, time limit, ordinal, or reset. Relative speed uses a documented heuristic. Filter-only queries use the existing keyword/wildcard ordering. Relevance, incomplete vegetarian tags, and broth/sauce derivative matches remain properties of the frozen retrieval system. No guarantee of dietary suitability, allergen safety, reliable cost, health ranking, or household-sized servings is added. The current index usually lacks servings and does not index cooking instructions, so this implementation cannot answer those missing facts. No corpus, frontend, database, or deployment changes are part of this work.
