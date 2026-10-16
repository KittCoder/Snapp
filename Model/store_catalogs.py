"""Verified, store-isolated inventory access. Never promotes or rewrites source data."""
from __future__ import annotations
import hashlib,json,math,re,sys,threading,tempfile
from dataclasses import dataclass,asdict
from pathlib import Path
from product_retrieval import ProductCandidateRetriever,DEFAULT_FEATURES_PATH
from product_compatibility import ProductMatchService,DEFAULT_OVERRIDES_PATH
from ingredient_normalization import parse_package_size
from product_ontology import FoodIdentity,IdentityCatalog
from basket_quantity import BasketBuilder,get_basket_builder

ROOT=Path(__file__).resolve().parents[1]
class CatalogError(ValueError):pass

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class MemoryRetriever(ProductCandidateRetriever):
    def __init__(self,features,store_id="isolated"):
        super().__init__(index_dir=Path(tempfile.gettempdir())/'snapp-ctown-no-vector-index'/store_id);self._features=features
    @property
    def features(self):return self._features
    def load_index(self):return False  # C-Town can never read the Morton Williams vector index.

@dataclass(frozen=True)
class StoreMetadata:
    id:str
    retailer:str
    store_id:str
    store_name:str
    address:str|None
    borough:str|None
    zip_code:str|None
    product_count:int
    inventory_version:str
    verified_at:str|None
    price_coverage:float|None=None
    package_coverage:float|None=None
    catalog_source:str|None=None
    def public(self):return asdict(self)

