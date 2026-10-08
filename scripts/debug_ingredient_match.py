#!/usr/bin/env python3
"""Explain the production decision and structural rejects for an ingredient.

Lexical mode is the default: it works without loading an embedding model.
Use --semantic to add the existing local BGE/index supporting signal.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService,rank_identity_candidate
from product_ontology import describe,compatibility


def diagnose(text, mode='exact', semantic=False, limit=10):
 service=ProductMatchService(match_mode=mode)
 result=service.match_recipe_ingredient(text,limit=limit,use_semantic=semantic)
 identity=describe(text)
 allowed=service.identity_catalog.candidate_ids(identity,mode)
 # Diagnostic-only ungated retrieval makes excluded products visible. These
 # candidates NEVER participate in the production selection above.
 raw=service.retriever.retrieve_product_candidates(text,limit=limit,use_semantic=semantic)
 rejects=[];diagnostic_candidates=[]
 for candidate in raw.candidates:
  feature=service.feature_by_id[candidate.product_id]
  product=service.identity_catalog.identities[candidate.product_id]
  decision=compatibility(identity,product,mode)
  diagnostic_candidates.append({'candidate':candidate.to_dict(),'query_ontology':identity.to_dict(),'candidate_ontology':product.to_dict(),'hard_compatibility':{'match_type':decision.match_type,'allowed':decision.allowed,'reasons':list(decision.reasons),'unknown_attributes':list(decision.uncertain)},'ranked':rank_identity_candidate(candidate,identity,product,decision).to_dict()})
  if not decision.allowed and decision.match_type!='substitute':
   rejects.append(rank_identity_candidate(candidate,identity,product,decision).to_dict())
 return {'ingredient':text,'normalized_ingredient':result.normalized_ingredient_signature,
  'ontology':identity.to_dict(),'mode':mode,'confidence_semantics':'Rule/rank score, NOT a calibrated probability; independent human calibration pending.',
  'eligible_inventory_count':len(service.identity_catalog.identities),'structurally_eligible_count':len(allowed),
  'production_result':result.to_dict(),'final_rejection_reason':result.reason_codes if not result.selected_match else [],'diagnostic_only_ungated_candidates':diagnostic_candidates,'diagnostic_only_ungated_rejects':rejects}


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('ingredient');parser.add_argument('--mode',choices=['exact','substitute'],default='exact')
 parser.add_argument('--semantic',action='store_true');parser.add_argument('--limit',type=int,default=10)
 args=parser.parse_args();print(json.dumps(diagnose(args.ingredient,args.mode,args.semantic,args.limit),indent=2,allow_nan=False))
if __name__=='__main__':main()
