"""Bounded worker-local store indexes; Supabase remains the versioned source of truth."""
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
import os
import threading
from catalog_timing import timing


class HotStoreCatalogCache:
    def __init__(self, max_stores=None):
        self.max_stores = max_stores if max_stores is not None else int(os.getenv('MAX_HOT_STORES', '2'))
        if not 1 <= self.max_stores <= 3:
            raise ValueError('MAX_HOT_STORES must be between 1 and 3')
        self.values = OrderedDict()
        self.pending = {}
        self.warm_jobs = {}
        self.lock = threading.RLock()
        self.load_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='store-warm')

    @staticmethod
    def key(catalog):
        from supabase_store_catalog import FEATURE_VERSION
        return (catalog.metadata.id, catalog.metadata.inventory_version, FEATURE_VERSION,
                catalog.version_id, catalog.override_hash)

    def is_hot(self, catalog):
        with self.lock:
            return self.key(catalog) in self.values

    def get(self, catalog):
        key = self.key(catalog)
        with self.lock:
            if key in self.values:
                self.values.move_to_end(key)
                return self.values[key]
            future = self.pending.get(key)
            owner = future is None
            if owner:
                future = self.pending[key] = Future()
        if not owner:
            return future.result()
        try:
            # Only one full inventory can be under construction at a time.
            with self.load_lock:
                with self.lock:
                    # Remove obsolete snapshots of this store and evict BEFORE loading.
                    for old in list(self.values):
                        if old[0] == key[0]:
                            del self.values[old]
                    while len(self.values) >= self.max_stores:
                        self.values.popitem(last=False)
                with timing('hot_store_load'):
                    value = self.load(catalog)
                with self.lock:
                    self.values[key] = value
                future.set_result(value)
            return value
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def warm(self, catalog):
        key = self.key(catalog)
        with self.lock:
            if key in self.values:
                self.values.move_to_end(key)
                return 'hot'
            if key not in self.warm_jobs:
                job = self.executor.submit(self.get, catalog)
                self.warm_jobs[key] = job
                def finished(future):
                    # Consume the failure; pricing can retry and logs keep provider details safe.
                    try:
                        future.result()
                    except Exception as exc:
                        from catalog_diagnostics import log_catalog_error
                        log_catalog_error(exc, 'store_background_warm')
                    with self.lock:
                        self.warm_jobs.pop(key, None)
                job.add_done_callback(finished)
            return 'warming'

    @staticmethod
    def load(catalog):
        from supabase_store_catalog import RequestCatalog, CatalogUnavailable
        if not catalog.current():
            raise CatalogUnavailable('Inventory changed before store load')
        rows = []
        seen = set()
        offset = 0
        while True:
            page = catalog.gateway.select('store_products', {
                'select': 'feature_json,identity_json,source_json,source_position',
                'store_id': 'eq.' + catalog.metadata.id,
                'inventory_version_id': 'eq.' + catalog.version_id,
                'order': 'source_position.asc', 'offset': offset, 'limit': 900})
            if not isinstance(page, list):
                raise CatalogUnavailable('Invalid bulk inventory page')
            for row in page:
                feature = row['feature_json']
                pid = feature.get('product_id')
                source = row['source_json']
                if not isinstance(pid, str) or not pid or pid in seen:
                    raise CatalogUnavailable('Duplicate or missing bulk product ID')
                if catalog.metadata.retailer == 'ctown' and (
                        source.get('retailer') != 'ctown' or source.get('store_id') != catalog.metadata.store_id):
                    raise CatalogUnavailable('Cross-store bulk inventory rejected')
                seen.add(pid)
                # Keep matching/package features and identities, never source row blobs.
                rows.append({'feature_json': feature, 'identity_json': row['identity_json'],
                             'source_position': row['source_position'],
                             'source_json': {k: source.get(k) for k in
                                             ('source_url', 'availability', 'retailer', 'store_id')}})
            offset += len(page)
            if offset > catalog.metadata.product_count:
                raise CatalogUnavailable('Bulk inventory count exceeds verified version')
            if len(page) < 900:
                break
        if len(rows) != catalog.metadata.product_count:
            raise CatalogUnavailable('Bulk inventory count differs from verified version')
        if not catalog.current():
            raise CatalogUnavailable('Inventory changed during store load')
        prepared = RequestCatalog(catalog.metadata, rows)
        # Build lookup maps once, before the store is advertised as hot.
        service = prepared.builder().match_service
        _ = service.feature_by_id
        _ = service.retriever.lexical_docs
        _ = service.identity_catalog
        return prepared

    def close(self):
        self.executor.shutdown(wait=True)
