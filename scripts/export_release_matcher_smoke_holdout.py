#!/usr/bin/env python3
"""Fixed-seed, query-disjoint final blind holdout; no labels generated."""
import csv,json,hashlib,random,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import norm
from product_compatibility import ProductMatchService
from human_qa_ingredient_matcher import add_diagnostic_alternatives,top_alternatives,immutable_hash,REVIEW_FIELDS
OUT=ROOT/'data/matcher_release_smoke_holdout';AUDIT=ROOT/'data/matcher_release_hardening'
EXCLUSIONS=['data/matcher_final_200_holdout/review.csv','Model/evaluation/release_hardening_regressions.jsonl','data/matcher_micro_holdout/review.csv','Model/evaluation/precision_hardening_regressions.jsonl','data/matcher_validation/review.csv','data/matcher_structural_holdout/review.csv','data/matcher_final_holdout/review.csv','Model/evaluation/ingredient_matcher_regressions.jsonl','Model/evaluation/structural_review_regressions.jsonl','Model/evaluation/final_holdout_regressions.jsonl','Model/evaluation/micro_holdout_regressions.jsonl','Model/evaluation/real_recipe_match_regression_cases.jsonl','data/matcher_audit/harvest_ingredients.json','Model/evaluation/ingredient_inventory_benchmark.json']
def queries(value):
 if isinstance(value,dict):
  for key,v in value.items():
   if key in ('ingredient','raw_ingredient','query','text','raw','matcher_text') and isinstance(v,str):yield v
   elif key=='ingredients' and isinstance(v,list):
    for item in v:
     if isinstance(item,str):yield item
     else:yield from queries(item)
   elif isinstance(v,(dict,list)):yield from queries(v)
 elif isinstance(value,list):
  for item in value:yield from queries(item)
def excluded_queries(path):
 if path.suffix=='.csv':return {norm(r['ingredient_query']) for r in csv.DictReader(path.open())}
 if path.suffix=='.jsonl':return {norm(q) for line in path.read_text().splitlines() for q in queries(json.loads(line))}
 value=json.loads(path.read_text())
 return {norm(q) for q in value} if path.name=='harvest_ingredients.json' else {norm(q['text']) for q in value['queries']}
def groups(row):
 o=row['ontology'];family=o.get('family');sub=o.get('subfamily');out=set()
 if family in {'produce','nuts','cream','dairy','grain','pasta','rice','fish','sweetener'}:out.add('semantic-head traps')
 if family in {'prepared','sausage','deli_meat','dessert_mix','gelatin','gelatin_dessert','cookie','confection','cereal','produce_mix','gravy','dressing','pastry','chips'} or sub in {'strawberry','eggplant','bacon_fat'}:out.add('prepared-food/head boundaries')
 if family=='dairy' and sub in {'cream','heavy_cream','sour_cream','light_cream'} or family in {'plant_cream','leavener'}:out.add('nonfood boundary')
 if family in {'meat','sausage','deli_meat'} or sub=='bacon_fat':out.add('meat form')
 if family in {'tomato','sauce','condiment_paste'} or family=='produce' and sub=='tomato':out.add('tomato/sauce')
 if o.get('purchase_variants') or o.get('grade') or o.get('treatment') or o.get('fat_level') or o.get('state') or o.get('flavor'):out.add('required variants')
 if family in {'seasoning','pasta','nuts','legume','tea','pickle','chips'} or sub in {'asparagus','shallot','raisin','coconut'}:out.add('false-negative retrieval')
 return out
