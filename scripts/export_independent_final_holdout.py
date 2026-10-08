"""Final unlabeled holdout. Selection/context only; no correctness analysis."""
import ast,csv,json,hashlib,random,re,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import norm,ONTOLOGY_VERSION
from product_compatibility import MATCHER_VERSION
OUT=ROOT/'data/matcher_independent_final_holdout';SEED=20261017
POP=ROOT/'data/matcher_surgical_audit/after_population.jsonl'
KEYS={'ingredient','ingredient_query','raw_ingredient','query','text','raw','matcher_text','query_text'}
def collect(v):
 if isinstance(v,dict):
  for k,x in v.items():
   if k in KEYS and isinstance(x,str):yield x
   elif k=='ingredients' and isinstance(x,list):
    for i in x:
     if isinstance(i,str):yield i
     else:yield from collect(i)
   elif isinstance(x,(dict,list)):yield from collect(x)
 elif isinstance(v,list):
  for x in v:yield from collect(x)
def ids(v):
 if isinstance(v,dict):
  for k,x in v.items():
   if k=='case_id' and isinstance(x,str):yield x
   elif isinstance(x,(dict,list)):yield from ids(x)
 elif isinstance(v,list):
  for x in v:yield from ids(x)
def tags(r):
 o=r['ontology'];f=o.get('family');s=o.get('subfamily');t=r['ingredient_query'].lower();g=set()
 if f in {'produce','dairy','nuts','rice','grain','pasta','fish','sugar'}:g.add('semantic-head collisions')
 if f in {'prepared','dessert','dessert_mix','cookie','confection','pastry','chips','dressing','sausage','deli_meat'}:g.add('prepared-food boundaries')
 if f=='nonfood' or f=='dairy' and s in {'cream','heavy_cream','light_cream','sour_cream'} or re.search(r'cleaner|soap|bags|scent|tartar',t):g.add('food/nonfood boundaries')
 if f in {'meat','fish','shellfish','deli_meat','sausage'}:g.add('meat species/cuts/forms')
 if f=='cheese':g.add('cheese subtype/form')
 if f=='tomato' or f=='produce' and s=='tomato':g.add('tomato derivatives')
 if f=='broth':g.add('broth/stock species')
 if f in {'plant_milk','plant_yogurt'} or f=='dairy' and s in {'milk','yogurt','greek_yogurt'}:g.add('milk/yogurt variants')
 if f in {'nuts','beans','legume'}:g.add('nuts/legumes/peas')
 if f=='seasoning' or f=='produce' and s in {'chili_pepper','bell_pepper'}:g.add('pepper/spice identities')
 if o.get('state') or re.search(r'\b(fresh|frozen|canned|dried)\b',t):g.add('fresh/frozen/canned/dried')
 if o.get('purchase_variants') or o.get('grade') or o.get('variety') or o.get('treatment') or o.get('dietary_requirements'):g.add('required variants')
 if o.get('fat_level') or o.get('salt_level'):g.add('required fat/salt attributes')
 if o.get('identity_form')=='derived' or f in {'produce','rice','nuts','pasta','sugar'}:g.add('basic vs derived product')
 if not r['selected_match'] and f and f not in {'nonfood','prepared'}:g.add('candidate-retrieval FN opportunities')
 return g
