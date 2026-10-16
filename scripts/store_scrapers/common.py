"""Staging-only storage, conservative public HTTP, and shared normalization."""
from __future__ import annotations
import hashlib,json,math,re,sys,time,threading
from collections import Counter,defaultdict
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/store_scrapes'
sys.path.insert(0,str(ROOT/'Model'))
from ingredient_normalization import parse_package_size

def utcnow(): return datetime.now(timezone.utc).isoformat()
def write_json(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str)+'\n');tmp.replace(path)
def init_dirs(retailer):
    base=OUT/retailer
    for name in ('raw','normalized','audit','checkpoints'): (base/name).mkdir(parents=True,exist_ok=True)
    return base

def borough_for(address,zip_code=''):
    text=str(address or '').lower(); z=str(zip_code or '')[:5]
    if not z:
        m=re.search(r'\b(\d{5})\b',text);z=m.group(1) if m else ''
    if z.startswith('103'):return 'Staten Island'
    if z.startswith('104'):return 'Bronx'
    if z.startswith('112'):return 'Brooklyn'
    if z.startswith(('111','113','114','116')) or z in {'11004','11005'}:return 'Queens'
    if z.startswith(('100','101','102')):return 'Manhattan'
    for token,borough in [('staten island','Staten Island'),('bronx','Bronx'),('brooklyn','Brooklyn'),('queens','Queens'),('manhattan','Manhattan')]:
        if token in text:return borough
    return None

def parse_price(value):
    if isinstance(value,bool):return None
    if isinstance(value,(int,float)):
        return round(float(value),4) if math.isfinite(value) and value>0 else None
    text=str(value or '').strip().replace(',','')
    multi=re.fullmatch(r'(\d+)\s*(?:for|/)\s*\$?(\d+(?:\.\d{1,2})?)',text,re.I)
    if multi:return round(float(multi[2])/int(multi[1]),4) if int(multi[1])>0 and float(multi[2])>0 else None
    match=re.fullmatch(r'\$?\s*(\d+(?:\.\d{1,2})?)\s*(?:(?:/|per\s+)(?:lb|lbs|pound|oz|kg|each|ea))?',text,re.I)
    return parse_price(float(match[1])) if match else None

