#!/usr/bin/env python3
import csv,json,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/matcher_demo_hardening'
RULES={
'f399fc150a3074e52306':('PREPARED_FOOD_LEAKAGE','produce','Fried/breaded produce is a prepared head, not raw produce.','Explicit fried requests need own identities.'),
'476f4e2faa23e99d3969':('REQUIRED_ATTRIBUTE_UNVERIFIED','produce','Require white cherry variety evidence through shared specificity.','Unknown variety abstains.'),
'd87faeafb2e0d876fe3c':('QUERY_NORMALIZATION_ERROR','fish/liquid','Cooking liquor/liquid from protein is not protein flesh.','Unknown cooking-liquid head abstains.'),
'f5ea3f95ed3bca513dbb':('WRONG_STATE','produce','Unspecified whole produce cannot silently become dried produce.','Preserve explicitly requested dried fruit.'),
'733ee7e854560ad0a4ea':('WRONG_SPECIES','meat','Veal identity must precede generic round/cut alias to beef.','Preserve generic cut inference only without explicit species.'),
'226cb030436d5f173e17':('REQUIRED_VARIANT_DROPPED','breadcrumbs','Italian seasoned crumb identity differs from panko/plain crumbs.','Generic crumbs remain generic.'),
'836b19c9f547874e57f2':('WRONG_SUBFAMILY','sauce','Thai chili sauce requires Thai-style subtype evidence.','Generic chili sauce remains generic.'),
'e3d36f4c84fd59e27e5c':('QUERY_NORMALIZATION_ERROR','pasta','Disjunctive pasta shapes must inherit shared whole-wheat modifier.','Malformed mixed-family alternatives abstain.'),
'0a3a7573b83e3aa5c146':('WRONG_SEMANTIC_HEAD','fat/fish','Protein packed in oil retains protein head, not packing component.','Preserve genuine oils and oil-based dressings.'),
'4c28a08aca769815f387':('PRODUCT_HEAD_LEAKAGE','seasoning/snack','Pita thins/chips retain snack head despite salt modifier.','Explicit snacks remain purchasable.'),
'bd6ca4228312c7fe8b57':('WRONG_FORM','seed/produce','Celery seed is a spice seed, not vegetable stalk.','Do not flatten celery salt or celery stalks.'),
'90025f1507af0208bb4c':('PRODUCT_HEAD_LEAKAGE','extract','Vanilla essence alias needs extract evidence; standalone flavor does not prove extract in products.','Cooking vanilla query alias retained.'),
'7e3f1b42eed9496e862a':('PREPARED_FOOD_LEAKAGE','beans/snack','Puffs have snack head; legume content does not make plain cooked legumes.','Plain canned/dry beans stay separate.')}
def main():
 assert not (OUT/'root_causes.json').exists();OUT.mkdir(exist_ok=True)
 qa=ROOT/'data/matcher_final_200_holdout';labels=list(csv.DictReader((qa/'final_200_holdout_assistant_labeled.csv').open()));original={r['case_id']:r for r in csv.DictReader((qa/'review.csv').open())};manual={'review_label','reviewer','review_notes','failure_cause','wrong_family','prepared_food_false_positive','structurally_correct'}
 assert len(labels)==200 and {r['case_id'] for r in labels}==set(original)
 assert all(all(r[k]==original[r['case_id']][k] for k in original[r['case_id']] if k not in manual) for r in labels)
 cases=[]
 for r in labels:
  if r['review_label']=='WRONG':
   cause,family,rule,risk=RULES[r['case_id']];cases.append(dict(case_id=r['case_id'],ingredient=r['ingredient_query'],selected_product=r['selected_product'],root_cause=cause,affected_family=family,general_rule=rule,regression_risk=risk,review_notes=r['review_notes']))
 assert len(cases)==13
 files=['Model/product_ontology.py','Model/food_identity_rules.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/runtime_artifact_manifest.json']
 for p in files:(OUT/(Path(p).name+'.before')).write_bytes((ROOT/p).read_bytes())
 (OUT/'source_hashes_before.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},indent=2)+'\n')
 for p in ('evaluation.json','population.jsonl'):(OUT/('before_'+p)).write_bytes((ROOT/'data/matcher_precision_hardening'/('after_'+p)).read_bytes())
 value=dict(provenance='Assistant QA, not independent human certification',label_counts=dict(collections.Counter(r['review_label'] for r in labels)),wrong_root_cause_counts=dict(collections.Counter(r['root_cause'] for r in cases)),cases=cases)
 (OUT/'root_causes.json').write_text(json.dumps(value,indent=2)+'\n')
 with (OUT/'wrong_root_causes.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
 print(json.dumps({k:v for k,v in value.items() if k!='cases'},indent=2))
if __name__=='__main__':main()
