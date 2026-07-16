# Phase 3 Failed Top-1 Audit

Baseline: 16 failed top-1 cases before cleanup. This audit was generated before applying fixes.

## case-008 - dried parsley

- Expected acceptable product/family: parsley flakes (parsley flakes, dried parsley)
- Selected product: Simply Organic Parsley
- Confidence: medium
- Failure category: scoring/weight issue
- Resolution: explicit dried/flakes evidence now outranks inferred dried herb products; fixture already covered flakes

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Simply Organic Parsley | 0.7202 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0686, semantic_similarity=0.0917, attribute_compatibility=0.13 | none |
| 2 | alt | McCormick Parsley Flakes | 0.7142 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0649, semantic_similarity=0.0894, attribute_compatibility=0.13 | none |
| 3 | alt | McCormick Parsley Flakes | 0.7142 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0649, semantic_similarity=0.0894, attribute_compatibility=0.13 | none |
| 4 | alt | Plain Parsley | 0.7 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0831, semantic_similarity=0.0973, attribute_compatibility=0.13 | none |
| 5 | alt | Lawry's® Coarse Ground With Parsley Garlic Salt | 0.6963 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0414, semantic_similarity=0.0949, attribute_compatibility=0.13 | none |

## case-019 - gluten-free flour

- Expected acceptable product/family: gluten free flour (gluten free flour)
- Selected product: None
- Confidence: no_safe_match
- Failure category: missing canonical identity
- Resolution: generic flour family detection added; fixture accepts gluten-free brown rice flour as valid gluten-free flour

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | alt | Bob's Red Mill Gluten Free All Purpose Baking Flour | 0.3893 | lexical_similarity=0.0573, semantic_similarity=0.0985, category_compatibility=0.07, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 2 | alt | MASECA Corn Masa Flour, Gluten Free, Instant | 0.3742 | lexical_similarity=0.0447, semantic_similarity=0.0959, category_compatibility=0.07, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 3 | alt | Bob's Red Mill 1-to-1 Baking Flour, Gluten Free | 0.3711 | lexical_similarity=0.0387, semantic_similarity=0.0989, category_compatibility=0.07, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 4 | alt | Kikkoman Marinade & Sauce, Gluten-Free, Less Sodium, Teriyaki | 0.3674 | lexical_similarity=0.0499, semantic_similarity=0.0841, category_compatibility=0.07, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 5 | alt | Bob's Red Mill Gluten Free Chocolate Cake Mix | 0.3137 | semantic_similarity=0.0882, category_compatibility=0.07, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |

## case-039 - 2% milk

- Expected acceptable product/family: 2% reduced fat milk (2% reduced fat milk, reduced fat milk)
- Selected product: Organic Valley® 2% Milk
- Confidence: medium
- Failure category: ambiguous evaluation case
- Resolution: milk fat percent added; 2% no longer ranks behind 1%; fixture accepts semantically correct 2% milk wording

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Organic Valley® 2% Milk | 0.8079 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0781, semantic_similarity=0.0998, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 2 | alt | a2 Milk 2% Reduced Fat Milk | 0.8067 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.07, semantic_similarity=0.1067, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 3 | alt | Lactaid 2% Reduced Fat Milk | 0.8051 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.07, semantic_similarity=0.1051, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 4 | alt | Lactaid 2% Reduced Fat Milk | 0.8051 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.07, semantic_similarity=0.1051, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 5 | alt | Borden 2% Milk Singles, American | 0.7957 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0646, semantic_similarity=0.1011, category_compatibility=0.07, attribute_compatibility=0.13 | none |

## case-043 - oat milk

- Expected acceptable product/family: oat milk (oat milk, oatmilk)
- Selected product: a2 Milk Whole Milk
- Confidence: medium
- Failure category: under-aggressive conflict rule
- Resolution: plant milk now hard-rejects dairy milk and other plant milk kinds

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | a2 Milk Whole Milk | 0.807 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0852, semantic_similarity=0.0918, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 2 | alt | Elmhurst Unsweetened Oat Milk | 0.7854 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.06, semantic_similarity=0.0954, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 3 | alt | GODIVA Milk Chocolate | 0.7848 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0635, semantic_similarity=0.0912, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 4 | alt | a2 Milk Grassfed Whole Milk | 0.7835 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.066, semantic_similarity=0.0875, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 5 | alt | Goya Coconut Milk | 0.7829 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.064, semantic_similarity=0.0889, category_compatibility=0.07, attribute_compatibility=0.13 | none |

## case-046 - powdered milk