def main():
 diagnostics=json.loads((AUDIT/'holdout_diagnostics.json').read_text())
 counts=diagnostics['diagnostic_counts']['WRONG']
 assert counts.get('corrected',0)+counts.get('abstained',0)>=12,'Stopping gate not met'
 tests=json.loads((AUDIT/'separate_test_results.json').read_text())
 assert all(r['passed'] for r in tests.values()),'Regression gate not met'
 corpus=json.loads((AUDIT/'corpus_checks.json').read_text())
 assert not corpus['failures'] and corpus['catastrophic_new_accepted_negatives']==0,'Corpus gate not met'
 assert 'Ran 509 tests' in (AUDIT/'full_tests.log').read_text() and (AUDIT/'full_tests.log').read_text().rstrip().endswith('OK')
 if OUT.exists() and any(OUT.glob('*label*')):raise ValueError('Never overwrite labeled review data')
 assert json.loads((AUDIT/'after_evaluation.json').read_text())['no_match_rate']<=0.33
 strong=json.loads((AUDIT/'strong_category_cohorts.json').read_text())
 assert strong['cheese']['changed_selections']==0 and strong['meat']['accepted_after']>=strong['meat']['accepted_before']-1
 sources={f:excluded_queries(ROOT/f) for f in EXCLUSIONS};excluded=set().union(*sources.values());unique={}
 population=AUDIT/'after_population.jsonl'
 for line in population.open():
  row=json.loads(line);key=norm(row['ingredient_query'])
  if key not in excluded:unique.setdefault(key,row)
 eligible=list(unique.values());seed=20261014;rng=random.Random(seed);used=set();cases=[]
 quotas={'semantic-head traps':2,'prepared-food/head boundaries':2,'nonfood boundary':1,'meat form':2,'tomato/sauce':1,'required variants':1,'false-negative retrieval':1};pools={g:[r for r in eligible if g in groups(r)] for g in quotas};deficits={}
 for group in sorted(quotas,key=lambda g:(len(pools[g]),g)):
  pool=[r for r in pools[group] if r['case_id'] not in used];chosen=rng.sample(pool,min(quotas[group],len(pool)));deficits[group]=quotas[group]-len(chosen)
  for row in chosen:used.add(row['case_id']);cases.append({**row,'sample_group':'hard: '+group})
 # Scarcity is documented; redistribute uniformly, never by correctness.
 while len(cases)<10:
  added=False
  for group in quotas:
   pool=[r for r in pools[group] if r['case_id'] not in used]
   if pool and len(cases)<10:
    row=rng.choice(pool);used.add(row['case_id']);cases.append({**row,'sample_group':'hard: '+group});added=True
  if not added:raise ValueError('Insufficient disjoint hard-category population')
 for group,count in [('Exact/High',25),('Rejected',15)]:
  pool=[r for r in eligible if r['case_id'] not in used and (bool(r['selected_match']) and r['confidence'] in ('exact','high') if group=='Exact/High' else not r['selected_match'])]
  if len(pool)<count:raise ValueError(f'Insufficient {group}: {len(pool)} available, {count} required')
  for row in rng.sample(pool,count):used.add(row['case_id']);cases.append({**row,'sample_group':group})
 assert len(cases)==len({norm(r['ingredient_query']) for r in cases})==50
 overlaps={f:sum(norm(r['ingredient_query']) in keys for r in cases) for f,keys in sources.items()};assert not any(overlaps.values())
 add_diagnostic_alternatives(cases,ProductMatchService());OUT.mkdir(exist_ok=True)
 columns=['case_id','sample_group','ingredient_query','selected_product','match_type','confidence','food_family','subfamily','key_attributes','selected_product_ontology','top_3_alternatives','score_breakdown','current_matcher_decision','reason_codes']+REVIEW_FIELDS
 rows=[]
 for r in cases:
  p=r['selected_match'] or {};o=r['ontology'];rows.append({'case_id':r['case_id'],'sample_group':r['sample_group'],'ingredient_query':r['ingredient_query'],'selected_product':p.get('product_name',''),'match_type':r['match_type'],'confidence':r['confidence'],'food_family':o.get('family') or '', 'subfamily':o.get('subfamily') or '', 'key_attributes':json.dumps(o),'selected_product_ontology':json.dumps(p.get('ontology',{})),'top_3_alternatives':json.dumps(top_alternatives(r)),'score_breakdown':json.dumps(p.get('score_breakdown',{})),'current_matcher_decision':'accepted' if p else 'rejected','reason_codes':json.dumps(r['reason_codes']),**{k:'' for k in REVIEW_FIELDS}})
 with (OUT/'review.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
 rows=list(csv.DictReader((OUT/'review.csv').open()));assert all(not r['review_label'] for r in rows)
 (OUT/'population.jsonl').write_bytes(population.read_bytes());files=['Model/product_ontology.py','Model/food_identity_rules.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/morton_williams_product_features.json','Model/all_recipes.json']
 counts=dict(collections.Counter(r['sample_group'] for r in cases));manifest={'seed':seed,'sample_total':50,'eligible_population':len(eligible),'sample_counts':{g:{'requested':25 if g=='Exact/High' else 15 if g=='Rejected' else quotas[g[6:]],'sampled':n} for g,n in counts.items()},'hard_available_counts':{g:len(p) for g,p in pools.items()},'hard_quota_shortfalls_before_redistribution':deficits,'overlap_counts':overlaps,'overlap_definition':'Normalized query disjointness; quantities retained, not canonical-food independence.','exclusion_sources':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in EXCLUSIONS},'source_hashes':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},'population_sha256':hashlib.sha256(population.read_bytes()).hexdigest(),'review_csv_sha256':hashlib.sha256((OUT/'review.csv').read_bytes()).hexdigest(),'immutable_review_hashes':{r['case_id']:immutable_hash(r) for r in rows},'blank_review_labels_confirmed':True,'cases':cases}
 (OUT/'sample.json').write_text(json.dumps(manifest,indent=2)+'\n');(OUT/'README.md').write_text('# Final mini-holdout\n\n50 fixed-seed smoke cases, disjoint from all five prior QA sets and regression/historical corpora. Labels are blank; no automatic answer key. See sample.json for strata, scarcity, query-normalization limits and source hashes.\n\nRun `.venv/bin/python scripts/review_matcher_human.py --directory data/matcher_release_smoke_holdout`. Analyze only reviewed labels with `.venv/bin/python scripts/analyze_matcher_human_review.py --directory data/matcher_release_smoke_holdout`; incomplete reviews remain provisional.\n');print(json.dumps({k:v for k,v in manifest.items() if k not in ('cases','immutable_review_hashes','source_hashes','exclusion_sources')},indent=2))
if __name__=='__main__':main()
