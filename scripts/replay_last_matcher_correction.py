"""Replay existing assistant QA unchanged, diagnostics only; no new holdout."""
import csv,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService
OUT=ROOT/'data/matcher_last_correction';SOURCE=ROOT/'data/matcher_independent_final_holdout/independent_final_300_assistant_labeled.csv'
rows=list(csv.DictReader(SOURCE.open()));outputs=ProductMatchService().match_recipe_ingredients([r['ingredient_query'] for r in rows],limit=5,use_semantic=True)
value=[{'case_id':r['case_id'],'query':r['ingredient_query'],'label':r['review_label'],'before':r['selected_product'],'before_decision':r['current_matcher_decision'],'review_notes':r['review_notes'],'output':o.to_dict()} for r,o in zip(rows,outputs)]
(OUT/'holdout_replay.json').write_text(json.dumps(value,indent=2)+'\n')
for r in value:
 s=r['output']['selected_match']
 if r['label'] in ('WRONG','SHOULD_HAVE_MATCHED') or s and s['product_name']!=r['before']:
  print(r['label'],r['case_id'],r['query'],'=>',(s or {}).get('product_name'),flush=True)
for p,h in json.loads((OUT/'qa_source_hashes.json').read_text()).items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
