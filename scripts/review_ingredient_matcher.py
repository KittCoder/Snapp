#!/usr/bin/env python3
"""Real-inventory proxy evaluation, failure harvest and fixed-seed QA sampling.

Never turn unreviewed/ambiguous examples into asserted correct matches.
"""
import argparse,collections,importlib.util,json,math,random,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))


def load_matcher(phase):
 if phase=='before':
  spec=importlib.util.spec_from_file_location('matcher_before',ROOT/'data/matcher_audit/product_compatibility_before.py')
  module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
 import product_compatibility;return product_compatibility

def rate(num,den):return round(num/den,5) if den else None

def summary(rows):
 scored=[r for r in rows if r['classification']!='AMBIGUOUS']
 accepted=[r for r in scored if r['selected_product']]
 good=sum(r['classification']=='CORRECT' for r in accepted)
 actual=sum(r['valid_inventory_match_exists'] for r in scored)
 false_neg=sum(r['classification']=='SHOULD_HAVE_MATCHED' for r in scored)
 wrong=sum(r['classification']=='WRONG_PRODUCT' for r in scored)
 no_match=sum(not r['selected_product'] for r in rows)
 return {'count':len(rows),'scored':len(scored),'unreviewed_or_ambiguous':len(rows)-len(scored),
  'precision':rate(good,len(accepted)),'recall':rate(good,actual),'false_positive_rate':rate(wrong,len(accepted)),
  'false_negative_rate':rate(false_neg,actual),'no_match_rate':rate(no_match,len(rows)),
  'classifications':dict(collections.Counter(r['classification'] for r in rows))}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['before','after'],required=True)
 parser.add_argument('--benchmark',type=Path,default=ROOT/'Model/evaluation/ingredient_inventory_benchmark.json')
 args=parser.parse_args();gold=json.loads(args.benchmark.read_text());matcher=load_matcher(args.phase)
 from product_retrieval import lexical_score,Candidate
 service=matcher.ProductMatchService();features=service.feature_by_id
 labelled={p['id']:p for p in gold['products']}
 start=time.perf_counter();texts=[q['text'] for q in gold['queries']]
 results=service.match_recipe_ingredients(texts,limit=5,use_semantic=True)
 batch_seconds=time.perf_counter()-start
 rows=[]
 for q,result in zip(gold['queries'],results):
  chosen=result.selected_match;pid=chosen.product_id if chosen else None
  classification='CORRECT' if pid in q['acceptable_ids'] else 'AMBIGUOUS' if pid and pid not in labelled else 'WRONG_PRODUCT' if pid else 'SHOULD_HAVE_MATCHED' if q['acceptable_ids'] else 'CORRECT'
  rows.append({'ingredient':q['text'],'group':q['family'],'expected_ids':q['acceptable_ids'],
   'valid_inventory_match_exists':bool(q['acceptable_ids']),'selected_product':chosen.to_dict() if chosen else None,
   'top_alternatives':[c.to_dict() for c in result.compatible_alternatives[:3]],
   'rejected_candidates':[c.to_dict() for c in result.rejected_candidates[:3]],
   'match_type':getattr(result,'match_type','legacy_unspecified'), 'confidence':result.confidence,
   'classification':classification,'review_provenance':'independent name-rule proxy, NOT human review',
   'family_error':bool(pid and pid in labelled and labelled[pid]['family']!=q['family']),
   'prepared_error':bool(pid and pid in labelled and labelled[pid]['identity']=='prepared'),
   'ontology':getattr(result,'ontology',{}),'reason_codes':result.reason_codes})
 by_query={};by_product={};pairrows=[]
 for p in gold['pairs']:
  q=p['ingredient'];feature=features[p['product_id']]
  if q not in by_query:by_query[q]=matcher.profile_from_query(q,service.overrides)[0]
  if p['product_id'] not in by_product:by_product[p['product_id']]=matcher.profile_from_feature(feature)
  signals=matcher.compatibility_signals(by_query[q],by_product[p['product_id']])
  score,reasons,exact,alias=lexical_score(q,feature)
  candidate=Candidate(p['product_id'],p['product_name'],feature['normalized_name'],feature['record_status'],feature.get('canonical_name'),lexical_similarity=score,semantic_similarity=.95,exact_match=exact,alias_match=alias)
  ranked=matcher.score_candidate(candidate,feature,by_query[q],by_product[p['product_id']],signals,service.config)
  if args.phase=='after':
   from product_ontology import describe,compatibility
   decision=compatibility(describe(q),describe(feature['original_product_name'],feature=feature,product=True))
   predicted=decision.match_type in ('exact','equivalent')
  else:predicted=not matcher.has_hard_reject(signals) and ranked.final_score>=service.config.minimum_selection_score
  pairrows.append({**p,'predicted':predicted})
 def pairmetrics(xs):
  tp=sum(x['expected'] and x['predicted'] for x in xs);fp=sum(not x['expected'] and x['predicted'] for x in xs)
  fn=sum(x['expected'] and not x['predicted'] for x in xs);tn=sum(not x['expected'] and not x['predicted'] for x in xs)
  return {'count':len(xs),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':rate(tp,tp+fp),'recall':rate(tp,tp+fn),'accuracy':rate(tp+tn,len(xs)),'false_positive_rate':rate(fp,fp+tn)}
 # Warm, uncached identity measurements separate batch startup/embedding cost.
 import copy
 rng=random.Random(20261006);sample=rng.sample(texts,min(100,len(texts)));lat=[]
 for text in sample:
  service.cache._items.clear() if hasattr(service.cache,'_items') else None
  start=time.perf_counter();service.match_recipe_ingredient(text,use_semantic=True);lat.append((time.perf_counter()-start)*1000)
 rng=random.Random(20261006)
 pools={'exact_high':[r for r in rows if r['selected_product'] and r['confidence'] in ('exact','high')],
        'medium':[r for r in rows if r['selected_product'] and r['confidence']=='medium'],
        'rejected':[r for r in rows if not r['selected_product']],
        'hard_categories':[r for r in rows if r['group'] in ('cheese','meat','chicken_broth','beef_broth','vegetable_broth','milk','yogurt','tomato_paste','tomato_sauce','diced_tomato','crushed_tomato')]}
 samples={name:rng.sample(pool,min(len(pool),300 if name=='exact_high' else 200)) for name,pool in pools.items()}
 report={'phase':args.phase,'matcher_version':matcher.MATCHER_VERSION,'label_provenance':gold['label_provenance'],
  'inventory_sha256':gold['inventory_sha256'],'overall':summary(rows),
  'bucket_calibration':{b:summary([r for r in rows if r['confidence']==b]) for b in sorted({r['confidence'] for r in rows})},
  'pair_metrics':{'all':pairmetrics(pairrows),**{g:pairmetrics([r for r in pairrows if r['group']==g]) for g in ['cheese','meat']},'prepared':pairmetrics([r for r in pairrows if r['kind']=='prepared_negative'])},
  'food_family_error_rate':rate(sum(r['family_error'] for r in rows),sum(bool(r['selected_product']) for r in rows)),
  'prepared_food_false_positive_rate':rate(sum(r['prepared_error'] for r in rows),sum(bool(r['selected_product']) for r in rows)),
  'performance':{'warm_uncached_median_ms':round(statistics.median(lat),3),'warm_uncached_p95_ms':round(sorted(lat)[math.ceil(len(lat)*.95)-1],3),'batch_seconds':round(batch_seconds,3),'batch_ingredients_per_second':round(len(texts)/batch_seconds,2)},
  'qa_samples':{name:{'requested':300 if name=='exact_high' else 200,'available':len(pools[name]),'sampled':len(xs),'proxy_metrics':summary(xs),'human_review_status':'PENDING; proxy classifications are not independent human QA','rows':xs} for name,xs in samples.items()},
  'freeze_recommendation':'DO_NOT_FREEZE_MATCHER','rows':rows,'pair_rows':pairrows}
 output=ROOT/f'data/matcher_audit/{args.phase}_benchmark.json';output.write_text(json.dumps(report,indent=2,default=str)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('rows','pair_rows','qa_samples')},indent=2))
if __name__=='__main__':main()
