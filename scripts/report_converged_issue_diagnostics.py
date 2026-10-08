#!/usr/bin/env python3
"""Assistant adjudication of replayed material issues; unresolved never correct."""
import json,csv,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/matcher_convergence_audit'
WRONG={
 'bb0064fa4ab239f5cfd9':'Cream selected cream-carbonara ramen: purchased ramen head remains unrecognized.',
 'b2a78fb4e52785a0f69a':'Pure wild rice selected long-grain/wild-rice blend: mixture specificity not represented.',
 '11c071770ed47506b398':'Dark brown sugar selected light brown sugar: requested shade/grade omitted from identity.',
 '08ef785ef680d8deaacb':'Plain marshmallow selected toasted marshmallow: unrequested processing not represented.',
 'b58d63daf5b671a0dcfa':'Pineapple spears selected sliced pineapple: purchase-form evidence is insufficient for the requested shape.'}
UNRESOLVED={
 '097b8aa9faede8e01e3e':'Listed fruit components vs tropical fruit salad: composition scope/state is not verified.',
 'ea7b2e23bf257b8902a5':'White potato variety is not verified by generic potato metadata.',
 '937e72e1bf25de6719f0':'Sliced packaged jalapeno state/treatment is undocumented; raw/fresh suitability unresolved.',
 '927adc62347ca968a6ce':'Truncated Pepperidge Farm Lemon Frozen record does not establish actual purchased product head.',
 '15139854a291ee5ea17f':'Requested 50–70% cocoa content not verified by selected dark-chocolate-chip record.',
 '62e3883e14aae1a9a44c':'Egg-white specialty spaghetti is a changed selection whose suitability for unspecified ordinary pasta needs independent review.'}
def main():
 replay=json.loads((OUT/'known_issue_replay.json').read_text());rows=replay['rows'];counts={};material=[]
 for r in rows:
  label=r['original_review_label'];s=r['current_output']['selected_match'];cid=r['case_id'];outcome='ambiguous_not_counted_correct';note='Original AMBIGUOUS retained; never counted correct.'
  if label in ('WRONG','SHOULD_HAVE_MATCHED'):
   if not s:outcome='now_abstained' if label=='WRONG' else 'still_rejected';note='Current strict pipeline abstains; no review label overwritten.'
   elif cid in WRONG:outcome='still_wrong' if label=='WRONG' else 'newly_wrong';note=WRONG[cid]
   elif cid in UNRESOLVED:outcome='unresolved';note=UNRESOLVED[cid]
   else:
    outcome='now_correct_or_acceptable' if label=='WRONG' else 'now_recovered';note='Assistant inspected selected product against the requested head, subtype, explicit attributes and allowed kitchen preparation. This is reused-sample diagnostics, not independent certification.'
   material.append(r)
  r.update(diagnostic_outcome=outcome,assistant_adjudication=note)
  group=r['source_group'];counts.setdefault(group,{}).setdefault(label,collections.Counter())[outcome]+=1
 aggregate={label:dict(collections.Counter(r['diagnostic_outcome'] for r in rows if r['original_review_label']==label)) for label in ('WRONG','SHOULD_HAVE_MATCHED','AMBIGUOUS')}
 hashes=replay['source_hashes'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
 value={'provenance':'Assistant-reviewed issue replay and explicit assistant adjudication, not independent human ground truth. CORRECT includes acceptable substitutions; unresolved/AMBIGUOUS are never correct.','prior_issue_rows':len(rows),'material_rows':len(material),'aggregate':aggregate,'by_source':{g:{l:dict(c) for l,c in labels.items()} for g,labels in counts.items()},'source_hashes':hashes,'remaining_wrong_cases':[r['case_id'] for r in rows if r['diagnostic_outcome'] in ('still_wrong','newly_wrong')],'unresolved_cases':[r['case_id'] for r in rows if r['diagnostic_outcome']=='unresolved'],'rows':rows}
 (OUT/'known_issue_diagnostics.json').write_text(json.dumps(value,indent=2)+'\n')
 columns=['source_group','case_id','ingredient_query','original_review_label','original_selected_product','current_selected_product','diagnostic_outcome','assistant_adjudication']
 with (OUT/'known_issue_diagnostics.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows({**{k:r.get(k,'') for k in columns},'current_selected_product':(r['current_output']['selected_match'] or {}).get('product_name','')} for r in rows)
 print(json.dumps({k:v for k,v in value.items() if k not in ('rows','source_hashes')},indent=2))
if __name__=='__main__':main()