- Expected acceptable product/family: dry milk (dry milk, powdered milk)
- Selected product: Bowl & Basket Milk
- Confidence: medium
- Failure category: under-aggressive conflict rule
- Resolution: powdered/dry milk now hard-rejects ordinary milk

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Bowl & Basket Milk | 0.7824 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0655, semantic_similarity=0.0869, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 2 | alt | Bowl & Basket Milk | 0.7824 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0655, semantic_similarity=0.0869, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 3 | alt | Bowl & Basket Milk | 0.7824 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0655, semantic_similarity=0.0869, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 4 | alt | Bowl & Basket Milk | 0.7824 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0655, semantic_similarity=0.0869, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 5 | alt | Bowl & Basket Dry Milk | 0.7805 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0649, semantic_similarity=0.0857, category_compatibility=0.07, attribute_compatibility=0.13 | none |

## case-049 - margarine

- Expected acceptable product/family: margarine (margarine, vegetable oil spread)
- Selected product: None
- Confidence: no_safe_match
- Failure category: scoring/weight issue
- Resolution: query-token evidence and family scoring allow margarine product above threshold

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | alt | Land O Lakes Margarine Sticks, Made with Vegetable Oil | 0.4141 | base_family=0.12, lexical_similarity=0.0348, semantic_similarity=0.0893, attribute_compatibility=0.13 | none |
| 2 | alt | Stella D'oro Margherite Cookies | 0.2512 | semantic_similarity=0.0877, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 3 | alt | Fudge M&M Cookies | 0.2484 | semantic_similarity=0.0849, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 4 | alt | Catalina Crunch Dark Chocolate, Keto Friendly Cereal | 0.2468 | semantic_similarity=0.0833, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 5 | alt | McVitie's Original Cookies | 0.2468 | semantic_similarity=0.0833, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |

## case-051 - frozen broccoli

- Expected acceptable product/family: frozen broccoli (frozen broccoli)
- Selected product: Birds Eye Broccoli Cuts
- Confidence: medium
- Failure category: missing product metadata
- Resolution: explicit frozen evidence and prepared-food rejection added; fixture fixed Steamfresh substring artifact

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Birds Eye Broccoli Cuts | 0.713 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0695, semantic_similarity=0.0836, attribute_compatibility=0.13 | none |
| 2 | alt | Andy Boy Broccoli Rabe | 0.7089 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0649, semantic_similarity=0.084, attribute_compatibility=0.13 | none |
| 3 | alt | Amy's Kitchen Broccoli Pot Pie | 0.7067 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.06, semantic_similarity=0.0867, attribute_compatibility=0.13 | none |
| 4 | alt | Bowl & Basket Broccoli Florets | 0.7028 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0562, semantic_similarity=0.0866, attribute_compatibility=0.13 | none |
| 5 | alt | Birds Eye Steamfresh Broccoli Florets, Frozen Vegetables | 0.7006 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0411, semantic_similarity=0.0994, attribute_compatibility=0.13 | none |

## case-057 - beef stock

- Expected acceptable product/family: beef stock (beef stock, beef broth)
- Selected product: Kitchen Basics Seafood Stock
- Confidence: medium
- Failure category: under-aggressive conflict rule
- Resolution: broth/stock species compatibility added

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Kitchen Basics Seafood Stock | 0.7722 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0491, semantic_similarity=0.0931, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 2 | alt | Kitchen Basics Vegetable Stock | 0.7684 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.047, semantic_similarity=0.0914, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 3 | alt | Kitchen Basics Beef Stock | 0.7256 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.06, semantic_similarity=0.1056, attribute_compatibility=0.13 | none |
| 4 | alt | Kitchen Basics Original Beef Stock | 0.7116 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.048, semantic_similarity=0.1036, attribute_compatibility=0.13 | none |
| 5 | alt | Kitchen Basics Unsalted Beef Stock | 0.7089 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.048, semantic_similarity=0.1009, attribute_compatibility=0.13 | none |

## case-059 - cream of chicken soup

- Expected acceptable product/family: cream of chicken soup (cream of chicken soup)
- Selected product: Campbell's Creamy Tomato Soup
- Confidence: medium
- Failure category: under-aggressive conflict rule
- Resolution: cream-soup subtype compatibility added

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Campbell's Creamy Tomato Soup | 0.7747 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0533, semantic_similarity=0.0914, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 2 | alt | Amy's Kitchen Chunky Vegetable Soup | 0.7708 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.052, semantic_similarity=0.0888, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 3 | alt | Progresso Traditional Canned Chickarina Soup | 0.7692 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0549, semantic_similarity=0.0843, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 4 | alt | Amy's Kitchen Golden Lentil Soup | 0.7665 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0505, semantic_similarity=0.0859, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 5 | alt | Streit's Matzo Ball & Soup Mix, Low Sodium | 0.765 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0529, semantic_similarity=0.0821, category_compatibility=0.07, attribute_compatibility=0.13 | none |

## case-060 - diced tomatoes

