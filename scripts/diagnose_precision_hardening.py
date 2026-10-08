#!/usr/bin/env python3
"""Replay immutable assistant QA as diagnostics, never a new answer key."""
import csv,json,sys,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService,profile_from_query
from product_ontology import compatibility,describe
OUT=ROOT/'data/matcher_precision_hardening'
# Explicit assistant adjudication of changed products; not inferred from proxy labels.
SUPPORTED={
 '587653f8e0d76424e1fc':'Plain heavy cream satisfies unspecified cream.',
 'f749e597cacc38d42f64':'Cream branch of explicit cream-or-milk alternative.',
 '209d8185d07499667b57':'Plain heavy cream satisfies unspecified cream.',
 'cd6091fd4a389303c960':'Bran cereal verifies the requested bran identity; raisin/nut additions acceptable for unspecified cereal.',
 'ccde54c08ebc63ed3c30':'Plain oil-packed tuna can be flaked in the kitchen; no packing medium requested.',
 'e2df0ba054d58e161dfa':'Explicit sweet relish head.',
 '23f5a77d5a87c6de0e0e':'Real pork bacon can be diced into lardons; imitation topping rejected.',
 'efc675b720f83359aa17':'Explicit red potato variety.',
 '3a4c86b32a27dd697a5f':'Explicit red potato variety.',
 '8060424ba9af3a0fd79d':'Required white grain is no longer inferred from generic long-grain rice.',
 '927adc62347ca968a6ce':'Truncated Pepperidge Farm Lemon Frozen record does not verify its actual head; unresolved, never counted as correct. No brand/product exception added.',
 '750fd97836866a95d003':'Explicit sweet cucumber gherkins can be chopped.',
 '706f1084206a6ec3dba1':'Explicit pine nut subtype.',
 '56f3d6e22347bde141d5':'Explicit sweet cherry identity; state undocumented but no purchased fresh/frozen state specified.',
 '83558674c76a9dc773bd':'Explicit soy tofu identity.',
 '9918833e879546bef6d1':'Egg noodles can be cooked; no purchased cooked-state requirement.',
 '827e2b4a5ec33b745163':'Cooking vanilla alias resolves to pure vanilla extract.',
 '2837f0e26f34c869721b':'Explicit natural unsweetened cocoa.',
 '04a065ba9a103249fce4':'Explicit whole-grain wheat pasta; no requested shape.',
 'f2936a96904b78b58467':'Explicit dry lima beans.',
 '8d1b4a20673fee6ba5a7':'Plain pasta can be cooked; no shape or purchased cooked-state requirement.'}
def main():
 labels_path=ROOT/'data/matcher_micro_holdout/micro_holdout_assistant_labeled.csv';raw=labels_path.read_bytes();labels=list(csv.DictReader(raw.decode().splitlines()));assert len(labels)==300
 service=ProductMatchService();results=service.match_recipe_ingredients([r['ingredient_query'] for r in labels],limit=5,use_semantic=True)
 population={r['case_id']:r for r in map(json.loads,(OUT/'after_population.jsonl').open())};rows=[];references=[]
 for old,result in zip(labels,results):
  now=result.to_dict();chosen=now['selected_match'];pid=chosen and chosen['product_id'];pop=population[old['case_id']]['selected_match'];assert pid==(pop and pop['product_id']),old['case_id']
  note=SUPPORTED.get(old['case_id'],'');label=old['review_label'];outcome='not_adjudicated'
  if label in ('WRONG','SHOULD_HAVE_MATCHED'):
   outcome='abstained' if not pid and label=='WRONG' else 'still_rejected' if not pid else 'unresolved'
   if pid and note and old['case_id']!='927adc62347ca968a6ce':outcome='corrected' if label=='WRONG' else 'recovered'
   if pid and chosen['product_name']==old['selected_product'] and label=='WRONG':outcome='remaining_wrong'
  rows.append({'case_id':old['case_id'],'ingredient_query':old['ingredient_query'],'original_review_label':label,'original_selected_product':old['selected_product'],'current_selected_product':chosen and chosen['product_name'],'diagnostic_outcome':outcome,'assistant_diagnostic_note':note,'current_output':now})
  if outcome=='recovered':
   query,_=profile_from_query(old['ingredient_query'],service.overrides);allowed=service.identity_catalog.candidate_ids(query.ontology);retrieval=service.retriever.retrieve_product_candidates(query.normalized_signature,limit=20,use_semantic=True,allowed_product_ids=allowed);ids=[c.product_id for c in retrieval.candidates];rank=ids.index(pid)+1 if pid in ids else None
   references.append({'case_id':old['case_id'],'known_valid_product_id':pid,'rank':rank,'failure_stage_fixed':'COMPATIBILITY' if old['case_id'] in ('04a065ba9a103249fce4','8d1b4a20673fee6ba5a7','9918833e879546bef6d1') else 'ONTOLOGY','note':note})
 assert labels_path.read_bytes()==raw
 counts={label:dict(collections.Counter(r['diagnostic_outcome'] for r in rows if r['original_review_label']==label)) for label in ('WRONG','SHOULD_HAVE_MATCHED')}
 summary={'provenance':'Assistant-adjudicated changed decisions on reused hard-biased QA. Not independent validation; unresolved is not correct.','case_count':300,'label_file_sha256':hashlib.sha256(raw).hexdigest(),'diagnostic_counts':counts,'known_valid_recovered_reference_count':len(references),'known_valid_candidate_recall':{str(k):sum(bool(r['rank'] and r['rank']<=k) for r in references)/len(references) for k in (5,10,20)},'references':references,'rows':rows}
 (OUT/'micro_diagnostics.json').write_text(json.dumps(summary,indent=2)+'\n')
 fields=[k for k in rows[0] if k!='current_output']
 with (OUT/'micro_diagnostics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in rows)
 print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','references')},indent=2))
if __name__=='__main__':main()
