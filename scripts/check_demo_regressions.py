#!/usr/bin/env python3
import json,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility
results={};failures=[]
for p in sorted((ROOT/'Model/evaluation').glob('*regressions.jsonl')):
 rows=[json.loads(l) for l in p.read_text().splitlines()];bad=[]
 for r in rows:
  q=describe(r['ingredient']);f=r.get('product_feature');product=describe(r['product_name'],feature=f,product=True);d=compatibility(q,product,mode=r.get('mode','exact'))
  if (d.allowed or (r.get('mode')=='substitute' and d.match_type=='substitute'))!=r['expected_allowed']:bad.append({'case_id':r.get('case_id',r.get('id')),'ingredient':r['ingredient'],'product':r['product_name'],'expected':r['expected_allowed'],'allowed':d.allowed,'reasons':d.reasons})
 results[p.name]={'cases':len(rows),'failures':len(bad)};failures.extend(bad)
report={'corpora':results,'failures':failures,'total':sum(r['cases'] for r in results.values()),'catastrophic_new_accepted_negatives':sum(not r['expected'] and r['allowed'] for r in failures)}
(ROOT/'data/matcher_demo_hardening/corpus_checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

assert not failures