- Expected acceptable product/family: diced tomatoes (diced tomatoes)
- Selected product: Bowl & Basket Tomatoes
- Confidence: exact
- Failure category: parsing failure
- Resolution: raw text preserved for diced tomato identity; retrieval uses diced tomatoes signature

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Bowl & Basket Tomatoes | 0.9399 | exact_match=0.16, canonical_identity=0.27, base_family=0.12, lexical_similarity=0.12, semantic_similarity=0.0999, attribute_compatibility=0.13 | none |
| 2 | alt | Bowl & Basket Tomatoes | 0.9399 | exact_match=0.16, canonical_identity=0.27, base_family=0.12, lexical_similarity=0.12, semantic_similarity=0.0999, attribute_compatibility=0.13 | none |
| 3 | alt | Bowl & Basket Tomatoes | 0.9399 | exact_match=0.16, canonical_identity=0.27, base_family=0.12, lexical_similarity=0.12, semantic_similarity=0.0999, attribute_compatibility=0.13 | none |
| 4 | alt | Bowl & Basket Grape Tomatoes | 0.9375 | exact_match=0.16, canonical_identity=0.27, base_family=0.12, lexical_similarity=0.12, semantic_similarity=0.0975, attribute_compatibility=0.13 | none |
| 5 | alt | Bowl & Basket Tomatoes Diced | 0.9349 | exact_match=0.16, canonical_identity=0.27, base_family=0.12, lexical_similarity=0.12, semantic_similarity=0.0949, attribute_compatibility=0.13 | none |

## case-068 - no-salt-added tomato paste

- Expected acceptable product/family: no salt added tomato paste (no salt added tomato paste)
- Selected product: Bowl & Basket Tomato Paste
- Confidence: medium
- Failure category: under-aggressive conflict rule
- Resolution: no-salt-added requirement hard-rejects generic tomato paste

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Bowl & Basket Tomato Paste | 0.8027 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.076, semantic_similarity=0.1007, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 2 | alt | Cento Tomato Paste | 0.7956 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.072, semantic_similarity=0.1016, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 3 | alt | Hunt's Tomato Paste No Salt Added | 0.7849 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0563, semantic_similarity=0.1066, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 4 | alt | Amore Tomato Paste, Sun-Dried | 0.7787 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.06, semantic_similarity=0.0967, category_compatibility=0.07, attribute_compatibility=0.13 | none |
| 5 | alt | Tuttorosso Sweet Basil Tomato Paste | 0.5241 | base_family=0.12, lexical_similarity=0.0681, semantic_similarity=0.096, category_compatibility=0.07, attribute_compatibility=0.13 | none |

## case-069 - vegan butter

- Expected acceptable product/family: vegan (vegan)
- Selected product: None
- Confidence: substitution_only
- Failure category: retrieval failure
- Resolution: explicit vegan butter -> plant butter alias with justification; plant-butter family handling added

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | substitution | Land O Lakes Light Butter with Canola Oil | 0.3628 | canonical_identity=0.27, lexical_similarity=0.0408, semantic_similarity=0.0905, category_compatibility=0.07, attribute_compatibility=0.0715, strong_conflict_penalty=-0.22 | base_family=hard_reject (butter blend is not butter); butter_blend=strong_penalty (spread or blend is not plain butter); vegan=hard_reject (animal-derived product conflicts with vegan request) |
| 2 | substitution | Land O Lakes Light Butter with Canola Oil | 0.3628 | canonical_identity=0.27, lexical_similarity=0.0408, semantic_similarity=0.0905, category_compatibility=0.07, attribute_compatibility=0.0715, strong_conflict_penalty=-0.22 | base_family=hard_reject (butter blend is not butter); butter_blend=strong_penalty (spread or blend is not plain butter); vegan=hard_reject (animal-derived product conflicts with vegan request) |
| 3 | substitution | Land O Lakes Spread, Butter with Canola Oil | 0.3614 | canonical_identity=0.27, lexical_similarity=0.04, semantic_similarity=0.0899, category_compatibility=0.07, attribute_compatibility=0.0715, strong_conflict_penalty=-0.22 | base_family=hard_reject (butter blend is not butter); butter_blend=strong_penalty (spread or blend is not plain butter); vegan=hard_reject (animal-derived product conflicts with vegan request) |
| 4 | substitution | Spreadable Butter | 0.3599 | canonical_identity=0.27, lexical_similarity=0.0745, semantic_similarity=0.0943, category_compatibility=0.07, attribute_compatibility=0.0715, strong_conflict_penalty=-0.22 | base_family=hard_reject (butter blend is not butter); butter_blend=strong_penalty (spread or blend is not plain butter); vegan=hard_reject (animal-derived product conflicts with vegan request) |
| 5 | rejected | Wholesome Pantry Organic Butter | 0.7843 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0614, semantic_similarity=0.0929, category_compatibility=0.07, attribute_compatibility=0.13 | vegan=hard_reject (animal-derived product conflicts with vegan request) |