class StoreCatalog:
    def __init__(self,metadata,path=None,rows=None):
        self.metadata=metadata;self.path=path;self._rows=rows;self._builder=None;self.lock=threading.RLock();self.override_hash=digest(DEFAULT_OVERRIDES_PATH) if DEFAULT_OVERRIDES_PATH.exists() else None
    def builder(self):
        if self.metadata.retailer=='morton_williams':return get_basket_builder()
        if self._builder is not None:return self._builder
        if digest(self.path)!=self.metadata.inventory_version:raise CatalogError('Verified inventory changed; reload registry')
        rows=json.loads(self.path.read_text());ids={r['source_product_id'] for r in rows}
        if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
        from scripts.store_scrapers.aggregate import feature_for
        dependencies=['scripts/store_scrapers/aggregate.py','Model/ingredient_normalization.py','Model/product_ontology.py','Model/food_identity_rules.py','Model/structural_identity_policy.py']
        adapter_hash=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in dependencies)).hexdigest()
        cache_dir=self.path.parent.parent/'runtime_features';cache_path=cache_dir/(self.metadata.store_id+'.json');features=None;identities=None
        def checksum(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if cache_path.exists():
            try:
                payload=json.loads(cache_path.read_text());cached=payload['features']
                if (payload['inventory_version']==self.metadata.inventory_version and payload['adapter_version']==adapter_hash
                    and payload['store_id']==self.metadata.store_id and payload['features_sha256']==checksum(cached)
                    and {f['product_id'] for f in cached}==ids and len(cached)==len(rows)):
                    features=cached
                    saved=payload.get('identities')
                    if isinstance(saved,dict) and payload.get('identities_sha256')==checksum(saved) and set(saved)=={f['product_id'] for f in cached if f.get('eligible_for_retrieval')}:identities=saved
            except (OSError,ValueError,KeyError,TypeError):pass
        if features is None:features=[feature_for(row) for row in rows]
        service=ProductMatchService(retriever=MemoryRetriever(features,self.metadata.store_id))
        if identities is not None:
            def restore(data):
                values={k:v for k,v in data.items() if k in FoodIdentity.__dataclass_fields__}
                for key in ('absence_claims','dietary_requirements','purchase_variants','evidence'):values[key]=tuple(values.get(key) or ())
                values['alternatives']=tuple(restore(v) for v in values.get('alternatives') or ())
                return FoodIdentity(**values)
            catalog=IdentityCatalog([]);catalog.identities={pid:restore(v) for pid,v in identities.items()}
            for pid,identity in catalog.identities.items():
                if identity.family:catalog.by_family.setdefault(identity.family,set()).add(pid)
            service._identity_catalog=catalog
        else:
            # Serialize only deterministic data from the existing ontology, never pickle.
            identities={pid:asdict(identity) for pid,identity in service.identity_catalog.identities.items()}
            cache_dir.mkdir(parents=True,exist_ok=True)
            payload={'store_id':self.metadata.store_id,'inventory_version':self.metadata.inventory_version,'adapter_version':adapter_hash,'features_sha256':checksum(features),'features':features,'identities':identities,'identities_sha256':checksum(identities)}
            with tempfile.NamedTemporaryFile(mode='w',dir=cache_dir,prefix=self.metadata.store_id+'-',suffix='.tmp',delete=False) as temp:json.dump(payload,temp)
            Path(temp.name).replace(cache_path)
        self._rows={r['source_product_id']:{k:r.get(k) for k in ('source_product_id','retailer','store_id','store_address','name','brand','category','subcategory','source_url','availability','snap_eligible')} | {'source_metadata':{k:r.get('source_metadata',{}).get(k) for k in ('category_names','verified_label_text')}} for r in rows}
        self._builder=BasketBuilder(service)
        return self._builder
    def current(self):
        path=DEFAULT_FEATURES_PATH if self.metadata.retailer=='morton_williams' else self.path
        overrides=digest(DEFAULT_OVERRIDES_PATH) if DEFAULT_OVERRIDES_PATH.exists() else None
        return digest(path)==self.metadata.inventory_version and overrides==self.override_hash
    def source_row(self,pid):return (self._rows or {}).get(pid)

class StoreRegistry:
    def __init__(self,root=ROOT/'data/store_scrapes',mw=True):
        self.root=Path(root).resolve();self.stores={};self.errors=[];self.whitelist_version=None
        whitelist=self.root/'integration_ready_stores.json'
        try:entries=json.loads(whitelist.read_text());self.whitelist_version=digest(whitelist)
        except (OSError,ValueError):entries=[];self.errors.append('Verified store whitelist unavailable')
        locations=json.loads((self.root/'ctown/stores.json').read_text()) if (self.root/'ctown/stores.json').exists() else []
        byid={s['store_id']:s for s in locations}
        for entry in entries:
            if entry.get('retailer')!='ctown' or entry.get('status')!='VERIFIED':continue
            sid=entry.get('store_id');key='ctown:'+str(sid)
            try:
                if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',sid):raise CatalogError('Invalid whitelist store ID')
                if key in self.stores:raise CatalogError('Duplicate verified store')
                location=byid.get(sid)
                if not location or location['address']!=entry['address'] or location['borough']!=entry['borough']:raise CatalogError('Verified physical store identity mismatch')
                path=(self.root/'ctown/normalized'/(sid+'.json')).resolve()
                if not path.is_relative_to(self.root/'ctown/normalized'):raise CatalogError('Invalid catalog path')
                rows=json.loads(path.read_text());self.validate_rows(rows,entry,location)
                version=digest(path);metadata=StoreMetadata(key,'ctown',sid,entry['store_name'],entry['address'],entry['borough'],location['zip_code'],len(rows),version,max(r['scraped_at'] for r in rows),entry.get('price_coverage'),entry.get('package_coverage'),location.get('catalog_url'))
                self.stores[key]=StoreCatalog(metadata,path)
            except (OSError,ValueError,KeyError,TypeError) as exc:self.errors.append({'store_id':sid,'reason':str(exc)})
        if mw:
            # The active production artifact and existing singleton are retained exactly.
            try:
                features=json.loads(DEFAULT_FEATURES_PATH.read_text()).get('features') or []
                m=StoreMetadata('morton-williams','morton_williams','morton-williams','Morton Williams',None,None,None,len(features),digest(DEFAULT_FEATURES_PATH),None)
                self.stores[m.id]=StoreCatalog(m)
            except (OSError,ValueError):self.errors.append('Active Morton Williams inventory unavailable')
    @staticmethod
    def validate_rows(rows,entry,location):
        if not isinstance(rows,list) or not rows or len(rows)!=entry['product_count']:raise CatalogError('Verified catalog count mismatch')
        seen=set();priced=0;packaged=0
        for r in rows:
            if not isinstance(r,dict):raise CatalogError('Malformed product row')
            if r.get('retailer')!='ctown' or r.get('store_id')!=entry['store_id'] or r.get('store_address')!=location['address'] or r.get('zip_code')!=location['zip_code']:raise CatalogError('Cross-store row or physical context mismatch')
            pid=r.get('source_product_id')
            if not pid or pid in seen or not str(r.get('name') or '').strip() or not r.get('source_url') or not r.get('scraped_at'):raise CatalogError('Malformed/duplicate source product')
            seen.add(pid)
            for key in ('price','sale_price','regular_price','effective_current_price'):
                value=r.get(key)
                if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value<=0):raise CatalogError('Invalid product price')
            if r.get('price_basis') not in ('package','weight','each','unknown'):raise CatalogError('Invalid price basis')
            q=r.get('package_quantity');u=r.get('package_unit')
            if q is not None and (type(q) not in (int,float) or not math.isfinite(q) or q<=0 or not u):raise CatalogError('Invalid package metadata')
            if r.get('snap_eligible') is not None:raise CatalogError('Unverified product SNAP eligibility')
            parsed_q,parsed_u,*_=parse_package_size(r.get('raw_size_text') or '')
            if q is not None and (parsed_q is None or not math.isclose(q,parsed_q,rel_tol=1e-6) or u!=parsed_u):raise CatalogError('Package metadata no longer matches validated parser')
            priced+=r.get('effective_current_price') is not None;packaged+=q is not None and bool(u)
        if abs(100*priced/len(rows)-entry['price_coverage'])>.02 or abs(100*packaged/len(rows)-entry['package_coverage'])>.02:raise CatalogError('Verified price/package coverage changed')
    def select(self,ids):
        if self.whitelist_version and digest(self.root/'integration_ready_stores.json')!=self.whitelist_version:raise CatalogError('Verified whitelist changed; reload registry')
        if not isinstance(ids,list) or not 1<=len(ids)<=13 or any(not isinstance(i,str) or i not in self.stores for i in ids):raise CatalogError('Choose only available verified stores')
        return [self.stores[i] for i in dict.fromkeys(ids)]
    def public(self):
        if self.whitelist_version and digest(self.root/'integration_ready_stores.json')!=self.whitelist_version:raise CatalogError('Verified whitelist changed; reload registry')
        return [s.metadata.public() for s in self.stores.values() if s.current()]
