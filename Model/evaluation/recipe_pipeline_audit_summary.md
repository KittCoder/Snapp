# Recipe Pipeline Audit Summary

## Pipeline Map
- Source recipe files: `Model/all_recipes.json`, `Model/recipes.json`, `Model/USDA recipes.json`.
- Current production source path: local recipe records are converted through source adapters into canonical ingredient records, then exposed as Spoonacular-style ingredients for existing UI code.
- Ingredient parser entry point: `ingredient_normalization.parse_ingredient`.
- Quantity normalization: `basket_quantity.canonical_quantity` converts mass, volume, and count units; unsafe mass-volume conversion stays unknown unless density exists.
- Semantic query construction: `product_retrieval.query_embedding_text` removes recipe quantity/package text and retains identity attributes.
- Lexical retrieval: token/canonical indexes in `ProductCandidateRetriever.lexical_search_space` and `lexical_candidates`.
- Vector retrieval: persisted local index in `Model/morton_williams_vector_index` via `ProductCandidateRetriever.retrieve_product_candidates_batch`.
- Compatibility filtering/ranking: `ProductMatchService._match_from_retrieval`, `compatibility_signals`, and `score_candidate`.
- Package parsing/optimization/aggregation: `basket_quantity.parse_package_info`, `calculate_coverage`, `calculate_cost`, `BasketBuilder.build_multi_recipe_basket`.

## Transformations And Loss Risks
- Source `raw`, `quantity`, `unit`, `name`, and `note` are adapted into `CanonicalRecipeIngredient`; trusted structured quantity/unit are preserved.
- Matcher text is reconstructed from canonical fields; source `raw_text` and `source_fields` are retained for provenance.
- `parse_ingredient` can still remove preparation words and split alternatives; identity-defining forms must be listed as meaningful modifiers or aliases.
- `query_embedding_text` drops quantity/unit by design; package metadata does not affect embeddings.
- Basket aggregation uses `ingredient_aggregation_signature`; attributes absent from profile can cause over-aggregation.

## Audit Size
- Recipes sampled: 800
- Recipes contributing audited ingredients: 694
- Ingredient lines audited: 5000
- Runtime: 149255.39 ms
- Unmatched ingredients: 1021 (20.4%)
- Package metadata present on selected products: 3616 (72.3%)
- Failure report artifact: `Model/evaluation/recipe_pipeline_failure_reports.json`

## Source Counts
- Public Domain Recipes: 460
- USDA MyPlate Kitchen: 234

## Schema Counts
- structured_ingredient_dict: 5000

## Confidence Counts
- medium: 2655 (53.1%)
- no_safe_match: 1019 (20.4%)
- exact: 861 (17.2%)
- low: 311 (6.2%)
- high: 152 (3.0%)
- substitution_only: 2 (0.0%)

## Failure Distribution
- no suspicious condition: 1875 (37.5%)
- selected product identity requires review: 1253 (25.1%)
- unmatched ingredient: 1021 (20.4%)
- missing or unsafe quantity conversion: 818 (16.4%)
- legitimate no-match or non-purchase ingredient: 749 (15.0%)
- quantity inferred when absent: 487 (9.7%)
- low confidence: 311 (6.2%)
- fresh/frozen/canned/dried distinction: 182 (3.6%)
- count unit: 158 (3.2%)
- raw versus cooked distinction: 114 (2.3%)
- unit already structured but discarded: 67 (1.3%)
- package metadata weak: 25 (0.5%)
- canonical ingredient missing: 13 (0.3%)
- range quantity: 9 (0.2%)

## Performance
- memory: {'max_rss_kb': 959397888}
- one_ingredient: {'basket_reported_cached_ms': 0.1, 'basket_reported_uncached_ms': 794.24, 'checkout_cost': None, 'ingredient_count': 1, 'warm_cached_ms': 0.1, 'warm_uncached_ms': 794.33}
- one_recipe: {'basket_reported_cached_ms': 8.95, 'basket_reported_uncached_ms': 485.27, 'checkout_cost': 6.99, 'ingredient_count': 8, 'warm_cached_ms': 8.95, 'warm_uncached_ms': 494.08}
- sixty_recipes: {'basket_reported_cached_ms': 486.78, 'basket_reported_uncached_ms': 11257.09, 'checkout_cost': 417.59, 'ingredient_count': 480, 'warm_cached_ms': 487.59, 'warm_uncached_ms': 11471.67}
- ten_recipes: {'basket_reported_cached_ms': 58.27, 'basket_reported_uncached_ms': 1921.75, 'checkout_cost': 68.46, 'ingredient_count': 80, 'warm_cached_ms': 58.42, 'warm_uncached_ms': 1980.0}

## Stage Metrics
- compatibility_safe_candidate_presence: 0.9986
- hard_conflict_selection_count: 0
- lexical_candidate_presence: 0.9914
- quantity_known_or_intentionally_absent_rate: 0.895
- selected_match_rate: 0.7958
- semantic_candidate_presence: 1.0
- unmatched_rate: 0.2042

## Golden Evaluation
- compatibility_safe_recall: 0.52
- final_top_1_accuracy: 0.31
- final_top_3_recall: 0.52
- hard_conflict_selection_count: 0
- lexical_top_10_recall: 0.5267
- lexical_top_30_recall: 0.54
- merged_top_30_recall: 0.5467
- semantic_top_10_recall: 0.5233
- semantic_top_30_recall: 0.5467

## Manual Review Ingredients
- water: 134
- olive oil: 41
- cold water: 24
- boiling water: 22
- shortening: 19
- cloves: 17
- lard: 16
- fat: 16
- cream: 16
- hot water: 15
- broken ice: 14
- margarine: 12
- lemon: 11
- piece lemon peel: 9
- seasoning: 8
- ketchup: 7
- gin: 7
- dripping: 7
- italian vermouth: 7
- orange juice: 7
- warm water: 6
- nuts: 6
- orange: 6
- cocktail cherry: 6
- yeast cake: 6
- turnips: 6
- cracker crumbs: 6
- brandy: 5
- french vermouth: 5
- whipping cream: 5
- sour cream: 5
- cooking spray: 5
- veal: 5
- oysters: 5
- allspice: 5
- coconut: 4
- soda water: 4
- apricots: 4
- gravy: 4
- currants: 4
- dry sherry: 4
- herbs: 4
- spareribs: 4
- lemon worth of juice: 4
- juice of lemon: 4
- sage: 4
- nonstick cooking spray: 4
- dill: 4
- italian seasoning: 4
- pimento: 4