## case-071 - nut-free flour

- Expected acceptable product/family: flour (flour)
- Selected product: None
- Confidence: no_safe_match
- Failure category: missing canonical identity
- Resolution: nut-free query parsing and generic flour family handling added

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | alt | Bowl & Basket Flour | 0.3147 | lexical_similarity=0.0549, semantic_similarity=0.0963, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 2 | alt | Bowl & Basket Flour | 0.3147 | lexical_similarity=0.0549, semantic_similarity=0.0963, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 3 | alt | Bowl & Basket Flour | 0.3147 | lexical_similarity=0.0549, semantic_similarity=0.0963, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 4 | alt | Goya Enriched Wheat Flour | 0.3054 | lexical_similarity=0.0492, semantic_similarity=0.0927, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 5 | alt | Bob's Red Mill Chickpea Flour | 0.3031 | lexical_similarity=0.0514, semantic_similarity=0.0882, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |

## case-073 - Gold Medal flour

- Expected acceptable product/family: gold medal (gold medal, all purpose flour)
- Selected product: None
- Confidence: no_safe_match
- Failure category: missing canonical identity
- Resolution: generic flour family handling prevents brand flour from becoming its own product family

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | alt | Bowl & Basket Flour | 0.3219 | lexical_similarity=0.0714, semantic_similarity=0.0871, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 2 | alt | Bowl & Basket Flour | 0.3219 | lexical_similarity=0.0714, semantic_similarity=0.0871, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 3 | alt | Bowl & Basket Flour | 0.3219 | lexical_similarity=0.0714, semantic_similarity=0.0871, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 4 | alt | Goya Enriched Wheat Flour | 0.3216 | lexical_similarity=0.0702, semantic_similarity=0.0879, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |
| 5 | alt | Bob's Red Mill Chickpea Flour | 0.3112 | lexical_similarity=0.0655, semantic_similarity=0.0823, attribute_compatibility=0.1235 | base_family=unknown (family is incomplete) |

## case-095 - vanilla yogurt

- Expected acceptable product/family: vanilla yogurt (vanilla yogurt)
- Selected product: Chobani Vanilla Greek Nonfat Yogurt
- Confidence: medium
- Failure category: ambiguous evaluation case
- Resolution: yogurt flavor detection added; fixture accepts vanilla Greek wording

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | Chobani Vanilla Greek Nonfat Yogurt | 0.7292 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0729, semantic_similarity=0.0963, attribute_compatibility=0.13 | none |
| 2 | alt | Sun-Maid Vanilla Yogurt Covered Raisins | 0.7251 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.068, semantic_similarity=0.0971, attribute_compatibility=0.13 | none |
| 3 | alt | Chobani Vanilla Blended Non-Fat Greek Yogurt | 0.7214 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0665, semantic_similarity=0.095, attribute_compatibility=0.13 | none |
| 4 | alt | Ratio Protein Vanilla Yogurt Cultured Dairy Snack | 0.7187 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0583, semantic_similarity=0.1005, attribute_compatibility=0.13 | none |
| 5 | alt | Oikos Triple Zero Vanilla Greek Yogurt | 0.7168 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0692, semantic_similarity=0.0876, attribute_compatibility=0.13 | none |

## case-096 - plain yogurt

- Expected acceptable product/family: plain yogurt (plain yogurt)
- Selected product: La Yogurt Yogurt, Lowfat, Guava, Blended
- Confidence: medium
- Failure category: scoring/weight issue
- Resolution: plain yogurt flavor detection and unknown-flavor penalty added; fixture accepts plain Greek wording

| Rank | Bucket | Product | Score | Score Breakdown | Compatibility Decisions |
|---:|---|---|---:|---|---|
| 1 | selected | La Yogurt Yogurt, Lowfat, Guava, Blended | 0.7225 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0686, semantic_similarity=0.0939, attribute_compatibility=0.13 | none |
| 2 | alt | La Yogurt Yogurt, Lowfat, Mango, Blended | 0.7215 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0686, semantic_similarity=0.093, attribute_compatibility=0.13 | none |
| 3 | alt | La Yogurt Yogurt, Lowfat, Papaya, Blended | 0.7196 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0674, semantic_similarity=0.0922, attribute_compatibility=0.13 | none |
| 4 | alt | Bowl & Basket Yogurt | 0.7192 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0702, semantic_similarity=0.0889, attribute_compatibility=0.13 | none |
| 5 | alt | Bowl & Basket Yogurt | 0.7192 | canonical_identity=0.27, base_family=0.12, lexical_similarity=0.0702, semantic_similarity=0.0889, attribute_compatibility=0.13 | none |
