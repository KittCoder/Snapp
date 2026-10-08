#!/usr/bin/env python3
"""Export actual outputs for independent human review; never infer review labels."""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, math, random, re, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Model'))
LABELS = {'CORRECT', 'ACCEPTABLE_SUBSTITUTE', 'WRONG', 'SHOULD_HAVE_MATCHED', 'AMBIGUOUS'}
CAUSES = {'wrong family', 'wrong subfamily', 'wrong species', 'wrong cut', 'wrong state/form', 'wrong dietary identity', 'wrong flavor', 'wrong fat/salt attribute', 'prepared-food leakage', 'brand noise', 'alias/taxonomy issue', 'embedding/lexical issue', 'unknown'}
REVIEW_FIELDS = ['review_label', 'reviewer', 'review_notes', 'failure_cause', 'wrong_family', 'prepared_food_false_positive', 'structurally_correct']
CATEGORIES = ['cheese', 'meat/cuts', 'broth/stock', 'milk', 'yogurt', 'tomato products', 'fresh/frozen/canned/dried', 'prepared-food negatives']
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def category(row):
    identity = row['ontology']; family = identity.get('family') or ''; sub = identity.get('subfamily', '') or ''
    tags = []
    for name, words in [('cheese', ['cheese']), ('meat/cuts', ['meat', 'poultry']), ('broth/stock', ['broth', 'stock']), ('milk', ['milk']), ('yogurt', ['yogurt']), ('tomato products', ['tomato'])]:
        if any(w in family or w in sub for w in words): tags.append(name)
    if identity.get('state') in ('fresh', 'frozen', 'canned', 'dried') or identity.get('form') in ('fresh', 'frozen', 'canned', 'dried'): tags.append(CATEGORIES[6])
    # Query or inventory candidate is prepared; this is a sampling stratum, not a gold label.
    candidates = row.get('rejected_candidates', []) + row.get('compatible_alternatives', [])
    if identity.get('family') in ('prepared','nonfood') or any(c.get('ontology', {}).get('family') in ('prepared','nonfood') for c in candidates): tags.append(CATEGORIES[7])
    return tags

def sample_population(rows, seed):
    rng = random.Random(seed); used = set(); selected = []; counts = {}
    def take(name, pool, requested):
        available = [r for r in pool if r['case_id'] not in used]
        picked = rng.sample(available, min(requested, len(available)))
        for r in picked:
            used.add(r['case_id']); selected.append({**r, 'sample_group': name})
        counts[name] = {'requested': requested, 'available_before_sampling': len(available), 'sampled': len(picked)}
    # Hard strata first avoids exhausting small categories in the broad samples.
    for i, name in enumerate(CATEGORIES):
        take('hard: ' + name, [r for r in rows if name in category(r)], 38 if i < 4 else 37)
    take('Exact/High', [r for r in rows if r['selected_match'] and r['confidence'].lower() in ('exact', 'high')], 400)
    take('Medium', [r for r in rows if r['selected_match'] and r['confidence'].lower() == 'medium'], 250)
    take('Rejected', [r for r in rows if not r['selected_match']], 250)
    return selected, counts

