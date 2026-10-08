#!/usr/bin/env python3
"""Assistant adjudication of replayed material issues; unresolved never correct."""
import json,csv,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/matcher_surgical_audit'
WRONG={}
UNRESOLVED={
 '15139854a291ee5ea17f':'Requested 50–70% cocoa content remains undocumented; not credited as recovered.',
 '62e3883e14aae1a9a44c':'Specialty egg-white noodle suitability remains unresolved; not credited as recovered.'}
INSPECTED_REPLACEMENTS={
 'b58d63daf5b671a0dcfa':('Pineapple','Plain whole pineapple can supply spears through the directional kitchen-cutting policy.'),
 '08ef785ef680d8deaacb':("Granny's Marshmallows, Mini",'Plain marshmallows replace toasted confections; mini size does not change the requested identity.'),
 '937e72e1bf25de6719f0':('Jalapeno Pepper Bag','Whole chili peppers can be diced; no processed-form unknown preservation inference is used.'),
 '11c071770ed47506b398':('Wholesome Organic Dark Brown Sugar','Selected brown sugar has explicit dark grade matching the required query grade.'),
 '927adc62347ca968a6ce':('Lemon','Simple lemon head establishes actual fruit; neither lemongrass nor lemon aioli is selected.')}
def main():
 replay=json.loads((OUT/'known_issue_replay.json').read_text());rows=replay['rows'];counts={};material=[]
 prior={r['case_id']:r for r in json.loads((OUT/'before_known_issue_diagnostics.json').read_text())['rows']}
 for r in rows:
  selected=r['current_output']['selected_match'];old=prior[r['case_id']]['current_output']['selected_match']
  if selected and (selected or {}).get('product_id')!=(old or {}).get('product_id'):
   assert r['case_id'] in INSPECTED_REPLACEMENTS
   assert selected['product_name']==INSPECTED_REPLACEMENTS[r['case_id']][0]
 for r in rows:
  label=r['original_review_label'];s=r['current_output']['selected_match'];cid=r['case_id'];outcome='ambiguous_not_counted_correct';note='Original AMBIGUOUS retained; never counted correct.'
  if label in ('WRONG','SHOULD_HAVE_MATCHED'):
   if not s:outcome='now_abstained' if label=='WRONG' else 'still_rejected';note='Current strict pipeline abstains; no review label overwritten.'
   elif cid in WRONG:outcome='still_wrong' if label=='WRONG' else 'newly_wrong';note=WRONG[cid]
   elif cid in UNRESOLVED:outcome='unresolved';note=UNRESOLVED[cid]
   else:
    outcome='now_correct_or_acceptable' if label=='WRONG' else 'now_recovered';note=INSPECTED_REPLACEMENTS[cid][1] if cid in INSPECTED_REPLACEMENTS else 'Selection unchanged from prior supported assistant diagnosis; carried forward, not independently recertified.'
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
