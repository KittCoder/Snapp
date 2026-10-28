"""Additive verified-store endpoints. Browser IDs never become filesystem paths."""
import threading
from flask import Blueprint,jsonify,request
from store_catalogs import CatalogError
from store_comparison import BasketComparison
from catalog_diagnostics import catalog_operation, log_catalog_error
from catalog_timing import profile_catalog_request, timing

_engine=None
_lock=threading.Lock()
def engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                with catalog_operation("store_registry_initialization"):
                    from supabase_store_catalog import configured_registry
                    _engine=BasketComparison(configured_registry())
    return _engine

def register_store_comparison(app,validated_json_payload,json_error,semantic_ready):
    bp=Blueprint('store_comparison',__name__)
    @bp.route('/api/stores',methods=['GET','OPTIONS'])
    @profile_catalog_request
    def stores():
        if request.method=='OPTIONS':return ('',204)
        try:return jsonify({'stores':engine().registry.public()})
        except Exception as exc:
            log_catalog_error(exc, 'store_registry_public')
            return json_error('Store catalog unavailable.',503)
    @bp.route('/api/shopping/compare',methods=['POST','OPTIONS'])
    @profile_catalog_request
    def compare():
        if request.method=='OPTIONS':return ('',204)
        data,error=validated_json_payload()
        if error:return error
        if set(data)-{'recipes','store_ids','pantry_items'}:return json_error('Unsupported comparison field.',400)
        try:
            result = engine().compare(data.get('recipes'),data.get('store_ids'),mw_semantic=semantic_ready(),pantry_items=data.get('pantry_items'))
            with timing('response_serialization'):
                return jsonify(result)
        except CatalogError as exc:return json_error(str(exc),400)
        except Exception as exc:
            log_catalog_error(exc, 'store_comparison')
            return json_error('Store comparison unavailable.',503)
    @bp.route('/api/recipes/store-prices', methods=['POST','OPTIONS'])
    @profile_catalog_request
    def recipe_prices():
        if request.method == 'OPTIONS': return ('',204)
        data,error=validated_json_payload()
        if error: return error
        if set(data)-{'store_id','recipes','pantry_items'}: return json_error('Unsupported pricing field.',400)
        try:
            prices=engine().compare_recipes(data.get('recipes'),data.get('store_id'),
                mw_semantic=semantic_ready(),pantry_items=data.get('pantry_items'))
            return jsonify(store_id=data['store_id'],prices=prices)
        except CatalogError as exc: return json_error(str(exc),400)
        except Exception as exc:
            log_catalog_error(exc,'recipe_store_prices')
            return json_error('Recipe prices unavailable.',503)
    @bp.route('/api/stores/warm',methods=['POST','OPTIONS'])
    def warm_store():
        if request.method=='OPTIONS': return ('',204)
        data,error=validated_json_payload()
        if error: return error
        if set(data)-{'store_id'}: return json_error('Unsupported warm field.',400)
        try:
            pricing=engine()
            catalog=pricing.registry.select([data.get('store_id')])[0]
            pricing._current([catalog])
            cache=getattr(catalog,'hot_cache',None)
            state=cache.warm(catalog) if cache is not None else 'file-backed'
            return jsonify(store_id=catalog.metadata.id,inventory_version=catalog.metadata.inventory_version,status=state),202 if state=='warming' else 200
        except CatalogError as exc: return json_error(str(exc),400)
        except Exception as exc:
            log_catalog_error(exc,'store_warm')
            return json_error('Store warming unavailable.',503)
    app.register_blueprint(bp)
