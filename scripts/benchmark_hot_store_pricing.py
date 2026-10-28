"""Offline production-path replay on real catalogs; never models remote network latency.

Run with --hot for the optimized path, without it for remote-pool reference parity.
Use --output PATH to retain full results and CPU/wall stage timings for comparison.
"""
import sys,json,time,threading,gc,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Model'),str(ROOT)]
from store_catalogs import StoreRegistry
from supabase_store_catalog import DatabaseStoreCatalog,CandidateCache,SupabaseGateway,FEATURE_VERSION
from scripts.import_store_catalog import product_row
from store_comparison import BasketComparison
from catalog_timing import capture_timings,timed
from recipe_ingredient_adapter import canonical_recipe_ingredients
from product_compatibility import profile_from_query
from store_requirements import prepare_recipes

class LocalReplay(SupabaseGateway):
 def __init__(self,rows,metadata):
  self.rows=rows;self.meta=metadata;self.calls=[];self.query_count=0;self.lock=threading.Lock()
 def select(self,table,params):
  start=time.perf_counter()
  with self.lock:self.calls.append(table);self.query_count+=1
  if table=='store_inventory_versions':return [{'id':'version','source_version':self.meta.inventory_version,'product_count':self.meta.product_count,'feature_version':FEATURE_VERSION}]
  rows=self.rows
  for field in ['family','subfamily','semantic_head','normalized_name']:
   if field not in params:continue
   value=params[field]
   if value.startswith('in.'):rows=[r for r in rows if r[field] in json.loads('['+value[4:-1]+']')]
   else:
    import re
    terms=value.removeprefix('ilike.').strip('*').split('*');rows=[r for r in rows if re.search('.*'.join(re.escape(t) for t in terms),r[field],re.I)]
  offset=params.get('offset',0);limit=params.get('limit',900)
  # JSON round-trip models the actual gateway decode and isolates caller mutation.
  return json.loads(json.dumps(rows[offset:offset+limit]))

class Registry:
 def __init__(self,c):self.c=c
 def select(self,ids):return [self.c]
 def all_current(self,cs):return all(c.current() for c in cs)

def recipes():
 cached=json.loads((ROOT/'Model/recipe_chat_translations/es.json').read_text());titles=['Healthier Actually Delicious Turkey Burgers','Healthier Kung Pao Chicken']
 chosen=[]
 for title in titles:
  key,r=next((k,r) for k,r in cached.items() if title in r.get('name',{}));chosen.append({'id':key,'name':title,'ingredients':list(r['ingredients'])})
 for key in ['19780','28736','9741']:
  r=cached[key];chosen.append({'id':key,'name':next(iter(r['name'])),'ingredients':list(r['ingredients'])})
 return chosen

def run():
 r=recipes();file=StoreRegistry().stores['ctown:PS41_311'];file.builder();features=file._builder.match_service.retriever.features
 rows=[product_row(file.metadata,f,file.source_row(f['product_id']) or {},i) for i,f in enumerate(features)]
 gateway=LocalReplay(rows,file.metadata);cache=CandidateCache();cache.client=None
 c=DatabaseStoreCatalog(file.metadata,'version',gateway,cache)
 if '--hot' in sys.argv:
  from hot_store_catalog import HotStoreCatalogCache
  c.hot_cache=HotStoreCatalogCache()
 e=BasketComparison(Registry(c));prep,_=prepare_recipes(r)
 lines=[line for p in prep for line in p['ingredients']];unique={profile_from_query(l)[0].normalized_signature for l in lines}
 def price():
  if '--hot' in sys.argv:return e.compare_recipes(r,c.metadata.id,mw_semantic=False)
  return [dict(e.compare([recipe],[c.metadata.id])['stores'][0],recipe_id=recipe['id']) for recipe in r]
 output={'recipes':[(p['name'],len(p['ingredients'])) for p in r],'raw_ingredients':sum(len(p['ingredients']) for p in r),'purchase_lines':len(lines),'unique_normalized_names':len(unique),'unique_quantified_requirements':len(set(lines)),'rows':len(rows),'remote_network':False}
 if '--hot' in sys.argv:
  gateway.calls.clear();start=time.perf_counter();c.hot_cache.get(c)
  output['store_load_ms']=(time.perf_counter()-start)*1000
  output['load_queries']={t:gateway.calls.count(t) for t in set(gateway.calls)}
 gateway.calls.clear()
 with capture_timings() as trace:
  start=time.perf_counter();result=price();output['first_pricing_ms']=(time.perf_counter()-start)*1000
 output['cold_ms']=output.get('store_load_ms',0)+output['first_pricing_ms']
 output['before_or_cold_queries']={t:gateway.calls.count(t) for t in set(gateway.calls)};output['stages']=trace.summary();output['redis_lookup_attempts']=cache.hits+cache.misses
 output['candidate_lookups']=sum(stage['calls'] for stage in output['stages'] if stage['stage']=='matcher_scoring')
 output['matcher_batch_calls']=sum(stage['calls'] for stage in output['stages'] if stage['stage']=='matcher_total')
 output['basket_comparison_calls']=1 if '--hot' in sys.argv else len(r)
 # New recipe IDs bypass completed baskets, so warm means hot index rather than response-cache hit.
 r=[dict(p,id=p['id']+'-warm') for p in r];gateway.calls.clear()
 with capture_timings() as trace:
  start=time.perf_counter();warm=price();output['warm_ms']=(time.perf_counter()-start)*1000
 output['warm_queries']={t:gateway.calls.count(t) for t in set(gateway.calls)};output['warm_stages']=trace.summary()
 gateway.calls.clear();start=time.perf_counter();price();output['repeat_ms']=(time.perf_counter()-start)*1000
 def stable(p):return {k:v for k,v in p.items() if k not in ['latency_ms','recipe_id','basket_id','versions','cache_hit']}
 output['results']=[stable(p) for p in result]
 if '--output' in sys.argv:
  Path(sys.argv[sys.argv.index('--output')+1]).write_text(json.dumps(output,indent=2))
 print(json.dumps({k:v for k,v in output.items() if k!='results'},indent=2),flush=True)
 e.pool.shutdown()
 if getattr(c,'hot_cache',None):c.hot_cache.close()

