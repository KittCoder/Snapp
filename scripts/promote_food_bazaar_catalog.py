"""Prepare audited Food Bazaar catalogs for the existing per-location registry."""
import argparse,gzip,hashlib,json,sys,shutil
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Model'),str(ROOT)]
from scripts.store_scrapers.common import write_json
from store_catalogs import StoreRegistry,StoreMetadata,digest


def atomic_copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.promotion.tmp')
    shutil.copyfile(source,temporary);temporary.replace(target)


def run(source):
    root=ROOT/'data/store_scrapes';target=root/'food_bazaar'
    report=json.loads((source/'audit/finished_inventory.json').read_text())
    if not report.get('passed') or not report.get('all_accessible_catalogs_complete') or digest(source/'products.jsonl')!=report['products_sha256']:
        raise ValueError('A complete hash-verified source audit is required')
    locations=json.loads((source/'stores.json').read_text());entries=[];metadata=[];coordinates={}
    for location in locations:
        if not location.get('catalog_export_complete'):continue
        sid=str(location['store_id']);job=source/'store_jobs'/location['directory_id']
        audit=json.loads((job/'audit/output_validation.json').read_text());marker=json.loads((job/'audit/catalog_complete.json').read_text())
        if not audit['passed'] or marker.get('variant_coverage_version')!=1 or digest(job/'products.jsonl')!=marker['products_sha256'] or audit['products_sha256']!=marker['products_sha256']:
            raise ValueError('Store audit/hash mismatch: '+sid)
        rows=[json.loads(line) for line in (job/'products.jsonl').read_text().splitlines() if line.strip()]
        if len(rows)!=marker['declared_product_ids']:raise ValueError('Store coverage mismatch')
        path=target/'normalized'/(sid+'.json');write_json(path,rows)
        entry={k:location[k] for k in ('store_id','store_name','address','borough')}
        entry.update(retailer='food_bazaar',status='VERIFIED',product_count=len(rows),inventory_version=digest(path),
                     price_coverage=100*sum(r.get('effective_current_price') is not None for r in rows)/len(rows),
                     package_coverage=100*sum(r.get('package_quantity') is not None and bool(r.get('package_unit')) for r in rows)/len(rows))
        StoreRegistry.validate_rows(rows,entry,location)
        entries.append(entry)
        m=StoreMetadata('food_bazaar:'+sid,'food_bazaar',sid,location['store_name'],location['address'],location['borough'],location['zip_code'],len(rows),entry['inventory_version'],max(r['scraped_at'] for r in rows),entry['price_coverage'],entry['package_coverage'],location['source_url'])
        metadata.append(asdict(m))
        raw=json.loads(gzip.decompress((source/'raw'/(sid+'.json.gz')).read_bytes()))
        point=next(o['coordinates'] for o in raw['locations'] if str(o['id'])==sid)
        lat,lon=point['latitude'],point['longitude']
        if not 40.4<lat<41 or not -74.3<lon<-73.6:raise ValueError('Source coordinates outside NYC')
        coordinates[m.id]=[lat,lon]
    if len(entries)!=report['verified_catalogs'] or sum(e['product_count'] for e in entries)!=report['store_product_records']:
        raise ValueError('Promotion totals differ from audit')
    # Publish the same audited snapshot to the canonical staging paths too.
    previous=target/'audit/prior_canonical_products.jsonl'
    if (target/'products.jsonl').exists() and not previous.exists():atomic_copy(target/'products.jsonl',previous)
    for relative in ['products.jsonl','normalized/products.jsonl','summary.json','audit/finished_inventory.json','audit/output_validation.json']:
        atomic_copy(source/relative,target/relative)
    for entry in entries:
        sid=entry['store_id'];atomic_copy(source/'raw'/(sid+'.json.gz'),target/'raw'/(sid+'.json.gz'))
    write_json(target/'stores.json',locations)
    whitelist=root/'integration_ready_stores.json';existing=json.loads(whitelist.read_text())
    unavailable=[{k:location.get(k) for k in ('store_id','store_name','address','borough','zip_code','failure_reason')} | {'retailer':'food_bazaar','status':'LOCATION_NOT_EXPOSED','product_count':0} for location in locations if not location.get('catalog_export_complete')]
    write_json(whitelist,[e for e in existing if e.get('retailer')!='food_bazaar']+entries+unavailable)
    manifest=ROOT/'Model/store_catalog_manifest.json';existing=json.loads(manifest.read_text())
    write_json(manifest,[e for e in existing if e['retailer']!='food_bazaar']+metadata)
    write_json(ROOT/'Model/food_bazaar_store_coordinates.json',coordinates)
    print(json.dumps({'verified_locations':len(entries),'products':sum(e['product_count'] for e in entries)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);run(parser.parse_args().source)
