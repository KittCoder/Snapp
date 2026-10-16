#!/usr/bin/env python3
"""Import only locally VERIFIED inventories using server credentials. Never scrapes."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Model'))
sys.path.insert(0,str(ROOT))
from store_catalogs import StoreRegistry, DEFAULT_FEATURES_PATH
from supabase_store_catalog import SupabaseGateway, FEATURE_VERSION, CatalogUnavailable
from product_ontology import describe
from scripts.store_scrapers.aggregate import feature_for


def version_id(metadata):
    return hashlib.sha256((metadata.id+':'+metadata.inventory_version+':'+FEATURE_VERSION).encode()).hexdigest()


def product_row(metadata, feature, source, position):
    identity = describe(feature.get('original_product_name') or feature.get('normalized_name'),feature=feature,product=True)
    pid = str(feature['product_id'])
    vid = version_id(metadata)
    result = {'id':hashlib.sha256((vid+':'+pid).encode()).hexdigest(), 'store_id':metadata.id,
              'inventory_version_id':vid,'source_product_id':pid,
              'name':feature.get('original_product_name') or feature.get('normalized_name') or source.get('name'),
              'normalized_name':feature.get('normalized_name') or '', 'family':identity.family,
              'subfamily':identity.subfamily,'semantic_head':identity.semantic_head,
              'feature_json':feature,'identity_json':asdict(identity),'source_json':source,'source_position':position}
    for key in ('brand','category','subcategory','price','regular_price','sale_price','effective_current_price',
                'price_basis','raw_size_text','package_quantity','package_unit','availability','snap_eligible','source_url'):
        result[key] = source.get(key)
    if metadata.retailer=='morton_williams':
        for key in ('brand','category','subcategory','price','regular_price','sale_price','effective_current_price',
                    'price_basis','raw_size_text','package_quantity','package_unit','availability','source_url'):
            if result[key] is None: result[key] = feature.get(key)
    return result


def merge_non_null(old, new):
    if not isinstance(new,dict): return old if new is None else new
    result = dict(old) if isinstance(old,dict) else {}
    for key,value in new.items():
        if value is not None: result[key] = merge_non_null(result.get(key),value)
    return result


def run(gateway=None, verify=False, dry_run=False):
    registry = StoreRegistry()
    if registry.errors or len(registry.stores)!=13:
        raise RuntimeError('Exactly 12 verified C-Towns and active Morton Williams required: '+str(registry.errors))
    gateway = gateway or (None if dry_run else SupabaseGateway())
    report = {'mode':'dry_run' if dry_run else 'verify' if verify else 'import',
              'feature_version':FEATURE_VERSION,'stores':[]}
    for catalog in registry.stores.values():
        meta = catalog.metadata
        vid = version_id(meta)
        stats = {'store_id':meta.id,'source_version':meta.inventory_version,'version_id':vid,
                 'expected':meta.product_count,'inserted':0,'updated':0,'skipped':0,'verified':False}
        if verify:
            versions = gateway.select('store_inventory_versions',{'select':'id,source_version,product_count,active,feature_version',
                                       'store_id':'eq.'+meta.id,'id':'eq.'+vid,'limit':2})
            # Count with bounded source-ID pages rather than downloading feature_json.
            count = 0
            while True:
                page = gateway.select('store_products',{'select':'source_product_id','store_id':'eq.'+meta.id,
                                      'inventory_version_id':'eq.'+vid,'order':'source_position.asc','offset':count,'limit':900})
                count += len(page)
                if len(page)<900: break
            stats['database_count'] = count
            stats['verified'] = (len(versions)==1 and versions[0]['active'] and count==meta.product_count
                                 and versions[0]['source_version']==meta.inventory_version
                                 and versions[0]['product_count']==count and versions[0]['feature_version']==FEATURE_VERSION)
            if not stats['verified']: raise RuntimeError('Inventory verification failed for '+meta.id)
        else:
            if not dry_run:
                gateway.upsert('stores',[{'id':meta.id,'retailer':meta.retailer,'name':meta.store_name,
                     'address':meta.address,'borough':meta.borough,'zip_code':meta.zip_code,
                     'verified':True,'metadata':meta.public()}])
                gateway.upsert('store_inventory_versions',[{'id':vid,'store_id':meta.id,'scraped_at':meta.verified_at,
                     'source_version':meta.inventory_version,'product_count':meta.product_count,'feature_version':FEATURE_VERSION}])
            if meta.retailer=='ctown':
                sources = json.loads(catalog.path.read_text())
                pairs = ((feature_for(source),source) for source in sources)
            else:
                features = json.loads(DEFAULT_FEATURES_PATH.read_text())['features']
                pairs = ((feature,{}) for feature in features)
            batch = []
            def flush(batch):
                if not batch: return
                if dry_run:
                    stats['skipped'] += len(batch)
                    return
                # Fetch exact bounded ID batches to report genuinely inserted/updated/skipped.
                existing = gateway.select('store_products',{'select':'*','store_id':'eq.'+meta.id,
                                  'inventory_version_id':'eq.'+vid,
                                  'id':'in.('+','.join(row['id'] for row in batch)+')','limit':len(batch)})
                old = {row['id']:row for row in existing}
                changed = []
                for row in batch:
                    before = old.get(row['id'])
                    merged = merge_non_null(before,row)
                    if before is not None and merged==before: stats['skipped']+=1
                    else:
                        stats['updated' if before else 'inserted']+=1
                        changed.append(merged)
                if changed: gateway.upsert('store_products',changed)
            for position,(feature,source) in enumerate(pairs):
                batch.append(product_row(meta,feature,source,position))
                if len(batch)==100: flush(batch);batch=[]
            flush(batch)
            if not dry_run:
                count = gateway.request('POST','rpc/activate_store_inventory',payload={'target_store':meta.id,'target_version':vid})
                if count!=meta.product_count: raise RuntimeError('Activation count mismatch')
                stats['database_count']=count;stats['verified']=True
        report['stores'].append(stats)
        print(json.dumps(stats),flush=True)
    report['total_expected'] = sum(s['expected'] for s in report['stores'])
    report['total_imported'] = sum(s.get('database_count',0) for s in report['stores'])
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--verify',action='store_true')
    group.add_argument('--dry-run',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    try:
        result=run(verify=args.verify,dry_run=args.dry_run)
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(result,indent=2)+'\n')
    except (CatalogUnavailable,RuntimeError,ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)
