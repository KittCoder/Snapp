"""Home sale candidates come exclusively from the selected verified inventory."""
import json
from collections import OrderedDict
from threading import Lock

_cache = OrderedDict()
_lock = Lock()


def store_sale_pool(catalog, build_pool, mw_pool):
    key = (catalog.metadata.id, catalog.metadata.inventory_version, getattr(catalog, 'version_id', None))
    with _lock:
        if key in _cache:
            return _cache[key]
    # The local MW artifact belongs only to its explicitly selected MW catalog.
    if catalog.metadata.retailer == 'morton_williams' and not hasattr(catalog, 'gateway'):
        pool = mw_pool()
    else:
        if hasattr(catalog, 'gateway'):
            rows = []
            while True:
                page = catalog.gateway.select('store_products', {
                    'select': 'source_json,feature_json', 'store_id': 'eq.' + catalog.metadata.id,
                    'inventory_version_id': 'eq.' + catalog.version_id,
                    'sale_price': 'not.is.null', 'order': 'source_position.asc',
                    'limit': 900, 'offset': len(rows),
                })
                rows.extend(page)
                if len(page) < 900:
                    break
            products = [r['source_json'] for r in rows]
        else:
            products = json.loads(catalog.path.read_text())
        converted = []
        for row in products:
            if row.get('availability') is False:
                continue
            sale = row.get('sale_price')
            if sale is None:
                continue
            converted.append({**row, 'id': row.get('source_product_id'),
                'price': sale, 'original_price': row.get('regular_price') or row.get('original_price'),
                'sale_price': sale, 'is_on_sale': True, 'unit': row.get('raw_size_text') or row.get('unit')})
        pool = build_pool({'products': converted}) if converted else []
    pool = [{**item, 'store_id': catalog.metadata.id} for item in pool]
    with _lock:
        _cache[key] = pool
        while len(_cache) > 40:
            _cache.popitem(last=False)
    return pool
