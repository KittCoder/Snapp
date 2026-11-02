#!/usr/bin/env python3
import json,csv,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService
OUT=ROOT/'data/matcher_release_hardening';QA=ROOT/'data/matcher_final_200_holdout'
labels=QA/'final_200_holdout_assistant_labeled.csv';raw=labels.read_bytes();rows=list(csv.DictReader(labels.open()));service=ProductMatchService();results=service.match_recipe_ingredients([r['ingredient_query'] for r in rows],limit=5,use_semantic=True)
assert len(results)==200
value={'provenance':'Reused assistant-labeled hard holdout; diagnostics only','label_file_sha256':hashlib.sha256(raw).hexdigest(),'rows':[{'case_id':old['case_id'],'original_review_label':old['review_label'],'ingredient_query':old['ingredient_query'],'original_selected_product':old['selected_product'],'current_output':now.to_dict()} for old,now in zip(rows,results)]}
assert labels.read_bytes()==raw
(OUT/'holdout_replay.json').write_text(json.dumps(value,indent=2)+'\n')
for r in value['rows']:
 if r['original_review_label'] in ('WRONG','SHOULD_HAVE_MATCHED'):print(r['original_review_label'],r['case_id'],r['ingredient_query'],'=>',(r['current_output']['selected_match'] or {}).get('product_name'),r['current_output']['reason_codes'])