class Session:
    """GET-only public source session. No CAPTCHA/login/403 retries. Fresh-run cache is explicit."""
    def __init__(self,retailer,refresh=False):
        self.base=init_dirs(retailer);self.session=requests.Session()
        self.session.headers['User-Agent']='SNAPP-StagingResearch/1.0 (public grocery catalog audit)'
        self.refresh=refresh;self.lock=threading.Lock();self.last=0
    def get(self,url,params=None):
        prepared=requests.Request('GET',url,params=params).prepare().url
        key=hashlib.sha256(prepared.encode()).hexdigest();meta=self.base/'raw'/f'{key}.json';body=self.base/'raw'/f'{key}.body'
        if meta.exists() and body.exists():
            saved=json.loads(meta.read_text());deferred=False
            if saved.get('status_code') in (429,500,502,503,504):
                retry={str(k).lower():v for k,v in (saved.get('headers') or {}).items()}.get('retry-after')
                if retry:
                    try:
                        try:until=datetime.fromisoformat(saved['fetched_at']).timestamp()+float(retry)
                        except ValueError:until=parsedate_to_datetime(retry).timestamp()
                        deferred=time.time()<until
                    except (ValueError,TypeError,KeyError):pass
            if (not self.refresh and saved.get('status_code')==200) or deferred:
                r=requests.Response();r.status_code=saved['status_code'];r._content=body.read_bytes();r.url=saved['url'];r.headers.update(saved.get('headers',{}));r.encoding=saved.get('encoding');r.snapp_fetched_at=saved.get('fetched_at');return r
        for attempt in range(3):
            with self.lock:
                time.sleep(max(0,.4-(time.monotonic()-self.last)));self.last=time.monotonic()
            try:
                r=self.session.get(prepared,timeout=(10,35))
                body.write_bytes(r.content)
                event={'url':r.url,'requested_url':prepared,'status_code':r.status_code,'headers':dict(r.headers),'encoding':r.encoding,'fetched_at':utcnow(),'attempt':attempt+1}
                r.snapp_fetched_at=event['fetched_at']
                write_json(meta,event);self._event(event)
                if r.status_code not in (429,500,502,503,504) or attempt==2:return r
                delay=2**(attempt+1);retry=r.headers.get('Retry-After')
                if retry:
                    try:delay=float(retry)
                    except ValueError:
                        try:delay=max(0,(parsedate_to_datetime(retry)-datetime.now(timezone.utc)).total_seconds())
                        except (ValueError,TypeError):pass
                if delay>60: return r  # Leave a deferred retry; never shorten a server-requested wait.
                time.sleep(delay)
            except requests.RequestException as exc:
                self._event({'url':prepared,'error':str(exc),'attempt':attempt+1,'fetched_at':utcnow()})
                if attempt==2:raise
                time.sleep(2**(attempt+1))
    def _event(self,event):
        with self.lock:
            with (self.base/'checkpoints/requests.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
    def json(self,url,params=None):
        r=self.get(url,params);r.raise_for_status();return r.json()

def normalize_product(retailer,store,raw):
    size=str(raw.get('raw_size_text') or raw.get('size') or raw.get('unit') or '')
    quantity,unit,_,_=parse_package_size(size)
    if quantity is not None and parse_price(quantity) is None:quantity=None;unit=None
    text=str(raw.get('raw_price_text') or raw.get('price') or '')
    price=parse_price(raw.get('price'));regular=parse_price(raw.get('regular_price'));sale=parse_price(raw.get('sale_price'))
    # Explicit labels can safely split a combined source display; unlabeled
    # multiple amounts remain unknown rather than selecting the first number.
    labelled_sale=re.search(r'\bsale\s*:?\s*\$(\d+(?:\.\d{1,2})?)(?![\d.,])',text,re.I)
    labelled_regular=re.search(r'\bregular\s*:?\s*\$(\d+(?:\.\d{1,2})?)(?![\d.,])',text,re.I)
    if labelled_sale and labelled_regular:
        sale=sale or parse_price(labelled_sale[1]);regular=regular or parse_price(labelled_regular[1]);price=price or sale
    basis=raw.get('price_basis')
    if basis not in {'package','weight','each','unknown'}:
        basis='weight' if re.search(r'(?:/|per\s+)(?:lb|pound|oz|kg)\b',text,re.I) else 'each' if re.search(r'(?:/|per\s+)(?:each|ea)\b',text,re.I) else 'unknown'
    snap=raw.get('snap_eligible');evidence=raw.get('snap_evidence')
    if type(snap) is not bool or not evidence:snap=None;evidence=None
    metadata=dict(raw.get('source_metadata') or {})
    if evidence and 'snapEligible' in str(evidence) and not metadata.get('snap_semantics_verified'):
        metadata['raw_snap_eligible']=raw.get('snap_eligible')
        metadata['snap_confidence']='UNVERIFIED_SOURCE_SEMANTICS'
        snap=None  # Preserve the source boolean as evidence, not a verified claim.
    availability=raw.get('availability')
    if type(availability) is not bool:availability=None
    result={k:store.get(k) for k in ('store_id','store_name','borough','zip_code','service_area_id')}
    result.update(retailer=retailer,store_address=store.get('address'),source_product_id=str(raw.get('source_product_id') or raw.get('source_id') or raw.get('id') or ''),source_url=raw.get('source_url'),name=raw.get('name'),brand=raw.get('brand'),category=raw.get('category'),subcategory=raw.get('subcategory'),price=price,regular_price=regular,sale_price=sale,effective_current_price=sale or price,raw_price_text=text,price_basis=basis,raw_size_text=size,package_quantity=quantity,package_unit=unit,availability=availability,stock_status=raw.get('stock_status'),snap_eligible=snap,snap_evidence=evidence,image_url=raw.get('image_url'),scraped_at=raw.get('scraped_at') or utcnow(),source_metadata=metadata)
    return result

def coverage(rows):
    n=len(rows)
    return {key:round(100*sum(fn(r) for r in rows)/n,2) if n else None for key,fn in {
      'price_coverage':lambda r:parse_price(r.get('effective_current_price')) is not None,
      'package_coverage':lambda r:r.get('package_quantity') is not None and bool(r.get('package_unit')),
      'sale_coverage':lambda r:r.get('sale_price') is not None,
      'snap_coverage':lambda r:type(r.get('snap_eligible')) is bool,
      'availability_coverage':lambda r:type(r.get('availability')) is bool}.items()}

def validate_product(row):
    errors=[]
    for key in ('retailer','source_product_id','source_url','name','scraped_at'):
        if not row.get(key):errors.append('missing '+key)
    if not (row.get('store_id') or row.get('service_area_id')):errors.append('missing location context')
    for key in ('price','regular_price','sale_price','effective_current_price'):
        if row.get(key) is not None and parse_price(row[key]) is None:errors.append('invalid '+key)
    if row.get('snap_eligible') is not None and not row.get('snap_evidence'):errors.append('SNAP lacks evidence')
    for key in ('snap_eligible','availability'):
        if row.get(key) is not None and type(row[key]) is not bool:errors.append('invalid '+key)
    if row.get('price_basis') not in {'package','weight','each','unknown'}:errors.append('invalid price basis')
    return errors

def save_results(retailer,stores,products,discovery=None,limitations=None,started_at=None):
    base=init_dirs(retailer);write_json(base/'stores.json',stores);write_json(base/'audit/discovery.json',discovery or {})
    unique={};duplicates=Counter();invalid=[]
    contexts={str(s.get('store_id') or s.get('service_area_id')) for s in stores}
    for row in products:
        key=(row.get('retailer'),row.get('store_id') or row.get('service_area_id'),row.get('source_product_id'))
        errors=validate_product(row)
        if row.get('retailer')!=retailer:errors.append('retailer mismatch')
        if str(key[1]) not in contexts:errors.append('unknown store/service context')
        if errors:invalid.append({'identity':key,'errors':errors});continue
        if key in unique:duplicates[key[1]]+=1;continue
        unique[key]=row
    rows=list(unique.values());text=''.join(json.dumps(r,ensure_ascii=False,default=str)+'\n' for r in rows)
    for path in (base/'products.jsonl',base/'normalized/products.jsonl'):
        tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text);tmp.replace(path)
    bystore=defaultdict(list)
    for r in rows:bystore[r.get('store_id') or r.get('service_area_id')].append(r)
    audits=[]
    for s in stores:
        sid=s.get('store_id') or s.get('service_area_id');sr=bystore[sid]
        audits.append({'store_id':sid,'borough':s.get('borough'),'catalog_status':s.get('catalog_status'),'scrape_status':s.get('scrape_status') or ('PARTIAL' if sr else 'BLOCKED' if s.get('catalog_status')=='BLOCKED' else 'NO_PUBLIC_CATALOG' if s.get('catalog_status')=='NO_PUBLIC_CATALOG' else 'FAILED'),'raw_products':s.get('raw_products',len(sr)+duplicates[sid]),'normalized_products':len(sr),'unique_source_ids':len({r['source_product_id'] for r in sr}),'duplicate_ids':s.get('duplicate_ids',duplicates[sid]),**coverage(sr),'categories':sorted({str(r['category']) for r in sr if r.get('category')}),'failed_requests':s.get('failed_requests'),'scrape_duration_seconds':s.get('scrape_duration_seconds')})
    boroughs={b:{'discovered':sum(s.get('borough')==b for s in stores),'scraped':sum(a['borough']==b and a['normalized_products']>0 for a in audits),'blocked':sum(a['borough']==b and a['catalog_status']=='BLOCKED' for a in audits),'no_public_catalog':sum(a['borough']==b and a['catalog_status']=='NO_PUBLIC_CATALOG' for a in audits)} for b in ('Manhattan','Brooklyn','Queens','Bronx','Staten Island')}
    summary={'retailer':retailer,'generated_at':utcnow(),'started_at':started_at,'status':'YELLOW' if rows else 'RED','nyc_locations_discovered':len(stores),'locations_with_public_catalog':sum(s.get('catalog_status')=='AVAILABLE' for s in stores),'locations_scraped':sum(bool(v) for v in bystore.values()),'successful_locations':sum(a['scrape_status']=='SUCCESS' for a in audits),'blocked_locations':sum(s.get('catalog_status')=='BLOCKED' for s in stores),'no_public_catalog_locations':sum(s.get('catalog_status')=='NO_PUBLIC_CATALOG' for s in stores),'total_store_product_pairs':len(rows),'snap_true_products':sum(r.get('snap_eligible') is True for r in rows),'snap_false_products':sum(r.get('snap_eligible') is False for r in rows),'snap_unknown_products':sum(r.get('snap_eligible') is None for r in rows),'unique_underlying_product_ids':len({str((r.get('source_metadata') or {}).get('actual_product_id') or r['source_product_id']) for r in rows}),**coverage(rows),'borough_coverage':boroughs,'limitations':limitations or [],'discovery':discovery or {},'validation_errors':len(invalid),'duplicate_pairs_removed':sum(duplicates.values())}
    summary['failed_locations']=sum(a['scrape_status'] in {'BLOCKED','FAILED'} for a in audits)
    summary['partial_locations']=sum(a['scrape_status']=='PARTIAL' for a in audits)
    write_json(base/'summary.json',summary);write_json(base/'audit/stores.json',audits);write_json(base/'audit/validation_errors.json',invalid)
    events_path=base/'checkpoints/requests.jsonl'
    events=[json.loads(line) for line in events_path.read_text().splitlines() if line.strip()] if events_path.exists() else []
    failures=[e for e in events if e.get('error') or e.get('status_code',200)>=400]
    retry_queue=[e for e in failures if e.get('error') or e.get('status_code') in {429,500,502,503,504}]
    fetch_times=sorted(e['fetched_at'] for e in events if e.get('fetched_at') and e.get('status_code')==200)
    summary['source_fetch_window']={'first_public_fetch':fetch_times[0] if fetch_times else None,'last_public_fetch':fetch_times[-1] if fetch_times else None,'normalization_generated_at':summary['generated_at'],'successful_response_count':sum(e.get('status_code')==200 for e in events)}
    write_json(base/'summary.json',summary)
    write_json(base/'checkpoints/state.json',{'categories':sorted({str(r['category']) for r in rows if r.get('category')}),'pages_visited':sorted({e.get('url') for e in events if e.get('url')}),'hydrated_products':len(rows),'failed_requests':failures,'retry_queue':retry_queue,'stores':[s.get('store_id') or s.get('service_area_id') for s in stores],'product_ids_by_store':{str(k):[r['source_product_id'] for r in v] for k,v in bystore.items()},'saved_at':utcnow()})
    return summary
