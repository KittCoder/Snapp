#!/usr/bin/env python3
"""Assemble an honest local review from frozen evaluation/harvest sidecars."""
import collections,datetime,hashlib,json,random,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility,IdentityCatalog,ONTOLOGY_VERSION

def read(path):return json.loads((ROOT/path).read_text())
def lines(path):return [json.loads(x) for x in (ROOT/path).read_text().splitlines() if x.strip()]
def compact(report):return {k:v for k,v in report.items() if k not in ('rows','pair_rows','qa_samples')}
def percent(value):return 'n/a' if value is None else f'{100*value:.2f}%'
def cell(text):return str(text).replace('|','/').replace('\n',' ')

CORRECTIONS={
 0:'Specific vegetable oil is not canola oil.',8:'Margarine is distinct from dairy butter.',15:'Round cut is not an unspecified beef steak.',25:'Reduced-fat cheddar requires fat evidence.',26:'Monterey Jack is not pepper/Colby Jack; reduced fat must be verified.',27:'Low-sodium pasta sauce requires sodium evidence.',30:'Summer squash is not butternut squash.',38:'White pepper cannot be eggs.',44:'Lemon juice is not lemon tea.',45:'Apples cannot be apple pie.',47:'Powdered bouillon is distinct from liquid broth.',52:'Plain cooked chicken cannot be spicy prepared cutlets.',71:'Nonfat milk requires verified fat level.',78:'Unsalted butter requires verified salt status.',85:'Lime juice is not peach juice drink.',87:'Yellow squash is distinct from butternut squash.',92:'Dry milk is distinct from liquid milk.',94:'Skim milk requires verified fat level.',97:'Zucchini cannot be pancakes.',100:'White wine cannot be eggs.',125:'Reduced-fat feta requires fat evidence.',135:'Corn oil is distinct from canola oil.',136:'Yellow onion is distinct from white onion.',144:'Required low sodium cannot be inferred from silence.',146:'Green cabbage is not red cabbage.',161:'Ginger is not ginger dressing.',172:'Peanut butter cannot be a protein bar.',173:'Kernel corn is distinct from cream-style corn.',175:'Turkey liver cannot be lemonade tea.',184:'93% lean ground beef is not 85% lean ground beef.',192:'Plain gelatin is distinct from flavored gelatin mix.',196:'Fresh onion cannot be granulated dried onion.',222:'Required low-sodium diced tomatoes cannot be inferred.',230:'Pinto beans and low sodium must be verified.',254:'Plain pork tenderloin is not rotisserie-flavored tenderloin.',260:'Jalapeno is not cayenne seasoning.',261:'90% lean ground beef is not 85% lean.',263:'Whole eggs are distinct from egg whites.',285:'Low-fat cream cheese requires verified fat evidence.',311:'Fresh spinach cannot be selected without state evidence.',313:'Apple cannot be apple pie.'}

def assistant_label(row):
 """Conservative name-only QA: independent rules, not the production gate."""
 product=row.get('selected_product')
 if not product:return row['classification'],'Frozen independent proxy classification; inventory availability still needs human verification.'
 q=row['ingredient'].lower();p=product['product_name'].lower()
 wrong=[]
 if any(x in q for x in ['zest','peel','rind','outer scrapings']) and any(x in p for x in ['juice','curd','pie']):wrong.append('Peel/zest requirement cannot be fulfilled by juice/dessert.')
 if 'garlic' in q and 'sauce' not in q and 'sauce' in p:wrong.append('Garlic ingredient is not garlic sauce.')
 if 'butter' in q and 'bread' not in q and 'bread' in p:wrong.append('Butter ingredient is not bread.')
 if 'fat-free mozzarella' in q or 'fat free mozzarella' in q:
  if 'part-skim' in p or 'part skim' in p:wrong.append('Part-skim is not fat-free.')
 if 'green onion' in q and 'green onion' not in p and 'scallion' not in p:wrong.append('Scallions are not bulb onions.')
 if 'egg' in q and not any(x in q for x in ['white','yolk']) and 'egg whites' in p:wrong.append('Whole eggs are not egg whites.')
 if wrong:return 'WRONG_PRODUCT',' '.join(wrong)
 if any(x in q for x in ['fresh or frozen','salt cod','mixed with','with green chiles','with chiles','whole kernel corn mixed','or wild onion','process swiss','sharp cheddar','extra-sharp','milk cream','fruit yogurt','browned flour','instant minced','instant garlic']):return 'AMBIGUOUS','Material variant/preparation or compound ingredient needs independent review.'
 if ('spinach' in q and 'popeye' in p) or ('basil' in q and 'dorot' in p):return 'AMBIGUOUS','Recipe state is unspecified; listing state needs independent verification.'
 if 'lean' in q and '%' not in q:return 'AMBIGUOUS','Unquantified lean requirement is not verified.'
 if row['classification']=='WRONG_PRODUCT':return 'AMBIGUOUS','Proxy disagreement needs independent adjudication; do not assume either matcher or proxy is correct.'
 return 'CORRECT','Assistant name-only review: identity appears compatible; NOT independent human gold.'

