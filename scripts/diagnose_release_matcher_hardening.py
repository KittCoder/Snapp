#!/usr/bin/env python3
"""Explicit changed-product adjudication and stage traces, not human certification."""
import json,csv,sys,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService,profile_from_query
from product_ontology import compatibility
OUT=ROOT/'data/matcher_release_hardening'
SUPPORTED={
'f399fc150a3074e52306':('Eggplant','Aubergine is eggplant; plain purchased vegetable.'),
'226cb030436d5f173e17':('Progresso Italian Style Bread Crumbs','Explicit Italian crumb style.'),
'0a3a7573b83e3aa5c146':('Spectrum Avocado Oil','Plain cooking oil satisfies the oil branch.'),
'4c28a08aca769815f387':('Morton Salt','Plain salt head.'),
'90025f1507af0208bb4c':('McCormick Pure Vanilla Extract','Cooking essence/extract alias with explicit product extract head.'),
'7e3f1b42eed9496e862a':('Eden Foods Garbanzo Beans, Chickpeas, organic','Plain chickpeas; cooking is kitchen preparation, no required purchased canned state.'),
'47e1459bff51d5c43098':('Pork Spareribs','Explicit species and sparerib cut.'),
'6478033ee44d3c73a95f':('Tabasco Our hottest hot sauce yet!','Explicit hot sauce head.'),
'9a7e27b334141642272a':("Hellmann's Light Mayonnaise",'Light mayonnaise identifies reduced fat.'),
'c0883998e81f69f7370a':('Zespri Organic SunGold Kiwifruit','Explicit kiwi fruit identity; no requested green variety.'),
'135dafd446ac6478fc91':("Albert's Organic Bunched Red Radish",'Explicit radish identity; plural/singular alias.'),
'9292f203fe348c8a3e49':('HF Crushed Red Pepper','Explicit crushed red pepper identity.'),
'19fab69b9dcc3a3caf88':('Aladdin Whole Wheat Pita Bread','Explicit pita head and whole-wheat attribute.'),
'a282b61d16694c727fa8':('Sunsweet Dates, Chopped','Explicit dates and chopped form.'),
'cbdb8ecba0df7472828b':('Simply Organic Nutmeg','Spanish nutmeg alias; product head verified, company-prefix collision blocked.')}
STAGES={
'47e1459bff51d5c43098':('COMPATIBILITY','Sparerib cut missing from anatomical-cut recognition.'),
'27b15459cba4c7070eed':('COMPATIBILITY','Fresh state not verified on generic strawberry records; no inference.'),
'6478033ee44d3c73a95f':('ONTOLOGY','Known hot sauce classified as generic prepared food.'),
'a86d6cebb48b30551786':('COMPATIBILITY','Dried thyme state absent from candidate evidence.'),
'37fd2e68d535dce95541':('COMPATIBILITY','Required dry crumb state absent; some alternatives are seasoned/prepared.'),
'9a7e27b334141642272a':('COMPATIBILITY','Light mayonnaise reduced-fat alias not recognized.'),
'828f7072e0cae33e1834':('ONTOLOGY','Generic dried-bean parent identity absent; retained abstention.'),
'a61085deae69c70c3edf':('NORMALIZATION','Shared bell-pepper head is not scoped over yellow-or-red alternatives.'),
'4056a4a4993641fa48b1':('COMPATIBILITY','Required canned state absent from product evidence.'),
'c0883998e81f69f7370a':('ONTOLOGY','Kiwi/kiwifruit identity absent.'),
'39a8744b1c39a8918a35':('NORMALIZATION','Nutmeats alias absent.'),
'135dafd446ac6478fc91':('ONTOLOGY','Radish identity absent.'),
'9292f203fe348c8a3e49':('NORMALIZATION','Crushed hot red pepper alias absent.'),
'19fab69b9dcc3a3caf88':('ONTOLOGY','Pita without trailing bread noun absent; whole-wheat modifier now retained.'),
'b8478bf14f6485337095':('NORMALIZATION','Parenthetical alternative nut examples are ambiguous.'),
'a282b61d16694c727fa8':('ONTOLOGY','Date fruit identity absent.'),
'c81ea85493ea09ffed04':('COMPATIBILITY','Required canned state absent from product evidence.'),
'17448a5bdcc1ed0bde31':('THRESHOLD','Material-identity margin abstention; no threshold relaxation.'),
'cbdb8ecba0df7472828b':('NORMALIZATION','Spanish nutmeg alias absent; component-like company prefix now excluded.'),
'75d1c8717f2cd643d389':('COMPATIBILITY','Required canned state absent from product evidence.'),
'839ea05b7ea66e8d7f15':('ONTOLOGY','Generic vegetable parent unspecified; source mix composition unknown.'),
'f7139a9bde66019598a8':('ONTOLOGY','Toast-to-bread preparation alias absent; no broad recall changes.')}
def main():
 replay=json.loads((OUT/'holdout_replay.json').read_text());rows=replay['rows'];labels=ROOT/'data/matcher_final_200_holdout/final_200_holdout_assistant_labeled.csv';assert hashlib.sha256(labels.read_bytes()).hexdigest()==replay['label_file_sha256'];before={r['case_id']:r for r in map(json.loads,(OUT/'before_population.jsonl').open())};after={r['case_id']:r for r in map(json.loads,(OUT/'after_population.jsonl').open())}
 service=ProductMatchService();references=[];recoveries=[];new_good_changes=[]
 for row in rows:
  cid=row['case_id'];label=row['original_review_label'];now=row['current_output'];selected=now['selected_match'];pid=(selected or {}).get('product_id');assert pid==(after[cid]['selected_match'] or {}).get('product_id')
  outcome='not_readjudicated';note=''
  if label in ('WRONG','SHOULD_HAVE_MATCHED'):
   outcome='abstained' if label=='WRONG' and not pid else 'still_rejected' if not pid else 'unresolved'
   if pid and cid in SUPPORTED:
    name,note=SUPPORTED[cid];assert selected['product_name']==name,(cid,selected['product_name']);outcome='corrected' if label=='WRONG' else 'recovered'
   if label=='WRONG' and pid and selected['product_name']==row['original_selected_product']:outcome='remaining_wrong'
  row.update(diagnostic_outcome=outcome,assistant_diagnostic_note=note)
  if label=='SHOULD_HAVE_MATCHED':
   stage,reason=STAGES[cid];row.update(failure_stage_before=stage,failure_stage_explanation=reason,original_reason_codes=before[cid]['reason_codes']);recoveries.append({k:row[k] for k in ('case_id','ingredient_query','failure_stage_before','failure_stage_explanation','diagnostic_outcome')})
   if outcome=='recovered':references.append({'case_id':cid,'query':row['ingredient_query'],'reference_product_id':pid,'provenance':'Assistant inspected actual recovered product'})
  if label in ('CORRECT','ACCEPTABLE_SUBSTITUTE','AMBIGUOUS') and pid and selected['product_name']!=row['original_selected_product']:new_good_changes.append(cid)
 # Add one supported reference that remains unselected due to the margin gate.
 references.append({'case_id':'17448a5bdcc1ed0bde31','query':'1 slice of bread','reference_product_id':'mw_693090747e48a2d0','provenance':'Original visible Whole Grains Bread; acceptable for unspecified bread, still margin-abstained'})
 for ref in references:
  query,_=profile_from_query(ref['query'],service.overrides);allowed=service.identity_catalog.candidate_ids(query.ontology);retrieval=service.retriever.retrieve_product_candidates(query.normalized_signature,limit=20,use_semantic=True,allowed_product_ids=allowed);ids=[c.product_id for c in retrieval.candidates];pid=ref['reference_product_id'];ref.update(rank=ids.index(pid)+1 if pid in ids else None,structurally_allowed=pid in allowed,gate_reasons=list(compatibility(query.ontology,service.identity_catalog.identities[pid]).reasons))
 counts={label:dict(collections.Counter(r['diagnostic_outcome'] for r in rows if r['original_review_label']==label)) for label in ('WRONG','SHOULD_HAVE_MATCHED')}
 value=dict(provenance='Explicit assistant adjudication on reused hard-biased holdout, not independent human validation',case_count=200,label_file_sha256=replay['label_file_sha256'],diagnostic_counts=counts,known_valid_reference_count=len(references),known_valid_candidate_recall={str(k):sum(bool(r['rank'] and r['rank']<=k) for r in references)/len(references) for k in (5,10,20)},candidate_references=references,changed_prior_good_or_ambiguous_accepted_products=new_good_changes,rows=rows)
 (OUT/'holdout_diagnostics.json').write_text(json.dumps(value,indent=2)+'\n')
 (OUT/'false_negative_stages.json').write_text(json.dumps(recoveries,indent=2)+'\n')
 columns=['case_id','ingredient_query','original_review_label','original_selected_product','diagnostic_outcome','assistant_diagnostic_note','failure_stage_before','failure_stage_explanation'];small=[{**{k:r.get(k,'') for k in columns},'current_selected_product':(r['current_output']['selected_match'] or {}).get('product_name','')} for r in rows]
 with (OUT/'holdout_diagnostics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=columns+['current_selected_product']);w.writeheader();w.writerows(small)
 print(json.dumps({k:v for k,v in value.items() if k not in ('rows','candidate_references')},indent=2))
if __name__=='__main__':main()