CATEGORIES=['semantic-head collisions','prepared-food boundaries','food/nonfood boundaries','meat species/cuts/forms','cheese subtype/form','tomato derivatives','broth/stock species','milk/yogurt variants','nuts/legumes/peas','pepper/spice identities','fresh/frozen/canned/dried','required variants','required fat/salt attributes','basic vs derived product','candidate-retrieval FN opportunities']
def main():
 if OUT.exists():raise ValueError('Refuse to overwrite final holdout')
 frozen=json.loads((ROOT/'data/matcher_surgical_audit/source_hashes_after.json').read_text())
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
 files=sorted(set(list((ROOT/'Model/evaluation').glob('*.json'))+list((ROOT/'Model/evaluation').glob('*.jsonl'))+list((ROOT/'data').glob('matcher*/**/*.csv'))+list((ROOT/'data').glob('matcher*/**/*.json'))))
 sources={};excluded=set();excluded_ids=set();hashes={}
 for p in files:
  if p.name in {'source_hashes_after.json','source_hashes_before.json'}:continue
  if p.suffix=='.csv':v=list(csv.DictReader(p.open()))
  elif p.suffix=='.jsonl':v=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
  else:v=json.loads(p.read_text())
  qs=set(collect(v))
  if p.name=='harvest_ingredients.json' and isinstance(v,list):qs.update(x for x in v if isinstance(x,str))
  qnorm={norm(q) for q in qs if norm(q)};ci=set(ids(v));sources[str(p.relative_to(ROOT))]={'queries':qnorm,'ids':ci};excluded.update(qnorm);excluded_ids.update(ci);hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 # Conservative exclusion of literal manually specified queries in tests and
 # matcher evaluation scripts. Product-name literals are also excluded.
 manual=list((ROOT/'Model/tests').glob('*.py'))+list((ROOT/'scripts').glob('*.py'))
 for p in manual:
  if p.name==Path(__file__).name:continue
  tree=ast.parse(p.read_text());qs={norm(n.value) for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 1<=len(n.value)<=500 and norm(n.value)}
  sources[str(p.relative_to(ROOT))]={'queries':qs,'ids':set()};excluded.update(qs);hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 unique={}
 for line in POP.open():
  r=json.loads(line);q=norm(r['ingredient_query'])
  assert r['matcher_version']==MATCHER_VERSION
  if q not in excluded and r['case_id'] not in excluded_ids:unique.setdefault(q,r)
 eligible=sorted(unique.values(),key=lambda r:r['case_id']);rng=random.Random(SEED);used=set();cases=[]
 pools={g:[r for r in eligible if g in tags(r)] for g in CATEGORIES};shortfalls={}
 for g in sorted(CATEGORIES,key=lambda g:(len(pools[g]),g)):
  available=[r for r in pools[g] if r['case_id'] not in used];chosen=rng.sample(available,min(5,len(available)));shortfalls[g]=5-len(chosen)
  for r in chosen:used.add(r['case_id']);cases.append({**r,'sample_group':'hard/adversarial','hard_category':g})
 while len(cases)<75:
  added=False
  for g in sorted(CATEGORIES,key=lambda g:(sum(c.get('hard_category')==g for c in cases),g)):
   available=[r for r in pools[g] if r['case_id'] not in used]
   if available and len(cases)<75:
    r=rng.choice(available);used.add(r['case_id']);cases.append({**r,'sample_group':'hard/adversarial','hard_category':g});added=True
  if not added:raise ValueError('Insufficient truly disjoint hard examples')
 for group,n in [('accepted Exact/High',150),('rejected/no-match',75)]:
  pool=[r for r in eligible if r['case_id'] not in used and (bool(r['selected_match']) and r['confidence'] in ('exact','high') if group.startswith('accepted') else not r['selected_match'])]
  assert len(pool)>=n,(group,len(pool))
  for r in rng.sample(pool,n):used.add(r['case_id']);cases.append({**r,'sample_group':group,'hard_category':''})
 rng.shuffle(cases);norms={norm(r['ingredient_query']) for r in cases};caseids={r['case_id'] for r in cases}
 overlaps={p:{'normalized_query':len(norms&s['queries']),'case_id':len(caseids&s['ids'])} for p,s in sources.items()}
 assert len(cases)==len(norms)==len(caseids)==300 and not any(any(v.values()) for v in overlaps.values())
 fields=['case_id','sample_group','hard_category','ingredient_query','normalized_query_identity','current_matcher_decision','match_type','confidence','selected_product','selected_product_attributes','query_family','query_subfamily','product_family','product_subfamily','query_semantic_head','product_semantic_head','query_structural_attributes','top_3_alternatives','score_breakdown','rejection_reasons','matcher_diagnostics','review_label']
 rows=[]
 for r in cases:
  s=r['selected_match'] or {};q=r['ontology'];o=s.get('ontology',{});alts=[];seen={s.get('product_id')}
  for k in ['compatible_alternatives','substitution_candidates','rejected_candidates']:
   for a in r.get(k,[]):
    if a['product_id'] not in seen:seen.add(a['product_id']);alts.append({'candidate_context':k,**a})
  rows.append(dict(case_id=r['case_id'],sample_group=r['sample_group'],hard_category=r['hard_category'],ingredient_query=r['ingredient_query'],normalized_query_identity=norm(r['ingredient_query']),current_matcher_decision='accepted' if s else 'rejected',match_type=r['match_type'],confidence=r['confidence'],selected_product=s.get('product_name',''),selected_product_attributes=json.dumps(o),query_family=q.get('family') or '',query_subfamily=q.get('subfamily') or '',product_family=o.get('family') or '',product_subfamily=o.get('subfamily') or '',query_semantic_head=q.get('semantic_head') or '',product_semantic_head=o.get('semantic_head') or '',query_structural_attributes=json.dumps(q),top_3_alternatives=json.dumps(alts[:3]),score_breakdown=json.dumps(s.get('score_breakdown',{})),rejection_reasons=json.dumps({'result':r['reason_codes'],'candidates':[{'product':a['product_name'],'reasons':a['reason_codes'],'conflicts':a['conflicts']} for a in r.get('rejected_candidates',[])]}),matcher_diagnostics=json.dumps(r['diagnostics']),review_label=''))
 OUT.mkdir()
 with (OUT/'review.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 check=list(csv.DictReader((OUT/'review.csv').open()));assert len(check)==300 and sum(r['review_label']=='' for r in check)==300
 assert all(r['query_structural_attributes'] and r['matcher_diagnostics'] and r['match_type'] and r['confidence'] for r in check)
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
 category_counts=dict(collections.Counter(r['hard_category'] for r in rows if r['hard_category']));bundle=hashlib.sha256(json.dumps(frozen,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 manifest={'seed':SEED,'matcher_version':MATCHER_VERSION,'ontology_version':ONTOLOGY_VERSION,'matcher_bundle_sha256':bundle,'matcher_source_hashes':frozen,'population_source':str(POP.relative_to(ROOT)),'population_sha256':hashlib.sha256(POP.read_bytes()).hexdigest(),'eligible_disjoint_population':len(eligible),'sample_groups':dict(collections.Counter(r['sample_group'] for r in rows)),'hard_category_distribution':category_counts,'hard_pool_availability':{g:len(pools[g]) for g in CATEGORIES},'scarcity_before_redistribution':{g:n for g,n in shortfalls.items() if n},'actual_matcher_decisions':dict(collections.Counter(r['current_matcher_decision'] for r in rows)),'sanity_checks':{'total':300,'unique_case_ids':300,'unique_normalized_query_identities':300,'blank_labels':300,'overlap_count':0,'missing_context_where_available':0},'overlap_checks':overlaps,'exclusion_source_hashes':hashes,'normalization':'Ontology norm: case/Unicode/food-word/punctuation/spacing normalization; quantities retained. Also raw case-ID disjointness. Not a claim of canonical-food or recipe-template independence.','review_csv_sha256':hashlib.sha256((OUT/'review.csv').read_bytes()).hexdigest()}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(OUT/'sample_outputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in cases))
 text=f'''# Final blind independent validation\n\nExactly 300 unique cases: 150 accepted Exact/High, 75 rejected/no-match, and 75 hard/adversarial cases. All 300 review_label cells are intentionally blank. No correctness analysis, proxy truth, expected answers or review was generated. This is the final blind validation set for independent review outside Codex.\n\nMatcher: {MATCHER_VERSION}; ontology: {ONTOLOGY_VERSION}. Generation seed: {SEED}. Matcher bundle SHA-256: {bundle}. Individual frozen matcher/test/feature source hashes are in manifest.json. Bundle hash is SHA-256 of sorted compact JSON of those hashes. Source files were checked unchanged before and after export.\n\nPopulation source: {manifest['population_source']}, SHA-256 {manifest['population_sha256']}. These are frozen actual v3.6 outputs, not newly constructed queries. Available truly disjoint normalized queries: {len(eligible)}. No Medium group is generated.\n\nOverlap: zero normalized-query and case-ID matches across all indexed prior review/issue CSVs, sample/QA/audit JSONs, evaluation/regression/benchmark corpora and literal manually specified test/evaluation-script cases. manifest.json lists every source/hash/count. Full census population JSONL files are the sampling frame, not prior reviewed sets, and are not exclusion sources. Normalization retains quantities; canonical food identity/template independence is not claimed.\n\nHard strata use predeclared query/context risk tags, not correctness labels. Each requested category starts at five; rare pools are allocated first. Any scarcity is redistributed evenly to available hard categories without reusing cases. 'FN opportunities' means rejected queries with a recognized food family; it does not assert a false negative. Nonfood/head strata likewise identify review risks, not actual errors.\n\nHard category counts: {json.dumps(category_counts,sort_keys=True)}. Scarcity (shortfall from five before redistribution): {json.dumps(manifest['scarcity_before_redistribution'],sort_keys=True)}. Pool availability is preserved in manifest.json.\n\nThe 75 hard cases may include accepted or rejected decisions. Actual decisions across all groups: {json.dumps(manifest['actual_matcher_decisions'])}. These totals are distinct from sampling quotas. Alternatives are the available production compatible/substitute/rejected candidates, up to three; no candidates are fabricated when fewer exist. A rejected query legitimately has no selected-product attributes/score. All existing matcher context is retained in sample_outputs.jsonl.\n\nSanity checks: 300 rows, 300 unique IDs, 300 unique normalized queries, 300 blank labels, zero overlap, zero missing context where data exists. No matcher behavior, product features or tests changed. No review or precision/recall calculation performed.\n'''
 (OUT/'README.md').write_text(text);print(json.dumps({k:manifest[k] for k in ['sample_groups','hard_category_distribution','scarcity_before_redistribution','sanity_checks','seed','matcher_version','matcher_bundle_sha256']},indent=2))
if __name__=='__main__':main()
