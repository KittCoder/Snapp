"""Read-only Render probe: python ../scripts/diagnose_store_catalog.py (from Model).

Uses SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, STORE_CATALOG_BACKEND, REDIS_URL.
No dotenv loading, writes, credentials, raw rows, or raw provider bodies in output.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Model'))
from catalog_diagnostics import log_catalog_error, safe_message
from supabase_store_catalog import DatabaseStoreRegistry, SupabaseGateway, FEATURE_VERSION


def feature_version_diagnostics(versions):
    """Report the exact registry compatibility value, never another manifest version."""
    active = []
    for version in versions:
        actual = version.get('feature_version')
        state = ('absent' if 'feature_version' not in version else
                 'null' if actual is None else
                 'matching' if actual == FEATURE_VERSION else 'mismatched')
        active.append({'store_id': safe_message(version['store_id']),
                       'feature_version': safe_message(actual) if actual is not None else None,
                       'state': state})
    return {'expected_feature_version': FEATURE_VERSION,
            'feature_version_source': 'store_inventory_versions.feature_version',
            'active_feature_versions': active,
            'feature_version_mismatch_count': sum(v['state'] != 'matching' for v in active)}


def main():
    print(json.dumps({'environment_present': {name: bool(os.getenv(name)) for name in (
        'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'STORE_CATALOG_BACKEND', 'REDIS_URL')}}))
    try:
        gateway = SupabaseGateway()
        stores = []
        while True:
            page = gateway.select('stores', {'select': 'id,metadata,verified,active',
                                  'order': 'id.asc', 'limit': 500, 'offset': len(stores)})
            stores.extend(page)
            if len(page) < 500:
                break
        print(json.dumps({'store_count': len(stores), 'verified_active_store_count': sum(
            bool(s['verified'] and s['active']) for s in stores)}))
        versions = gateway.select('store_inventory_versions', {
            'select': 'id,store_id,source_version,product_count,feature_version',
            'active': 'eq.true', 'order': 'store_id.asc', 'limit': 100})
        print(json.dumps({'active_inventory_version_count': len(versions),
                          'active_product_count': sum(v['product_count'] for v in versions)}))
        print(json.dumps(feature_version_diagnostics(versions)))
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'Model/store_catalog_manifest.json').read_text())
        known = next(s['id'] for s in manifest if s['retailer'] == 'ctown')
        version = next(v for v in versions if v['store_id'] == known)
        rows = gateway.select('store_products', {
            'select': 'feature_json,identity_json,source_json,source_position',
            'store_id': 'eq.' + known, 'inventory_version_id': 'eq.' + version['id'],
            'order': 'source_position.asc', 'limit': 1})
        if not rows:
            raise RuntimeError('Known C-Town active inventory has no product row')
        # Exercise exact candidate field/filter syntax even if this family has no rows.
        gateway.candidates(known, version['id'], 'family', ['cheese'], 1)
        print(json.dumps({'known_ctown_product_fetch': 'ok', 'candidate_filter': 'ok'}))
        registry = DatabaseStoreRegistry(gateway=gateway)
        print(json.dumps({'runtime_registry_store_count': len(registry.public()), 'result': 'ok'}))
        return 0
    except Exception as exc:
        log_catalog_error(exc, 'render_catalog_probe')
        print(json.dumps({'result': 'failed', 'exception_class': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
