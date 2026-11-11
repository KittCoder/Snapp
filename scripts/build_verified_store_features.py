"""Build source/version-pinned lexical features for VERIFIED C-Towns only. No scraping."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from store_catalogs import StoreRegistry

def run():
 registry=StoreRegistry();result=[]
 if registry.errors:raise RuntimeError('Verified inventory validation failed: '+str(registry.errors))
 for catalog in registry.stores.values():
  if catalog.metadata.retailer=='morton_williams':continue
  start=time.perf_counter();catalog.builder();result.append({'id':catalog.metadata.id,'inventory_version':catalog.metadata.inventory_version,'product_count':catalog.metadata.product_count,'seconds':time.perf_counter()-start});print(json.dumps(result[-1]),flush=True)
 target=ROOT/'data/store_scrapes/audit/multi_store_review/feature_build.json';target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':run()