def main():
 before=read('data/matcher_audit/before_benchmark.json');after=read('data/matcher_audit/after_benchmark.json')
 payload=read('Model/morton_williams_product_features.json');features=payload['features'];catalog=IdentityCatalog(features)
 texts=read('data/matcher_audit/harvest_ingredients.json');bh=lines('data/matcher_audit/before_harvest.jsonl');ah=lines('data/matcher_audit/after_harvest.jsonl')
 corrections=[]
 for index,note in CORRECTIONS.items():
  old=bh[index]['selected_match'];new=ah[index]['selected_match']
  if not old or new and old['product_id']==new['product_id']:continue
  corrections.append({'ingredient':texts[index],'before_selected':old,'after_selected':new,'after_match_type':ah[index]['match_type'],'after_confidence':ah[index]['confidence'],'ontology':ah[index]['ontology'],'review_classification':'CORRECTED_WRONG_OR_UNVERIFIED_SELECTION' if new else 'SAFE_ABSTENTION','explanation':note,'provenance':'Assistant-curated representative failure; not a random QA estimate. Original input preserved separately because baseline cache leaked raw text.'})
 qa={}
 for name,bucket in after['qa_samples'].items():
  xs=[]
  for row in bucket['rows']:
   label,note=assistant_label(row)
   xs.append({**row,'proxy_classification':row['classification'],'assistant_review_classification':label,'assistant_review_note':note,'human_review_status':'PENDING'})
  counts=dict(collections.Counter(r['assistant_review_classification'] for r in xs))
  qa[name]={**{k:v for k,v in bucket.items() if k!='rows'},'assistant_name_review_counts':counts,'rows':xs}
 rng=random.Random(20261006)
 negatives=[r for r in after['pair_rows'] if r['kind']=='prepared_negative']
 prep_sample=rng.sample(negatives,min(200,len(negatives)))
 qa['prepared_negative_pairs']={'requested':200,'sampled':len(prep_sample),'classification_provenance':'Frozen name-rule proxy pair labels, NOT human review; includes known proxy errors such as Cracker Barrel cheese.','human_review_status':'PENDING','rows':prep_sample}
 # Baseline harvest strata, including Low, remain independently visible.
 baseline_strata={}
 for bucket in ('exact','high','medium','low','no_safe_match'):
  pool=[{'ingredient':q,'result':r} for q,r in zip(texts,bh) if r['confidence']==bucket]
  baseline_strata[bucket]={'available':len(pool),'sampled':min(100,len(pool)),'rows':rng.sample(pool,min(100,len(pool)))}
 fn_counts=collections.Counter();fn_examples=[]
 for row in after['rows']:
  if row['classification']!='SHOULD_HAVE_MATCHED':continue
  query=describe(row['ingredient']);reasons=set()
  for pid in row['expected_ids']:
   product=catalog.identities.get(pid)
   if product:reasons.update(compatibility(query,product).reasons)
  if 'unknown_family' in reasons:group='taxonomy_missing'
  elif 'ambiguous_identity_or_variant' in reasons or 'ambiguous_required_identity' in reasons:group='ambiguous_identity'
  elif any(x.startswith('unverified_') for x in reasons):group='inventory_metadata_issue'
  elif any('form' in x or 'state' in x for x in reasons):group='form_or_state_mismatch'
  elif any('subfamily' in x or 'style' in x or 'cut' in x for x in reasons):group='strict_identity_policy_or_proxy_error'
  else:group='attribute_conflict_or_proxy_error'
  fn_counts[group]+=1
  fn_examples.append({'ingredient':row['ingredient'],'expected_ids':row['expected_ids'],'analysis_group':group,'identity_reasons':sorted(reasons),'label_provenance':'Proxy false negative; human availability adjudication pending.'})
 log=(ROOT/'data/matcher_audit/final_full_tests.log').read_text();test_count=re.search(r'Ran (\d+) tests',log)
 failures=re.findall(r'^(?:FAIL|ERROR): (.+)$',log,re.M)
 diff_check=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
 review={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'recommendation':'DO_NOT_FREEZE_MATCHER',
 'scope':'Standalone ingredient/product matcher; existing quantity/cost/basket behavior retained. Local only.',
 'inventory':{'source_file':'Model/morton_williams_product_features.json','snapshot_metadata':payload['metadata'],'eligible':len(catalog.identities),'total':len(features),'sha256':before['inventory_sha256'],'live_stock_verified':False,'ontology_coverage':dict(collections.Counter(x.family or 'unknown' for x in catalog.identities.values()))},
 'benchmark':{'queries':len(after['rows']),'pairs':len(after['pair_rows']),'label_provenance':after['label_provenance'],'label_limitations':'Availability means known rule-labelled acceptable SKU, not exhaustive verified store availability. Proxy errors remain frozen for fair comparison. Unknown/ambiguous accepted products excluded from precision. Pair results test isolated compatibility, not production top-1 retrieval.'},
 'before':compact(before),'after':compact(after),'random_qa':qa,'baseline_harvest_strata':baseline_strata,'known_remaining_qa_errors':[r for bucket in qa.values() for r in bucket.get('rows',[]) if r.get('assistant_review_classification')=='WRONG_PRODUCT'],
 'false_negative_analysis':{'counts':dict(fn_counts),'rows':fn_examples,'remaining_work':'Independent human adjudication and better explicit inventory state/form/fat metadata. Do not loosen guards to chase proxy labels.'},
 'representative_corrected_failures':corrections,'calibration':'Rule/rank scores are not probabilities. Exact/High/Medium labels are proxy-evaluated and NOT independently human calibrated. Medium and Low pools are empty in this benchmark; no fabricated QA observations.',
 'tests':{'full_suite_count':int(test_count.group(1)) if test_count else None,'full_suite_failures':failures,'isolated_sale_test_log':'data/matcher_audit/isolated_sale_tests.log','regression_cases':len((ROOT/'Model/evaluation/ingredient_matcher_regressions.jsonl').read_text().splitlines()),'diff_check':'PASS' if diff_check.returncode==0 else 'FAIL','diff_check_output':diff_check.stdout+diff_check.stderr},
 'artifacts':{'before':'data/matcher_audit/before_benchmark.json','after':'data/matcher_audit/after_benchmark.json','before_harvest':'data/matcher_audit/before_harvest.jsonl','after_harvest':'data/matcher_audit/after_harvest.jsonl','benchmark':'Model/evaluation/ingredient_inventory_benchmark.json','regressions':'Model/evaluation/ingredient_matcher_regressions.jsonl'},
 'freeze_blockers':['Exact/High proxy precision below required 99%.','Independent human QA has not been completed.','No Medium examples available to validate the 95% target.','Cheese/meat pair overall accuracy/recall remain below target despite strong rejection precision.','Rule-labelled absence and unknown inventory attributes are not verified true no-match gold.','Prepared-food and compound-name extraction remain incomplete; no claim of zero family errors.']}
 (ROOT/'ingredient_matcher_review.json').write_text(json.dumps(review,indent=2,allow_nan=False)+'\n')
 out=['# Ingredient/product matcher review','', '**DO_NOT_FREEZE_MATCHER**','',
 'The new matcher materially improves measured selection precision, while stricter attribute gates reduce pair-level recall and increase rejected known-positive cases. The evidence does not meet the requested freeze criteria. Independent human QA is still pending; all reported benchmark metrics below use conservative frozen name-rule proxy labels.',
 '', '## Inventory and benchmark','',
 f"Inventory: {len(features):,} records, {len(catalog.identities):,} eligible, from the July 21, 2026 local snapshot. No live-stock refresh was performed. SHA-256: `{before['inventory_sha256']}`.",
 f"Frozen before tuning: {len(after['rows']):,} real recipe ingredient queries and {len(after['pair_rows']):,} real ingredient/inventory pairs, including 1,667 cheese and 1,021 meat pairs. The separate fixed-seed harvest contains 2,000 real ingredient lines. Permanent hand-specified regressions: {review['tests']['regression_cases']:,} pairs.",
 'Proxy labels come from an independent conservative name-rule classifier, not matcher predictions. They cover only confidently labelled products. Known label problems include Cracker Barrel counted as crackers, frozen corn losing its state when its title also contains “Steamfresh”, missing hyphenated salt/fat aliases, and compound ingredient headings. The original labels were kept unchanged. “No valid inventory match” therefore means no known acceptable labelled SKU, not proven absence across the entire catalog. Precision excludes ambiguous/unlabelled accepted SKUs; recall is also conditioned on labelled examples.',
 '', '## Production audit','',
 '`recipe_ingredient_adapter.canonical_recipe_ingredients` constructs matching text and quantity inputs. `ingredient_normalization.parse_ingredient` parses quantities, units, aliases and descriptors; `extract_product_features` supplies eligible normalized inventory. `ProductCandidateRetriever` merges canonical/exact aliases, token/fuzzy overlap and optional local BGE vectors. `ProductMatchService` reranks and caches. `BasketBuilder` then converts quantities, evaluates packages/prices and optimizes within supplied compatible alternatives. `model.match_recipe_ingredients_to_morton_williams` consumes that basket.',
 'Before: v1.12 retrieved broadly before most compatibility checks; incomplete identities could still earn selection scores, exact/canonical flags could overstate identity, forced overrides could bypass guards, and cache identity omitted material attributes. Confidence used rank thresholds (Exact .90, High .78, Medium .62, Low .45) with a .45 selection floor. Baseline batch caching also leaked another input’s raw/quantity context; the review aligns by the original input list, not the leaked output text.',
 'After: original ingredient text → deterministic ontology → family/subfamily/species/cut/attribute gate across eligible inventory → gated lexical and vector retrieval → identical mandatory gate during reranking → interpretable score → exact/equivalent/substitute/none metadata → unchanged quantity/cost optimization. Production is `ProductMatchService`; legacy low-level compatibility helpers remain for backward compatibility and comparison tests, and are not its selection policy.',
 '', '## Policies and implementation','',
 '- Food identities include family, subtype, species, cut, form, state, fat, salt, sweetness, flavor, bone, skin, raw/cooked/cured/prepared, dietary identity/requirements, variety and display brand. Unknown evidence stays null; explicit metadata can supply evidence, contradictory metadata abstains.',
 '- Cheese taxonomy distinguishes 25+ types, dairy versus plant cheese, part-skim versus fat-free, moisture/style and material forms. Meat distinguishes species and cuts, raw versus cured/prepared, bone/skin and explicit lean percentages. Raw meat without a requested cut abstains.',
 '- Broth/stock preserve species and sodium; liquid broth differs from bouillon. Tomato paste/sauce/puree/crushed/diced/whole/fresh remain separate. Milk percentages/types, yogurt Greek/regular/skyr, flavor and fat constraints remain structural.',
 '- General aliases include green onion/scallion, hamburger meat/ground beef, chuck roast/beef chuck roast, fillet/tenderloin, cornflour/cornstarch, corn masa flour, dry/powdered milk, broth/stock, rocket/arugula, and common hyphen spellings.',
 '- Whole cheese/produce can be cut at home where safe and is marked equivalent. Generic dairy milk permits ordinary percentages; explicit percentages remain required. Generic low-fat dairy milk permits verified 1%/2%. Generic cream permits heavy/light cream. Whole eggs can supply whites/yolks; egg whites cannot replace whole eggs.',
 '- Default mode is strict. Explicit substitute mode permits only the documented small same-family policy (parmesan/pecorino, chicken breast/thigh, regular→Greek yogurt); substitutions are separate and the existing basket does not auto-buy `substitution_only` results.',
 '- Prepared foods, nonfood/pet products and unverified required attributes reject. Forced/approved/substitution overrides cannot bypass ontology gates. Ready ingredients such as pancake mix, soup, breadcrumbs, pita and hummus have explicit identities and retain prepared-food boundary checks.',
 '- Verified structure contributes .88; lexical contributes up to .07 and finite cosine up to .05. Components expose family/canonical/subtype/form/state/dietary/cut/required attributes, prepared rejection and optional variant preference. Brand and quantity/price contribute zero. Substitution scores cap at .70. Nonfinite vectors supply no positive evidence.',
 '- Exact requires an exact lexical/canonical flag, exact identity and score ≥ .94; High ≥ .90; remaining verified selections are Medium. These are provisional rank labels, not calibrated probabilities. Ties among the same verified identity need no product-brand margin; ambiguous identity/cut/state abstains instead. No Low auto-selection is emitted.',
 '- Cache keys include full required identity, normalized signature, mode, scoring configuration, matcher/ontology/index/override versions and requested limits; quantity context is restored per input. Gate-specific batch retrieval keeps equal embedding texts with different identities distinct.',
 '', '## Before / after proxy metrics','', '| Metric | Before | After |','|---|---:|---:|']
 for label,key in [('Selection precision','precision'),('Selection recall','recall'),('Wrong share of accepted scored matches','false_positive_rate'),('Rejected known-positive share','false_negative_rate'),('No-match share of all queries','no_match_rate')]:out.append(f"| {label} | {percent(before['overall'][key])} | {percent(after['overall'][key])} |")
 for label,key in [('Family error / accepted queries','food_family_error_rate'),('Prepared error / accepted queries','prepared_food_false_positive_rate')]:out.append(f'| {label} | {percent(before[key])} | {percent(after[key])} |')
 for group in ('cheese','meat','prepared'):
  for label,key in [('pair precision','precision'),('pair recall','recall'),('pair accuracy','accuracy'),('negative-pair false-positive rate','false_positive_rate')]:out.append(f"| {group.title()} {label} | {percent(before['pair_metrics'][group][key])} | {percent(after['pair_metrics'][group][key])} |")
 out+=['','Pair tests exercise isolated structural acceptance under strong semantic support, not production top-1 ranking. Pair accuracy counts both true positives and true negatives; high rejection precision does not imply 99% overall structural accuracy. Query wrong-share uses wrong/(correct+wrong accepted); pair false-positive rate uses FP/(FP+TN).',
 '', '## Bucket calibration (proxy only)','', '| Phase / bucket | Count | Precision | Conditional recall | Wrong accepted share |','|---|---:|---:|---:|---:|']
 for phase,report in [('Before',before),('After',after)]:
  for bucket in ('exact','high','medium','low','no_safe_match'):
   values=report['bucket_calibration'].get(bucket,{})
   out.append(f"| {phase} {bucket} | {values.get('count',0)} | {percent(values.get('precision'))} | {percent(values.get('recall'))} | {percent(values.get('false_positive_rate'))} |")
 out+=['','Recall inside an accepted bucket is conditional on that bucket, not the bucket’s share of all valid ingredients. No Medium/Low observations were manufactured.',
 '', '## Fixed-seed random QA','', '| Stratum | Requested | Sampled | Assistant heuristic classifications |','|---|---:|---:|---|']
 for name,bucket in qa.items():out.append(f"| {name} | {bucket['requested']} | {bucket['sampled']} | {cell(bucket.get('assistant_name_review_counts','Independent proxy pair labels only'))} |")
 out+=['','Seed: `20261006`. The review JSON retains every sample’s ingredient, expected IDs/proxy label, selected product, alternatives, ontology, score breakdown, confidence, assistant heuristic classification, and pending human status. Baseline Exact/High/Medium/Low/rejected strata are also retained. The accepted sample was reviewed through conservative name rules after direct inspection exposed prepared-food and fat/style errors. This is **assistant heuristic QA, not independent human QA**. Rejected/hard-category availability remains proxy-labelled. Zero Medium examples were available, so the requested 200 Medium reviews cannot be supplied from this population. Independent review of these exported samples is necessary before freeze.',
 '', '## False negatives','', f"Proxy rejected known-positive cases: {after['overall']['classifications'].get('SHOULD_HAVE_MATCHED',0)}. Reason classes: `{dict(fn_counts)}`.",
 'Required state/form/fat/bone/salt evidence is frequently missing from inventory titles. Some labelled positives conflict with exact-mode type/form policy or are proxy-label errors. False-negative diagnostics preserve expected SKUs and each ontology reason. No quantity, brand, embedding or score-threshold failure is inferred without evidence. Improve explicit catalog metadata and independently adjudicate availability before relaxing safeguards.',
 '', '## Representative corrected failures','', 'These are deliberately representative examples from the fixed input harvest, separate from random QA statistics. Safe abstention removes an unsafe or unverified purchase; it does not claim a valid replacement was found.',
 '', '| Ingredient | Before product | After product | Correction |','|---|---|---|---|']
 for r in corrections:out.append(f"| {cell(r['ingredient'])} | {cell(r['before_selected']['product_name'])} | {cell(r['after_selected']['product_name'] if r['after_selected'] else 'NO MATCH')} | {cell(r['explanation'])} |")
 out+=['','## Performance and validation','', '| Measurement | Before | After |','|---|---:|---:|']
 for label,key in [('Warm uncached median (ms)','warm_uncached_median_ms'),('Warm uncached p95 (ms)','warm_uncached_p95_ms'),('Batch elapsed (seconds)','batch_seconds'),('Batch ingredients/second','batch_ingredients_per_second')]:out.append(f"| {label} | {before['performance'][key]} | {after['performance'][key]} |")
 out+=['','Measurements use the same local snapshot and 100 fixed-seed warm uncached calls; batch timing includes startup and local embedding work. The matcher needs no per-ingredient LLM call. Diagnostic lexical mode works without loading an external model; optional BGE uses the existing local model/index with lexical degradation on failure.',
 f"Full Python suite: {review['tests']['full_suite_count']} tests; failures: `{failures}`. The sale endpoint test expects a pristine warmup manager after earlier suite tests made it ready; it passes independently (11/11). This unrelated suite-order assertion was left unchanged. Matcher/ontology/retrieval/quantity/adapter/real-recipe tests pass. The permanent corpus contains {review['tests']['regression_cases']} assertions exercised within the ontology test. Runtime artifact validation passes after updating only the matcher-version field in the manifest.",
 f"`git diff --check`: {review['tests']['diff_check']}. No files were staged, committed, pushed, stashed or reverted.",
 '', '## Files and usage','',
 'Changed: `Model/product_compatibility.py`, `Model/product_retrieval.py`, `Model/runtime_artifact_manifest.json` (matcher version only), `Model/tests/test_product_compatibility.py`, `Model/tests/test_real_recipe_regressions.py`. New: `Model/product_ontology.py`, `Model/tests/test_product_ontology.py`, two evaluation corpora, `scripts/build_ingredient_match_benchmark.py`, `scripts/review_ingredient_matcher.py`, `scripts/debug_ingredient_match.py`, this assembly script, the JSON/Markdown reports and `data/matcher_audit/` sidecars. Existing unrelated working-tree changes were preserved.',
 'Historical tests that bought implicit substitutes or unverified attributes now assert strict abstention. Positive basket integration fixtures use explicitly named meat cuts, without editing production recipe facts or shopping algorithms.',
 '', '```sh', '.venv/bin/python scripts/debug_ingredient_match.py "2 cups low-sodium chicken broth"', '.venv/bin/python scripts/debug_ingredient_match.py "parmesan" --mode substitute --semantic', '.venv/bin/python scripts/review_ingredient_matcher.py --phase after', '```',
 '', '## Freeze decision','', '**DO_NOT_FREEZE_MATCHER**. Exact/High proxy precision is below 99%; independent human QA is incomplete; Medium lacks validation data; cheese/meat pair recall and overall accuracy miss the requested target. Unknown metadata and compound/variant extraction still leave false positives and false negatives. Do not interpret passing regressions, low proxy prepared-error rates, or a large rule-labelled corpus as proof of perfection.', '']
 (ROOT/'ingredient_matcher_report.md').write_text('\n'.join(out))
 print(json.dumps({'corrected_failures':len(corrections),'regressions':review['tests']['regression_cases'],'qa_samples':{k:v['sampled'] for k,v in qa.items()},'overall':after['overall'],'test_failures':failures},indent=2))
if __name__=='__main__':main()
