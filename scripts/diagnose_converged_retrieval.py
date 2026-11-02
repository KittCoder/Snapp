#!/usr/bin/env python3
"""Stage-separated family and compatibility retrieval diagnostics, no answer key."""
import json,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService,profile_from_query
from product_ontology import compatibility,describe
OUT=ROOT/'data/matcher_convergence_audit';service=ProductMatchService()
known=json.load((ROOT/'data/matcher_release_hardening/holdout_diagnostics.json').open())['candidate_references']
suggested=[r for r in json.load((ROOT/'data/matcher_structural_audit/root_causes.json').open())['cases'] if r['review_label']=='SHOULD_HAVE_MATCHED']
sets={'inspected_known_valid_10':[{'case_id':r['case_id'],'query':r['query'],'reference_ids':[r['reference_product_id']],'provenance':r['provenance']} for r in known],'historical_suggested_52':[{'case_id':r['case_id'],'query':r['ingredient_query'],'reference_ids':r['reference_product_ids'],'provenance':r['reference_status']} for r in suggested]}
report={}
for name,refs in sets.items():
 traces=[];family_hits=collections.Counter();compatible_hits=collections.Counter()
 for r in refs:
  q,_=profile_from_query(r['query'],service.overrides);family=service.identity_catalog.family_candidate_ids(q.ontology);allowed=service.identity_catalog.candidate_ids(q.ontology);expected=set(r['reference_ids']);ranks={};family_ranks={}
  for k in (5,10,20,50):
   raw=service.retriever.retrieve_product_candidates(q.normalized_signature,limit=k,use_semantic=True,allowed_product_ids=family)
   gated=service.retriever.retrieve_product_candidates(q.normalized_signature,limit=k,use_semantic=True,allowed_product_ids=allowed)
   raw_ids=[c.product_id for c in raw.candidates];ids=[c.product_id for c in gated.candidates]
   family_hits[k]+=bool(expected & set(raw_ids));compatible_hits[k]+=bool(expected & set(ids))
   family_ranks[str(k)]=next((i+1 for i,p in enumerate(raw_ids) if p in expected),None);ranks[str(k)]=next((i+1 for i,p in enumerate(ids) if p in expected),None)
  compatible=expected & allowed;current=service.match_recipe_ingredient(r['query'],use_semantic=True);selected=current.selected_match and current.selected_match.product_id
  if not compatible:stage='RETRIEVED_BUT_REJECTED' if family_ranks['50'] else 'NOT_RETRIEVED';detail='reference also structurally rejected' if not family_ranks['50'] else 'required identity/attribute gate'
  elif not ranks['50']:stage='NOT_RETRIEVED';detail='compatible reference absent from gated top50'
  elif selected in expected:stage='REFERENCE_SELECTED';detail='selected known/suggested reference'
  else:stage='RETRIEVED_AND_COMPATIBLE_BUT_LOST_RANKING';detail='margin/threshold abstention' if selected is None else 'different selected candidate, not automatically judged wrong'
  gates={pid:list(compatibility(q.ontology,service.identity_catalog.identities[pid]).reasons) if pid in service.identity_catalog.identities else ['not_eligible_catalog'] for pid in expected}
  traces.append({**r,'stage':stage,'detail':detail,'family_pool_size':len(family),'compatible_pool_size':len(allowed),'family_ranks':family_ranks,'compatible_ranks':ranks,'gate_reasons':gates,'selected_product_id':selected})
 report[name]={'reference_queries':len(refs),'family_only_recall':{str(k):family_hits[k]/len(refs) for k in (5,10,20,50)},'compatible_recall':{str(k):compatible_hits[k]/len(refs) for k in (5,10,20,50)},'stage_counts':dict(collections.Counter(r['stage'] for r in traces)),'traces':traces}
# Counts below describe deterministic catalog exclusions, not false-positive rates
# or the number of embedding candidates actually scored.
identities=list(service.identity_catalog.identities.values());domain=sum(i.domain!='food' for i in identities);derived=sum(i.domain=='food' and i.identity_form=='derived' for i in identities);basic_queries=0
for row in map(json.loads,(OUT/'after_population.jsonl').open()):
 q=describe(row['ingredient_query']);basic_queries+=q.identity_form=='basic' and not q.ambiguous and not q.alternatives
report['catalog_gate_counts']={'eligible_catalog_products':len(identities),'wrong_domain_catalog_exclusions':domain,'derived_food_catalog_products':derived,'unambiguous_basic_nonalternative_population_queries':basic_queries,'basic_vs_derived_incompatible_catalog_pairs':basic_queries*derived,'count_definition':'Wrong-domain count is distinct eligible product identities vetoed globally. Basic/derived count is the cross-product of unambiguous basic queries and derived catalog products rejected before similarity; not observed false positives or returned-candidate count.'}
(OUT/'candidate_recall.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:{a:b for a,b in v.items() if a!='traces'} for k,v in report.items()},indent=2))
