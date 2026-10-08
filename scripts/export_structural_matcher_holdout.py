#!/usr/bin/env python3
"""Disjoint fixed-seed holdout from fresh actual outputs; labels stay blank."""
import argparse,collections,csv,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import norm
from human_qa_ingredient_matcher import category,add_diagnostic_alternatives,top_alternatives,immutable_hash,REVIEW_FIELDS,CATEGORIES


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,default=20261010);parser.add_argument('--output',type=Path,default=ROOT/'data/matcher_structural_holdout');args=parser.parse_args()
 paths=['data/matcher_validation/review.csv','Model/evaluation/ingredient_matcher_regressions.jsonl','Model/evaluation/structural_review_regressions.jsonl','Model/evaluation/real_recipe_match_regression_cases.jsonl','data/matcher_audit/harvest_ingredients.json','Model/evaluation/ingredient_inventory_benchmark.json']
 exclusions={};excluded=set()
 for path in paths:
  p=ROOT/path;queries=set()
  if path.endswith('.csv'):queries={r['ingredient_query'] for r in csv.DictReader(p.open())}
  elif path.endswith('.jsonl'):
   def collect(value):
    if isinstance(value,dict):
     for k,v in value.items():
      if k in ('ingredient','raw_ingredient','query','text','raw','matcher_text') and isinstance(v,str):queries.add(v)
      elif k=='ingredients' and isinstance(v,list):
       for entry in v:
        if isinstance(entry,str):queries.add(entry)
        else:collect(entry)
      elif isinstance(v,(dict,list)):collect(v)
    elif isinstance(value,list):
     for entry in value:collect(entry)
   for line in p.read_text().splitlines():collect(json.loads(line))
  elif path.endswith('harvest_ingredients.json'):queries=set(json.loads(p.read_text()))
  else:queries={q['text'] for q in json.loads(p.read_text())['queries']}
  exclusions[path]={norm(q) for q in queries};excluded.update(exclusions[path])
 population=ROOT/'data/matcher_structural_audit/after_population.jsonl'
 rows=[json.loads(line) for line in population.open()]
 # Use the same normalized identity for exclusions and within-sample uniqueness.
 # Keep the first population occurrence deterministically, without consulting labels.
 unique={}
 for r in rows:
  key=norm(r['ingredient_query'])
  if key not in excluded:unique.setdefault(key,r)
 eligible=list(unique.values())
 rng=random.Random(args.seed);used=set();cases=[];counts={}
 # Rare categories first. Redistribute unavailable quotas without selecting by
 # correctness or scores; the reviewer sees the resulting coverage limitation.
 pools={name:[r for r in eligible if name in category(r)] for name in CATEGORIES}
 order=sorted(CATEGORIES,key=lambda c:(len(pools[c]),c));hard=[]
 for name in order:
  pool=[r for r in pools[name] if r['case_id'] not in used];quota=38 if CATEGORIES.index(name)<4 else 37
  chosen=rng.sample(pool,min(quota,len(pool)))
  for r in chosen:used.add(r['case_id']);hard.append({**r,'sample_group':'hard: '+name})
 while len(hard)<300:
  added=False
  for name in order:
   pool=[r for r in pools[name] if r['case_id'] not in used]
   if pool and len(hard)<300:
    r=rng.choice(pool);used.add(r['case_id']);hard.append({**r,'sample_group':'hard: '+name});added=True
  if not added:raise ValueError('Not enough disjoint hard-category cases')
 cases.extend(hard)
 for group, requested, predicate in [('Exact/High',500,lambda r:r['selected_match'] and r['confidence'] in ('exact','high')),('Rejected',300,lambda r:not r['selected_match'])]:
  pool=[r for r in eligible if r['case_id'] not in used and predicate(r)]
  if len(pool)<requested:raise ValueError(f'Insufficient disjoint {group} population: {len(pool)}')
  for r in rng.sample(pool,requested):used.add(r['case_id']);cases.append({**r,'sample_group':group})
 counts=dict(collections.Counter(r['sample_group'] for r in cases))
 overlaps={path:sum(norm(r['ingredient_query']) in keys for r in cases) for path,keys in exclusions.items()}
 assert len(cases)==1100 and len(used)==1100 and len({norm(r['ingredient_query']) for r in cases})==1100 and not any(overlaps.values())
 from product_compatibility import ProductMatchService
 add_diagnostic_alternatives(cases,ProductMatchService())
 out=args.output;out.mkdir(parents=True,exist_ok=True)
 if (out/'review_labels.json').exists() or (out/'review_labeled.csv').exists():raise ValueError('Existing reviewer labels must never be overwritten; use a new output directory')
 import shutil
 shutil.copyfile(population,out/'population.jsonl')
 columns=['case_id','sample_group','ingredient_query','selected_product','match_type','confidence','food_family','subfamily','key_attributes','selected_product_ontology','top_3_alternatives','score_breakdown','current_matcher_decision','reason_codes']+REVIEW_FIELDS
 csvrows=[]
 for r in cases:
  p=r['selected_match'] or {};o=r['ontology']
  csvrows.append({'case_id':r['case_id'],'sample_group':r['sample_group'],'ingredient_query':r['ingredient_query'],'selected_product':p.get('product_name',''),'match_type':r['match_type'],'confidence':r['confidence'],'food_family':o.get('family') or '', 'subfamily':o.get('subfamily') or '', 'key_attributes':json.dumps(o),'selected_product_ontology':json.dumps(p.get('ontology',{})),'top_3_alternatives':json.dumps(top_alternatives(r)),'score_breakdown':json.dumps(p.get('score_breakdown',{})),'current_matcher_decision':'accepted' if p else 'rejected','reason_codes':json.dumps(r['reason_codes']),**{key:'' for key in REVIEW_FIELDS}})
 with (out/'review.csv').open('w',newline='') as handle:
  writer=csv.DictWriter(handle,fieldnames=columns);writer.writeheader();writer.writerows(csvrows)
 # Hash the literal CSV serialization, including blank optional fields.
 with (out/'review.csv').open(newline='') as handle:csvrows=list(csv.DictReader(handle))
 files=['Model/product_ontology.py','Model/food_identity_rules.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/morton_williams_product_features.json','Model/all_recipes.json']
 evaluation=json.loads((ROOT/'data/matcher_structural_audit/after_evaluation.json').read_text())
 manifest={'seed':args.seed,'sample_total':len(cases),'eligible_population':len(eligible),'sample_counts':{group:{'requested':500 if group=='Exact/High' else 300 if group=='Rejected' else (38 if CATEGORIES.index(group.removeprefix('hard: '))<4 else 37),'sampled':count} for group,count in counts.items()},'hard_quota_policy':'Rare categories first; unavailable quotas redistributed evenly over remaining eligible hard categories. No correctness labels consulted.','hard_available_counts':{name:len(pool) for name,pool in pools.items()},'exclusion_sources':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},'overlap_definition':'case-insensitive food-word normalization with punctuation, spacing and hyphen normalization; quantities retained (not canonical-food exclusion).','overlap_counts':overlaps,'blank_review_labels_confirmed':all(not r['review_label'] for r in csvrows),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},'population_sha256':hashlib.sha256(population.read_bytes()).hexdigest(),'review_csv_sha256':hashlib.sha256((out/'review.csv').read_bytes()).hexdigest(),'immutable_review_hashes':{r['case_id']:immutable_hash(r) for r in csvrows},'no_match_rate':evaluation['no_match_rate'],'latency':evaluation['latency'],'cases':cases}
 (out/'sample.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (out/'README.md').write_text('''# Fresh structural holdout\n\nLabels are blank. No matcher heuristics or proxy labels are an answer key. Review the 1,100 cases with `.venv/bin/python scripts/review_matcher_human.py --directory data/matcher_structural_holdout`. Start final analysis with `.venv/bin/python scripts/analyze_matcher_human_review.py --directory data/matcher_structural_holdout`; use --partial only for provisional metrics.\n\nSee ../matcher_validation/REVIEW_TOOL.md for shortcuts, persistence and manual assessment instructions. sample.json preserves complete outputs, source hashes, exclusions and overlap checks. Broad samples and hard strata are disjoint. Scarce hard categories have fewer cases because of exclusion of prior QA/regression/harvest/benchmark queries; do not interpret a small-category success as robust independent validation. No Medium coverage is fabricated. No matcher freeze is claimed.\n''')
 print(json.dumps({k:v for k,v in manifest.items() if k not in ('cases','immutable_review_hashes','source_hashes','exclusion_sources')},indent=2))

if __name__=='__main__':main()
