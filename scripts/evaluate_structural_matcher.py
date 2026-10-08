#!/usr/bin/env python3
"""Actual-output population audit and explicitly named diagnostic proxy metrics."""
import argparse,collections,json,math,statistics,sys,time,types,random,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
OUT=ROOT/'data/matcher_structural_audit'


def matcher(phase):
 if phase=='before':
  for name in ['product_ontology','product_compatibility']:
   module=types.ModuleType(name);module.__file__=str(ROOT/'Model'/f'{name}.py');sys.modules[name]=module
   exec(compile((OUT/(name+'.py.before')).read_text(),module.__file__,'exec'),module.__dict__)
 else:__import__('product_compatibility')
 return sys.modules['product_compatibility']


def fraction(n,d):return n/d if d else None

def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['before','after'],required=True);parser.add_argument('--output',type=Path,default=OUT);args=parser.parse_args();OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
 module=matcher(args.phase);service=module.ProductMatchService();ontology=sys.modules['product_ontology']
 audit=json.loads((ROOT/'data/matcher_structural_audit/root_causes.json').read_text());issues={r['case_id']:r for r in audit['cases']}
 labels=list(csv.DictReader((ROOT/'data/matcher_validation/review_assistant_labeled.csv').open()))
 texts=[json.loads(line)['ingredient_query'] for line in (ROOT/'data/matcher_validation/population.jsonl').open()]
 started=time.perf_counter();results=[]
 if args.phase=='before':results=[json.loads(line) for line in (ROOT/'data/matcher_validation/population.jsonl').open()]
 else:
  for offset in range(0,len(texts),200):
   batch=texts[offset:offset+200];matched=service.match_recipe_ingredients(batch,limit=5,use_semantic=True)
   if len(matched)!=len(batch):raise ValueError('Output alignment failed')
   for text,result in zip(batch,matched):
    row=result.to_dict();row.update(ingredient_query=text,case_id=__import__('hashlib').sha256(text.encode()).hexdigest()[:20]);results.append(row)
   print('matched',len(results),flush=True)
 (OUT/(args.phase+'_population.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in results))
 population_elapsed=time.perf_counter()-started
 byid={r['case_id']:r for r in results};accepted=[r for r in results if r['selected_match']]
 review_accepted=[];known_good=known_bad=unknown=missed=0;outcomes=[]
 for row in labels:
  now=byid[row['case_id']];pid=now['selected_match']['product_id'] if now['selected_match'] else None
  issue=issues.get(row['case_id'],{});valid=issue.get('reference_product_ids',[])
  if row['review_label'] in ('CORRECT','ACCEPTABLE_SUBSTITUTE') and row['current_matcher_decision']=='accepted':
   original=before_byid[row['case_id']]['selected_match'];valid=[original['product_id']]
  good=bool(pid and pid in valid)
  bad=bool(pid and ((row['review_label']=='WRONG' and now['selected_match']['product_name']==row['selected_product'])))
  if pid:
   review_accepted.append(now);known_good+=good;known_bad+=bad;unknown+=not good and not bad
  elif valid:missed+=1
  outcomes.append({'case_id':row['case_id'],'query':row['ingredient_query'],'review_label':row['review_label'],'current_selected':now['selected_match'],'review_reference_hit':good,'known_original_error_persists':bad,'unreviewed_changed_selection':bool(pid and not good and not bad),'remains_abstained':not pid})
 # Independent-name-rule pair benchmark is a proxy, not a human answer key.
 benchmark=json.loads((ROOT/'Model/evaluation/ingredient_inventory_benchmark.json').read_text());pairs=[]
 labelled_products={p['id']:p for p in benchmark['products']};bytext={r['ingredient_query']:r for r in results};proxy_rows=[]
 for query in benchmark['queries']:
  row=bytext[query['text']];chosen=row['selected_match'];pid=chosen['product_id'] if chosen else None
  label='CORRECT' if pid in query['acceptable_ids'] else 'AMBIGUOUS' if pid and pid not in labelled_products else 'WRONG' if pid else 'SHOULD_HAVE_MATCHED' if query['acceptable_ids'] else 'CORRECT'
  product=labelled_products.get(pid,{})
  proxy_rows.append({'query':query['text'],'group':query['family'],'selected':bool(pid),'label':label,'positive':bool(query['acceptable_ids']),
   'wrong_family':bool(pid and product and product['family']!=query['family']),
   'wrong_subfamily':bool(pid and product and product['family']==query['family'] and product['identity']!=query['identity']),
   'prepared':bool(pid and product.get('identity')=='prepared'),
   'attribute_leakage':bool(pid and product and any(product.get('attributes',{}).get(k)!=v for k,v in query.get('attributes',{}).items())),
   'state_form_mistake':bool(pid and product and any(product.get('attributes',{}).get(k)!=v for k,v in query.get('attributes',{}).items() if k in ('state','form'))),
   'species_cut_mistake':bool(pid and product and query['family']=='meat' and product['identity']!=query['identity'])})
 def top1_metrics(xs):
  scored=[r for r in xs if r['label']!='AMBIGUOUS'];a=[r for r in scored if r['selected']];good=sum(r['label']=='CORRECT' for r in a);positive=sum(r['positive'] for r in scored);wrong=sum(r['label']=='WRONG' for r in a);fn=sum(r['label']=='SHOULD_HAVE_MATCHED' for r in scored)
  return {'count':len(xs),'scored':len(scored),'accepted_total':sum(r['selected'] for r in xs),'accepted_scored':len(a),'correct':good,'wrong':wrong,'ambiguous_or_unlabelled_product':len(xs)-len(scored),'precision_including_unlabelled_as_not_correct_proxy':fraction(good,sum(r['selected'] for r in xs)),'precision_proxy':fraction(good,len(a)),'recall_proxy':fraction(good,positive),'false_positive_rate_proxy':fraction(wrong,len(a)),'false_negative_rate_proxy':fraction(fn,positive),'wrong_family_count':sum(r['wrong_family'] for r in xs),'wrong_subfamily_count':sum(r['wrong_subfamily'] for r in xs),'prepared_food_fp':sum(r['prepared'] for r in xs),'wrong_species_cut':sum(r['species_cut_mistake'] for r in xs),'attribute_leakage':sum(r['attribute_leakage'] for r in xs),'state_form_mistakes':sum(r['state_form_mistake'] for r in xs)}
 top1_proxy={'all':top1_metrics(proxy_rows),**{g:top1_metrics([r for r in proxy_rows if r['group']==g]) for g in ('cheese','meat')}}

 for pair in benchmark['pairs']:
  feature=service.feature_by_id[pair['product_id']]
  decision=ontology.compatibility(ontology.describe(pair['ingredient']),ontology.describe(feature['original_product_name'],feature=feature,product=True))
  pairs.append({**pair,'predicted':decision.allowed})
 def pair_metrics(xs):
  tp=sum(r['expected'] and r['predicted'] for r in xs);fp=sum(not r['expected'] and r['predicted'] for r in xs);fn=sum(r['expected'] and not r['predicted'] for r in xs);tn=sum(not r['expected'] and not r['predicted'] for r in xs)
  return {'count':len(xs),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision_proxy':fraction(tp,tp+fp),'recall_proxy':fraction(tp,tp+fn),'accuracy_proxy':fraction(tp+tn,len(xs))}
 references=[r for r in audit['cases'] if r['review_label']=='SHOULD_HAVE_MATCHED'];hits=collections.Counter();traces=[]
 for reference in references:
  query,_=module.profile_from_query(reference['ingredient_query'],service.overrides);allowed=service.identity_catalog.candidate_ids(query.ontology)
  retrieval=service.retriever.retrieve_product_candidates(query.normalized_signature,limit=20,use_semantic=True,allowed_product_ids=allowed)
  candidates=[c.product_id for c in retrieval.candidates];expected=set(reference['reference_product_ids']);rank=next((i+1 for i,p in enumerate(candidates) if p in expected),None)
  for k in (5,10,20):hits[k]+=bool(rank and rank<=k)
  gates={p:list(ontology.compatibility(query.ontology,service.identity_catalog.identities[p]).reasons) for p in expected}
  stage='compatibility_rejected' if not expected & allowed else 'retrieval_miss' if not rank else 'selected_or_ranked'
  now=byid[reference['case_id']]
  if rank and not now['selected_match']:stage='margin_or_threshold_abstention'
  elif rank and now['selected_match']['product_id'] not in expected:stage='reference_lost_ranking_or_equivalent_unreviewed_alternative'
  traces.append({'case_id':reference['case_id'],'reference_product_ids':list(expected),'first_reference_rank':rank,'stage':stage,'gate_reasons':gates})
 lat=[]
 latency_sample=random.Random(20261008).sample(texts,100)
 # Prime the same query/model/index caches in both phases; only the matcher
 # result cache is cleared before each measured call.
 service.match_recipe_ingredients(latency_sample,limit=5,use_semantic=True)
 for text in latency_sample:
  service.cache._items.clear();start=time.perf_counter();service.match_recipe_ingredient(text,use_semantic=True);lat.append((time.perf_counter()-start)*1000)
 report={'population_wall_seconds':population_elapsed,'population_throughput_queries_per_second':len(results)/population_elapsed,'phase':args.phase,'latency_method':'100 fixed-seed queries; model/index and query embedding caches primed equally in both phases; matcher-result cache cleared before each single-query call','label_provenance':'assistant diagnostic review and independent-name-rule proxy, NOT independent human validation','population_count':len(results),'accepted':len(accepted),'rejected':len(results)-len(accepted),'no_match_rate':fraction(len(results)-len(accepted),len(results)),'confidence_distribution':dict(collections.Counter(r['confidence'] for r in results)),'query_family_distribution':dict(collections.Counter(r['ontology'].get('family') or 'unknown' for r in results)),'selected_family_distribution':dict(collections.Counter(r['selected_match']['ontology'].get('family') for r in accepted)),'review_anchored_proxy':{'known_good':known_good,'known_original_errors':known_bad,'unreviewed_changed_selections':unknown,'accepted':len(review_accepted),'precision_lower_bound_proxy':fraction(known_good,len(review_accepted)),'precision_upper_bound_proxy':fraction(known_good+unknown,len(review_accepted)),'reference_recall_proxy':fraction(known_good,sum((r['review_label'] in ('CORRECT','ACCEPTABLE_SUBSTITUTE') and r['current_matcher_decision']=='accepted') or r['review_label']=='SHOULD_HAVE_MATCHED' for r in labels)),'note':'Changed selections are unreviewed; bounds are reference agreement, not fresh manual precision.'},'top1_name_rule_proxy':top1_proxy,'pair_proxy':{'all':pair_metrics(pairs),**{group:pair_metrics([r for r in pairs if r['group']==group]) for group in ['cheese','meat']},'prepared':pair_metrics([r for r in pairs if r['kind']=='prepared_negative'])},'candidate_recall_proxy':{f'at_{k}':fraction(hits[k],len(references)) for k in (5,10,20)},'candidate_recall_reference_count':len(references),'candidate_recall_definition':'Recall over 52 assistant-suggested product references; includes seven unverified-state references. These are diagnostic proxies, not perfect gold.','candidate_failure_stages':dict(collections.Counter(r['stage'] for r in traces)),'latency':{'warm_uncached_median_ms':statistics.median(lat),'warm_uncached_p95_ms':sorted(lat)[94]},'material_margin_abstentions':sum('ambiguous_material_identity_margin' in r['reason_codes'] for r in results),'outcomes':outcomes,'candidate_traces':traces}
 (OUT/(args.phase+'_evaluation.json')).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['outcomes','candidate_traces','query_family_distribution']},indent=2),flush=True)

if __name__=='__main__':
 before_byid={r['case_id']:r for r in [json.loads(l) for l in (ROOT/'data/matcher_validation/population.jsonl').open()]}
 main()