def export(args):
    from product_compatibility import ProductMatchService
    source = ROOT / 'Model/all_recipes.json'
    queries = {}
    for recipe in json.loads(source.read_text())['recipes']:
        for ingredient in recipe.get('ingredients', []):
            text = ingredient.get('raw') or ingredient.get('name') if isinstance(ingredient, dict) else ingredient
            if isinstance(text, str) and text.strip(): queries.setdefault(text.strip(), []).append(recipe['id'])
    service = ProductMatchService(); texts = sorted(queries); rows = []; started = time.perf_counter()
    for offset in range(0, len(texts), 200):
        batch = texts[offset:offset + 200]
        results = service.match_recipe_ingredients(batch, limit=5, use_semantic=True)
        if len(results) != len(batch): raise ValueError('Matcher output alignment changed')
        for text, result in zip(batch, results):
            row = result.to_dict(); row.update(case_id=hashlib.sha256(text.encode()).hexdigest()[:20], ingredient_query=text, source_recipe_ids=queries[text])
            rows.append(row)
        print(f'Matched {len(rows)}/{len(texts)}', flush=True)
    batch_seconds = time.perf_counter() - started
    rng = random.Random(args.seed); latencies = []
    for text in rng.sample(texts, min(100, len(texts))):
        service.cache._items.clear(); start = time.perf_counter()
        service.match_recipe_ingredient(text, use_semantic=True)
        latencies.append((time.perf_counter() - start) * 1000)
    if args.exclude:
        if args.seed == json.loads(args.exclude.read_text())['seed']: raise ValueError('Holdout requires a NEW seed')
        excluded = {r['case_id'] for r in json.loads(args.exclude.read_text())['cases']}
        rows_for_sample = [r for r in rows if r['case_id'] not in excluded]
    else: rows_for_sample = rows
    cases, counts = sample_population(rows_for_sample, args.seed)
    add_diagnostic_alternatives(cases, service)
    out = args.output; out.mkdir(parents=True, exist_ok=True)
    files = ['Model/all_recipes.json', 'Model/morton_williams_product_features.json', 'Model/product_ontology.py', 'Model/food_identity_rules.py', 'Model/product_compatibility.py', 'Model/product_retrieval.py']
    manifest = {'seed': args.seed, 'sampling_unit': 'distinct actual raw ingredient query; hard strata first, without replacement', 'source_hashes': {p: digest(ROOT/p) for p in files}, 'population_count': len(rows), 'confidence_population': dict(collections.Counter(r['confidence'] for r in rows)), 'no_match_rate': sum(not r['selected_match'] for r in rows)/len(rows), 'sample_counts': counts, 'sample_total': len(cases), 'latency': {'mode': 'warm uncached single query, semantic enabled, 100 random population queries', 'median_ms': statistics.median(latencies), 'p95_ms': sorted(latencies)[math.ceil(.95*len(latencies))-1], 'batch_seconds': batch_seconds}, 'cases': cases}
    (out/'population.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    manifest['population_sha256'] = digest(out/'population.jsonl')
    (out/'sample.json').write_text(json.dumps(manifest, indent=2) + '\n')
    columns = ['case_id', 'sample_group', 'ingredient_query', 'selected_product', 'match_type', 'confidence', 'food_family', 'subfamily', 'key_attributes', 'selected_product_ontology', 'top_3_alternatives', 'score_breakdown', 'current_matcher_decision', 'reason_codes'] + REVIEW_FIELDS
    with (out/'review.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader()
        for r in cases:
            selected = r['selected_match'] or {}; ontology = r['ontology']
            alternatives = top_alternatives(r)
            writer.writerow({'case_id': r['case_id'], 'sample_group': r['sample_group'], 'ingredient_query': r['ingredient_query'], 'selected_product': selected.get('product_name', ''), 'match_type': r['match_type'], 'confidence': r['confidence'], 'food_family': ontology.get('family'), 'subfamily': ontology.get('subfamily'), 'key_attributes': json.dumps(ontology), 'selected_product_ontology': json.dumps(selected.get('ontology', {})), 'top_3_alternatives': json.dumps(alternatives), 'score_breakdown': json.dumps(selected.get('score_breakdown', {})), 'current_matcher_decision': 'accepted' if selected else 'rejected', 'reason_codes': json.dumps(r['reason_codes']), **{key: '' for key in REVIEW_FIELDS}})
    # Preserve immutable columns to catch accidental editing during review.
    manifest['review_csv_sha256'] = digest(out/'review.csv')
    with (out/'review.csv').open(newline='') as handle:
        manifest['immutable_review_hashes'] = {r['case_id']: immutable_hash(r) for r in csv.DictReader(handle)}
    (out/'sample.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out/'README.md').write_text('''# Independent human QA\n\nOpen review.csv in a spreadsheet. Every review_label is intentionally blank. No proxy labels are supplied. sample.json contains complete actual outputs; population.jsonl contains the entire query population. Alternatives marked diagnostic_only_ungated_not_selected come from a separate lexical inventory lookup and may violate structural gates; they are review aids, never selected matches. Empty alternatives mean none were returned; do not infer that no suitable inventory item exists. Consult Model/morton_williams_product_features.json when adjudicating rejected queries.\n\nUse only CORRECT, ACCEPTABLE_SUBSTITUTE, WRONG, SHOULD_HAVE_MATCHED, AMBIGUOUS. For accepted cases use WRONG for critical errors; for rejected cases use SHOULD_HAVE_MATCHED for false negatives. AMBIGUOUS stays in the precision denominator and never counts as correct. Fill reviewer for every label. For every accepted WRONG fill failure_cause and review_notes. Allowed causes: wrong family, wrong subfamily, wrong species, wrong cut, wrong state/form, wrong dietary identity, wrong flavor, wrong fat/salt attribute, prepared-food leakage, brand noise, alias/taxonomy issue, embedding/lexical issue, unknown.\n\nFor every accepted case fill wrong_family and prepared_food_false_positive with yes/no. For cheese and meat/cuts accepted cases also fill structurally_correct with yes/no. Keep all non-review columns unchanged. Metrics remain pending until actual human labels exist. Confidence is a matcher bucket, not calibrated probability. Inventory is a July 2026 snapshot.\n\nRun `.venv/bin/python scripts/human_qa_ingredient_matcher.py score --output data/matcher_validation`. After a human-observed cleanup, draw a fresh seed with export --seed NEW_INTEGER --exclude data/matcher_validation/sample.json --output data/matcher_validation_holdout. Do not evaluate fixes on the original sample alone.\n''')
    score(args)

def top_alternatives(row):
    candidates = []; seen = {row['selected_match']['product_id']} if row['selected_match'] else set()
    for key, status in [('compatible_alternatives', 'compatible'), ('substitution_candidates', 'substitute'), ('rejected_candidates', 'rejected'), ('diagnostic_alternatives', 'diagnostic_only_ungated_not_selected')]:
        for candidate in row.get(key, []):
            if candidate['product_id'] not in seen:
                candidates.append({**candidate, 'candidate_status': status}); seen.add(candidate['product_id'])
    return candidates[:3]

def add_diagnostic_alternatives(cases, service):
    from product_ontology import describe, compatibility
    for row in cases:
        if len(top_alternatives(row)) >= 3: continue
        query = describe(row['ingredient_query']); diagnostics = []
        retrieval = service.retriever.retrieve_product_candidates(row['ingredient_query'], limit=8, use_semantic=False)
        for candidate in retrieval.candidates:
            feature = service.feature_by_id[candidate.product_id]
            identity = describe(candidate.original_product_name, feature=feature, product=True)
            decision = compatibility(query, identity)
            diagnostics.append({'product_id': candidate.product_id, 'product_name': candidate.original_product_name, 'ontology': identity.to_dict(), 'lexical_similarity': candidate.lexical_similarity, 'structural_decision': decision.match_type, 'note': 'Ungated lexical diagnostic only; never changes current matcher decision'})
        row['diagnostic_alternatives'] = diagnostics

def immutable_hash(row):
    return hashlib.sha256(json.dumps({k:v for k,v in row.items() if k not in REVIEW_FIELDS}, sort_keys=True).encode()).hexdigest()

def metrics(cases, reviews):
    def rate(n, d): return n/d if d else None
    reviewed = [r for r in reviews if r['review_label']]
    accepted = [r for r in reviewed if cases[r['case_id']]['selected_match']]
    rejected = [r for r in reviewed if not cases[r['case_id']]['selected_match']]
    precision = lambda xs: rate(sum(r['review_label'] in ('CORRECT', 'ACCEPTABLE_SUBSTITUTE') for r in xs), len(xs))
    result = {'reviewed': len(reviewed), 'total': len(cases), 'Exact/High_manual_precision': precision([r for r in accepted if cases[r['case_id']]['confidence'].lower() in ('exact', 'high')]), 'Medium_manual_precision': precision([r for r in accepted if cases[r['case_id']]['confidence'].lower() == 'medium']), 'false_positive_rate': rate(sum(r['review_label']=='WRONG' for r in accepted), len(accepted)), 'rejected_SHOULD_HAVE_MATCHED_rate': rate(sum(r['review_label']=='SHOULD_HAVE_MATCHED' for r in rejected), len(rejected)), 'false_negative_rate': None, 'false_negative_rate_note': 'Population recall/FNR cannot be estimated from rejection review alone; rejection miss rate reported separately.'}
    for flag, key in [('wrong_family', 'wrong_family_count'), ('prepared_food_false_positive', 'prepared_food_false_positives')]:
        result[key] = sum(r[flag]=='yes' for r in accepted) if accepted and all(r[flag] in ('yes','no') for r in accepted) else None
    for tag, key in [('cheese', 'cheese_accuracy'), ('meat/cuts', 'meat_cut_accuracy')]:
        subset = [r for r in accepted if tag in category(cases[r['case_id']])]
        result[key] = rate(sum(r['structurally_correct']=='yes' and r['review_label'] in ('CORRECT','ACCEPTABLE_SUBSTITUTE') for r in subset), len(subset)) if all(r['structurally_correct'] in ('yes','no') for r in subset) else None
    result['material_errors'] = [r for r in reviewed if r['review_label'] in ('WRONG','SHOULD_HAVE_MATCHED')]
    result['freeze_recommendation'] = 'DO_NOT_FREEZE_MATCHER'
    return result

def score(args):
    out = args.output; manifest = json.loads((out/'sample.json').read_text()); cases = {r['case_id']: r for r in manifest['cases']}
    with (out/'review.csv').open(newline='') as handle: reviews = list(csv.DictReader(handle))
    if len(reviews)!=len(cases) or {r['case_id'] for r in reviews}!=set(cases): raise ValueError('Review cases missing, duplicated or added')
    for r in reviews:
        label = r['review_label']; c = cases[r['case_id']]
        if manifest.get('immutable_review_hashes', {}).get(r['case_id']) != immutable_hash(r): raise ValueError('Immutable review columns edited')
        if r['ingredient_query']!=c['ingredient_query'] or r['current_matcher_decision']!=('accepted' if c['selected_match'] else 'rejected'): raise ValueError('Immutable query/decision edited')
        if label and label not in LABELS: raise ValueError('Invalid review label')
        if label and not r['reviewer'].strip(): raise ValueError('Human reviewer required')
        if c['selected_match'] and label=='SHOULD_HAVE_MATCHED': raise ValueError('False negative label on accepted case')
        if not c['selected_match'] and label in ('WRONG','ACCEPTABLE_SUBSTITUTE'): raise ValueError('Accepted-match label on rejected case')
        if label=='WRONG' and (r['failure_cause'] not in CAUSES or not r['review_notes'].strip()): raise ValueError('Every wrong acceptance requires cause and investigation notes')
        for flag in ('wrong_family','prepared_food_false_positive','structurally_correct'):
            if r[flag] not in ('','yes','no'): raise ValueError('Flags must be blank, yes or no')
    result = metrics(cases, reviews)
    result['source_fingerprints_current'] = all((ROOT/p).exists() and digest(ROOT/p)==h for p,h in manifest['source_hashes'].items())
    sufficient = all(v['sampled']==v['requested'] for v in manifest['sample_counts'].values())
    if sufficient and result['source_fingerprints_current'] and result['reviewed']==result['total'] and (result['Exact/High_manual_precision'] or 0)>=.99 and (result['Medium_manual_precision'] or 0)>=.95 and result['false_positive_rate'] is not None and result['false_positive_rate']<=.01 and result['wrong_family_count']==0 and result['prepared_food_false_positives']==0 and (result['cheese_accuracy'] or 0)>=.99 and (result['meat_cut_accuracy'] or 0)>=.99 and not any(r['review_label']=='WRONG' for r in reviews):
        result['freeze_recommendation']='FREEZE_MATCHER'
    test_log = out/'full_tests.log'
    matches = re.findall(r'Ran (\d+) tests', test_log.read_text()) if test_log.exists() else []
    result['full_test_count'] = int(matches[-1]) if matches else None
    result['full_tests_passed'] = bool(matches and test_log.read_text().rstrip().endswith('OK'))
    if not result['full_tests_passed']: result['freeze_recommendation'] = 'DO_NOT_FREEZE_MATCHER'
    result.update(no_match_rate=manifest['no_match_rate'], latency=manifest['latency'], sample_counts=manifest['sample_counts'])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'report.md').write_text('# Independent human-QA validation\n\n**'+result['freeze_recommendation']+'**\n\nManual review: '+str(result['reviewed'])+'/'+str(result['total'])+'. Null metrics are pending, never zero errors. No human-observed cleanup has been performed by this exporter.\n\n```json\n'+json.dumps(result, indent=2)+'\n```\n')
    print(json.dumps({k:v for k,v in result.items() if k!='material_errors'}, indent=2), flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command', choices=['export','score']); parser.add_argument('--seed', type=int, default=20261007); parser.add_argument('--output', type=Path, default=ROOT/'data/matcher_validation'); parser.add_argument('--exclude', type=Path)
    args=parser.parse_args(); (export if args.command=='export' else score)(args)
