#!/usr/bin/env python3
"""Replay all five reviewed issue sets; never rewrite labels or generate samples."""
import json,csv,sys,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService
OUT=ROOT/'data/matcher_convergence_audit'
SOURCES={'950':'data/matcher_validation/review_assistant_issues.csv','1100':'data/matcher_structural_holdout/structural_holdout_assistant_issues.csv','700':'data/matcher_final_holdout/final_holdout_assistant_issues.csv','300':'data/matcher_micro_holdout/micro_holdout_assistant_issues.csv','200':'data/matcher_final_200_holdout/final_200_holdout_assistant_issues.csv'}
rows=[];hashes={}
for group,path in SOURCES.items():
 p=ROOT/path;hashes[path]=hashlib.sha256(p.read_bytes()).hexdigest()
 for r in csv.DictReader(p.open()):rows.append({'source_group':group,**r})
service=ProductMatchService();outputs=service.match_recipe_ingredients([r['ingredient_query'] for r in rows],limit=5,use_semantic=True);assert len(outputs)==len(rows)
results=[]
for old,now in zip(rows,outputs):
 new=now.to_dict();results.append({'source_group':old['source_group'],'case_id':old['case_id'],'ingredient_query':old['ingredient_query'],'original_review_label':old['review_label'],'original_selected_product':old['selected_product'],'original_review_notes':old['review_notes'],'current_output':new})
for path,digest in hashes.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
(OUT/'known_issue_replay.json').write_text(json.dumps({'provenance':'Reused assistant-reviewed issue sets; diagnostics only','source_hashes':hashes,'rows':results},indent=2)+'\n')
for r in results:
 s=r['current_output']['selected_match']
 if s and r['original_review_label'] in ('WRONG','SHOULD_HAVE_MATCHED'):print(r['source_group'],r['original_review_label'],r['case_id'],r['ingredient_query'],'=>',s['product_name'])
