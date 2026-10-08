#!/usr/bin/env python3
"""Freeze all 22 diagnoses before the precision-first production edits."""
import csv,json,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/matcher_precision_hardening'
def classify(row):
 q=row['ingredient_query'].lower();p=row['selected_product'].lower()
 if 'ham' in q:return 'WRONG_FORM','meat','Uncooked center-cut ham differs from cooked/deli ham; purchase form/preparation must be verified.','May abstain on underdocumented ham products.'
 if 'fried chicken' in p:return 'PREPARED_FOOD_LEAKAGE','meat','Fried/breaded prepared meat cannot satisfy plain cooked/basic meat.','Explicit fried products need their own requested identity.'
 if 'cream of beans' in p:return 'WRONG_SEMANTIC_HEAD','dairy/legume','Cream-of-X compounds have the named food head, not dairy cream; protect cream-of-vegetable/legume soups.','Preserve cream cheese, sour cream and cream of coconut.'
 if 'bran' in q:return 'REQUIRED_VARIANT_DROPPED','cereal','Required cereal grain/bran variants need affirmative evidence.','Generic cereal remains generic.'
 if 'tuna' in q:return 'PREPARED_FOOD_LEAKAGE','fish','Pesto/sauced fish is a prepared/flavored identity, not plain fish.','Plain canned tuna and explicitly requested flavored fish stay distinct.'
 if 'mixed' in q:return 'COMPOUND_QUERY_ERROR','produce_mix','Explicit vegetable mixes retain their purchased head; component examples cannot select a component.','Do not parse unrelated compound ingredients as a purchasable mix.'
 if 'pasta' in q:return 'REQUIRED_VARIANT_DROPPED','pasta','Pasta shape and whole-wheat grain narrow structural candidates before scoring.','May abstain on generic or missing grain metadata.'
 if 'relish' in q:return 'WRONG_SEMANTIC_HEAD','pickle','Sweet pickle relish has a relish head/form; whole pickles are different.','Generic chopped pickles still allow whole pickles.'
 if 'imitation' in p:return 'NONFOOD_OR_INELIGIBLE_PRODUCT','meat','Imitation toppings cannot establish real-meat species/cut identity.','Do not assert SNAP ineligibility without evidence; this is a food-identity gate.'
 if 'red potatoes' in q:return 'REQUIRED_ATTRIBUTE_UNVERIFIED','produce','Declared potato varieties/colors require product evidence.','Unknown color metadata safely abstains.'
 if 'pineapple' in q:return 'WRONG_SEMANTIC_HEAD','produce/juice','In-juice packing phrases do not turn the fruit head into juice, including percentages.','Actual juice remains a distinct requested identity.'
 if 'rice' in q:return 'REQUIRED_ATTRIBUTE_UNVERIFIED','rice','Explicit grain length requires affirmative evidence.','Generic rice stays generic; unknown length abstains.'
 if 'sweet pickles' in q:return 'REQUIRED_VARIANT_DROPPED','pickle','Required sweet pickle variant cannot disappear into generic pickles.','Dill and sweet variants remain distinct.'
 if 'pine nuts' in q:return 'WRONG_SUBFAMILY','nuts','Specific nut species precedes the generic nuts parent.','Generic nuts may still match known nuts; specific nuts cannot select unknown species.'
 if 'seltzer' in p:return 'NONFOOD_OR_INELIGIBLE_PRODUCT','beverage','Alcohol/domain evidence must veto food ingredient matching before scoring.','Legitimate SNAP-eligible food products must remain eligible.'
 if 'vinegar' in q:return 'WRONG_SUBFAMILY','acid','Declared vinegar fruit/style subfamily must be preserved.','Generic vinegar remains a parent; wrong flavored vinegar is not exact.'
 if 'sardines' in p:return 'WRONG_SEMANTIC_HEAD','fish/produce','A named protein head dominates fruit modifiers, including preserved lemon.','Fruit-only queries cannot match meat/fish containing fruit.'
 if 'cherries' in q:return 'REQUIRED_ATTRIBUTE_UNVERIFIED','produce','Sweet/tart cherry variants remain purchase attributes; Morello is tart.','Unknown cherry variety safely abstains for specific queries.'
 raise ValueError(row)
def main():
 if (OUT/'root_causes.json').exists():raise ValueError('Frozen diagnosis exists; do not overwrite')
 OUT.mkdir(exist_ok=True);qa=ROOT/'data/matcher_micro_holdout';rows=list(csv.DictReader((qa/'micro_holdout_assistant_labeled.csv').open()));original={r['case_id']:r for r in csv.DictReader((qa/'review.csv').open())};manual={'review_label','reviewer','review_notes','failure_cause','wrong_family','prepared_food_false_positive','structurally_correct'}
 assert len(rows)==300 and {r['case_id'] for r in rows}==set(original);assert all(all(r[k]==original[r['case_id']][k] for k in original[r['case_id']] if k not in manual) for r in rows)
 byid={r['case_id']:r for r in rows};issues=list(csv.DictReader((qa/'micro_holdout_assistant_issues.csv').open()));assert all(r==byid[r['case_id']] for r in issues)
 cases=[]
 for row in rows:
  if row['review_label']=='WRONG':
   cause,family,rule,risk=classify(row);cases.append({'case_id':row['case_id'],'ingredient':row['ingredient_query'],'selected_product':row['selected_product'],'root_cause':cause,'general_rule':rule,'affected_family':family,'regression_risk':risk,'review_notes':row['review_notes']})
 assert len(cases)==22
 files=['Model/product_ontology.py','Model/food_identity_rules.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/runtime_artifact_manifest.json']
 for file in files:(OUT/(Path(file).name+'.before')).write_bytes((ROOT/file).read_bytes())
 (OUT/'source_hashes_before.json').write_text(json.dumps({f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
 for file in ['after_evaluation.json','after_population.jsonl']:(OUT/('before_'+file.removeprefix('after_'))).write_bytes((ROOT/'data/matcher_micro_cleanup'/file).read_bytes())
 report={'provenance':'assistant QA, not perfect gold or independent certification','label_counts':dict(collections.Counter(r['review_label'] for r in rows)),'wrong_root_cause_counts':dict(collections.Counter(r['root_cause'] for r in cases)),'cases':cases};(OUT/'root_causes.json').write_text(json.dumps(report,indent=2)+'\n')
 with (OUT/'wrong_root_causes.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
 print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
if __name__=='__main__':main()
