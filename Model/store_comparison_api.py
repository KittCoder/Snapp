"""Additive verified-store endpoints. Browser IDs never become filesystem paths."""
import threading
from flask import Blueprint,jsonify,request
from store_catalogs import CatalogError
from store_comparison import BasketComparison

_engine=None
_lock=threading.Lock()
def engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from supabase_store_catalog import configured_registry
                _engine=BasketComparison(configured_registry())
    return _engine

def register_store_comparison(app,validated_json_payload,json_error,semantic_ready):
    bp=Blueprint('store_comparison',__name__)
    @bp.route('/api/stores',methods=['GET','OPTIONS'])
    def stores():
        if request.method=='OPTIONS':return ('',204)
        try:return jsonify({'stores':engine().registry.public()})
        except (OSError,ValueError,RuntimeError):return json_error('Store catalog unavailable.',503)
    @bp.route('/api/shopping/compare',methods=['POST','OPTIONS'])
    def compare():
        if request.method=='OPTIONS':return ('',204)
        data,error=validated_json_payload()
        if error:return error
        if set(data)-{'recipes','store_ids'}:return json_error('Unsupported comparison field.',400)
        try:return jsonify(engine().compare(data.get('recipes'),data.get('store_ids'),mw_semantic=semantic_ready()))
        except CatalogError as exc:return json_error(str(exc),400)
        except (OSError,RuntimeError,ValueError,TypeError):return json_error('Store comparison unavailable.',503)
    app.register_blueprint(bp)