def export_rows(sid, directory):
 catalog=StoreRegistry().stores[sid]
 with open(Path(directory)/(sid.replace(':','-')+'.jsonl'),'w') as output:
  for position,feature in enumerate(catalog.builder().match_service.retriever.features):
   output.write(json.dumps(product_row(catalog.metadata,feature,catalog.source_row(feature['product_id']) or {},position))+'\n')


def memory_run():
 """Fresh process RSS, with bulk pages streamed from disk rather than retained by a fake DB."""
 import subprocess,tempfile,weakref
 import model
 from store_catalogs import StoreMetadata
 from hot_store_catalog import HotStoreCatalogCache
 from supabase_store_catalog import FEATURE_VERSION
 ids=['ctown:PS41_311','ctown:U41_186','ctown:U41_131']
 manifest=json.loads((ROOT/'Model/store_catalog_manifest.json').read_text())
 def rss():
  gc.collect()
  return int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())]).strip())/1024
 with tempfile.TemporaryDirectory(prefix='snapp-hot-memory-') as directory:
  for sid in ids:
   subprocess.run([sys.executable,__file__,'--export-rows',sid,directory],check=True)
  class Pages:
   def select(self,table,params):
    sid=params['store_id'][3:]
    metadata=next(m for m in manifest if m['id']==sid)
    if table=='store_inventory_versions':
     return [{'id':'version','source_version':metadata['inventory_version'],'product_count':metadata['product_count'],'feature_version':FEATURE_VERSION}]
    offset,limit=params['offset'],params['limit']
    rows=[]
    with open(Path(directory)/(sid.replace(':','-')+'.jsonl')) as stream:
     for i,line in enumerate(stream):
      if i<offset:continue
      if i>=offset+limit:break
      rows.append(json.loads(line))
    return rows
  cache=HotStoreCatalogCache();gateway=Pages()
  print(json.dumps({'baseline_rss_mb':rss(),'max_hot_stores':cache.max_stores}),flush=True)
  first=None
  try:
   for sid in ids*3:
    metadata=StoreMetadata(**next(m for m in manifest if m['id']==sid))
    catalog=DatabaseStoreCatalog(metadata,'version',gateway,CandidateCache(),hot_cache=cache)
    start=time.perf_counter();index=cache.get(catalog)
    if first is None:first=weakref.ref(index)
    del index
    measured=rss()
    assert len(cache.values)<=2
    assert measured<1024, 'Unexpected RSS over 1 GiB in bounded index benchmark'
    print(json.dumps({'store_id':sid,'products':metadata.product_count,'load_ms':round((time.perf_counter()-start)*1000,2),'rss_mb':measured,'retained_stores':[k[0] for k in cache.values]}),flush=True)
   assert first() is None
   print(json.dumps({'evicted_index_freed':True}),flush=True)
  finally:cache.close()


if __name__=='__main__':
 if '--export-rows' in sys.argv:export_rows(sys.argv[2],sys.argv[3])
 elif '--memory' in sys.argv:memory_run()
 else:run()
