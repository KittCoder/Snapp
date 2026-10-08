#!/usr/bin/env python3
"""Freeze final assistant-QA evidence before any matcher edits."""
import csv,json,hashlib,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService,profile_from_query
from product_ontology import compatibility
OUT=ROOT/'data/matcher_micro_cleanup'
def cause(row):
 q=row['ingredient_query'].lower();p=row['selected_product'].lower()
 if 'unflavored gelatin' in q and 'unflavored gelatin' in p:return 'OTHER','Assistant label disagreement: explicit unflavored gelatin matches unflavored gelatin. Keep label and adjudicate independently.'
 if 'metal care' in p:return 'NONFOOD_LEAKAGE','Nonfood name/category evidence must hard-block all food identities; e.g. silver polish, furniture cleaner, cosmetic cream.'
 if any(x in p for x in ('strudel','spread','pate','protein treats','fluff','crispy','seasoning','vitaminwater')):return 'PREPARED_FOOD_LEAKAGE','Purchased derivative/head dominates component nouns; protects fruit pastry, nut snack, meat pate, flavored beverage and seasoning.'
 if 'paste' in p or any(x in q for x in ('cream sauce','sauce','syrup','peel','concentrate','in juice','pepper flakes')):return 'WRONG_SEMANTIC_HEAD','Resolve outer product head and packing medium before component nouns; applies to other sauces, extracts, fruit peels and juice-packed fruits.'
 if 'canadian bacon' in p:return 'WRONG_CUT','Back/Canadian bacon has a distinct cut identity from ordinary belly bacon; preserve species/cut and rendered-fat separation.'
 if 'snow peas' in q or 'brazil nuts' in q or 'spaghetti squash' in p:return 'WRONG_SUBFAMILY','Real compound taxa precede shared component words; protects other squash names, legumes and nut species.'
 if 'hint' in q:return 'COMPOUND_QUERY_ERROR','Alternatives/compound options must not collapse into a flavor/drink ingredient; parse or abstain rather than selecting a component derivative.'
 if 'speck' in q or 'season salt' in q:return 'QUERY_NORMALIZATION_ERROR','Quantity and conventional aliases establish seasoning identity, not produce or plain mineral salt.'
 if 'microwavable' in q or 'peppercorn' in q:return 'WRONG_FORM','Purchased microwave-ready/whole-peppercorn forms require evidence; generic products do not satisfy them.'
 if any(x in q for x in ('fat-reduced','sweet paprika','whole-grain','candied','extra virgin','flavored gelatin')):return 'REQUIRED_ATTRIBUTE_DROPPED','Explicit purchased grade, flavor, processing, grain, fat and sweetness narrow candidates; applies to unseen foods/brands.'
 if 'tuna' in q:return 'FLAVOR_LEAKAGE','Unrequested material fish flavors must be blocked just as meat/dairy variants are.'
 if 'olive' in q:return 'WRONG_SEMANTIC_HEAD','Shared cooking-oil head must scope over olive/vegetable alternatives; olives are not oils.'
 raise ValueError(row)
def main():
 if (OUT/'root_causes.json').exists():raise ValueError('Never overwrite frozen pre-edit evidence')
 OUT.mkdir(exist_ok=True);files=['Model/product_ontology.py','Model/food_identity_rules.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/runtime_artifact_manifest.json']
 for file in files:(OUT/(Path(file).name+'.before')).write_bytes((ROOT/file).read_bytes())
 (OUT/'source_hashes_before.json').write_text(json.dumps({f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
 for file in ['after_evaluation.json','after_population.jsonl']:(OUT/('before_'+file.removeprefix('after_'))).write_bytes((ROOT/'data/matcher_final_cleanup'/file).read_bytes())
 rows=list(csv.DictReader((ROOT/'data/matcher_final_holdout/final_holdout_assistant_labeled.csv').open()));original={r['case_id']:r for r in csv.DictReader((ROOT/'data/matcher_final_holdout/review.csv').open())};assert len(rows)==700 and set(original)=={r['case_id'] for r in rows}
 manual={'review_label','reviewer','review_notes','failure_cause','wrong_family','prepared_food_false_positive','structurally_correct'}
 assert all(all(r[k]==original[r['case_id']][k] for k in original[r['case_id']] if k not in manual) for r in rows)
 issues=list(csv.DictReader((ROOT/'data/matcher_final_holdout/final_holdout_assistant_issues.csv').open()));byid={r['case_id']:r for r in rows};assert all(r==byid[r['case_id']] for r in issues)
 service=ProductMatchService();cases=[]
 for row in rows:
  if row['review_label'] not in ('WRONG','SHOULD_HAVE_MATCHED'):continue
  q,_=profile_from_query(row['ingredient_query'],service.overrides);refs=[]
  for alt in json.loads(row['top_3_alternatives']):
   pid=alt.get('product_id');identity=service.identity_catalog.identities.get(pid)
   if identity:refs.append({'product_id':pid,'product_name':alt['product_name'],'ontology':identity.to_dict(),'gate_reasons':list(compatibility(q.ontology,identity).reasons)})
  if row['review_label']=='WRONG':c,rule=cause(row);stage='ONTOLOGY / COMPATIBILITY'
  else:
   reason=json.loads(row['reason_codes']);c='ONTOLOGY_MISCLASSIFICATION';rule='Correct genuine head/alias and preparation rules; unsupported required metadata stays unknown.'
   stage='NORMALIZATION' if 'or ' in row['ingredient_query'].lower() and 'ambiguous_identity_or_variant' in reason else 'ONTOLOGY' if q.ontology.family in (None,'prepared') else 'UNKNOWN_METADATA' if refs and any('unverified_' in x for x in refs[0]['gate_reasons']) else 'COMPATIBILITY'
  cases.append({**row,'root_cause':c,'general_rule':rule,'first_failure_stage':stage,'before_query_ontology':q.ontology.to_dict(),'reference_candidates':refs})
 assert sum(c['review_label']=='WRONG' for c in cases)==38 and sum(c['review_label']=='SHOULD_HAVE_MATCHED' for c in cases)==33
 report={'provenance':'assistant labels, not independent certification','counts':dict(collections.Counter(r['review_label'] for r in rows)),'wrong_root_cause_counts':dict(collections.Counter(r['root_cause'] for r in cases if r['review_label']=='WRONG')),'cases':cases}
 (OUT/'root_causes.json').write_text(json.dumps(report,indent=2)+'\n')
 with (OUT/'wrong_root_causes.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=['case_id','ingredient_query','selected_product','root_cause','general_rule']);writer.writeheader();writer.writerows({k:r[k] for k in writer.fieldnames} for r in cases if r['review_label']=='WRONG')
 print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
if __name__=='__main__':main()
