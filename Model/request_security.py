"""Bounded HTTP edge checks. Public computations do not confer owner-data access."""
import math
import os
import re
import time
import uuid
from flask import jsonify, request
from flask_limiter import Limiter
from werkzeug.exceptions import HTTPException

PUBLIC_ENDPOINTS = {'store_comparison.stores', 'store_comparison.compare', 'store_comparison.recipe_prices', 'store_comparison.warm_store', 'index', 'health', 'ready', 'recipe_search', 'recipe_chat',
 'recipe_chat_detail', 'recipe_nutrition_preview', 'grocery_stores', 'trader_joes_store',
 'sale_ingredients', 'dishes', 'chat', 'static', 'dev_product_candidates', 'dev_product_match'}


def production():
    return os.getenv('SNAPP_ENV', '').lower() == 'production'


def bounded_json(value, depth=0, counter=None):
    counter = counter if counter is not None else [0]
    counter[0] += 1
    if depth > 12 or counter[0] > 4000:
        raise ValueError('Request structure is too large.')
    if isinstance(value, str):
        if len(value) > 4000 or '\x00' in value:
            raise ValueError('Text value is too long or invalid.')
    elif isinstance(value, list):
        if len(value) > 200:
            raise ValueError('Too many items in request.')
        for item in value: bounded_json(item, depth+1, counter)
    elif isinstance(value, dict):
        if len(value) > 100:
            raise ValueError('Too many fields in request.')
        for key, item in value.items():
            if len(key) > 100: raise ValueError('Invalid field name.')
            bounded_json(item, depth+1, counter)
    elif isinstance(value, (float,int)) and not isinstance(value,bool):
        if abs(value)>10**12 or (isinstance(value,float) and not math.isfinite(value)):
            raise ValueError('Number is invalid or out of range.')


def validate_fields(data):
    for key in ('message','query','meal_prompt','dietary_restrictions','sale_ingredient_id','recipe_id','locale'):
        if key in data and data[key] is not None and not isinstance(data[key],str):
            raise ValueError('Invalid text field.')
    for key in ('for_schedule','include_price_estimate','include_nutrition','include_sale_matches'):
        if key in data and not isinstance(data[key],bool):raise ValueError('Invalid boolean field.')
    for key in ('limit','household_size','max_time','min_time'):
        value=data.get(key)
        if value is not None:
            if isinstance(value,bool) or not isinstance(value,(int,float,str)):
                raise ValueError('Invalid numeric field.')
            try: number=float(value)
            except (ValueError,TypeError,OverflowError):raise ValueError('Invalid numeric field.')
            maximum={'limit':50,'household_size':20,'max_time':1440,'min_time':1440}[key]
            if not math.isfinite(number) or number < 0 or number > maximum or number != int(number):
                raise ValueError('Numeric field is out of range.')
    for key in ('include_ingredients','exclude_ingredients','categories','dietary'):
        if key in data and data[key] is not None:
            if not isinstance(data[key],list) or len(data[key])>50 or any(not isinstance(v,str) or len(v)>150 for v in data[key]):
                raise ValueError('Invalid filter list.')
    if 'pantry_items' in data and data['pantry_items'] is not None and not isinstance(data['pantry_items'],list):
        raise ValueError('Invalid pantry list.')
    for item in data.get('pantry_items') or []:
        if not isinstance(item,dict):raise ValueError('Invalid pantry item.')
        if item.get('name') is not None and not isinstance(item['name'],str):raise ValueError('Invalid pantry name.')
        if item.get('quantity') is not None and (isinstance(item['quantity'],bool) or not isinstance(item['quantity'],(str,int,float))):raise ValueError('Invalid pantry quantity.')
    if data.get('state') is not None and not isinstance(data['state'],dict):raise ValueError('Invalid state.')
    if data.get('locale') is not None and data['locale'] not in {'en','es','zh-CN','zh-TW','ru','bn','ht','ko','ar','fr','ur','pl'}:
        raise ValueError('Unsupported locale.')
    if request.endpoint == 'recipe_chat' and len(data.get('message') or '') > 300:
        raise ValueError('Message is too long.')
    if data.get('recipe_id') and not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',data['recipe_id']):
        raise ValueError('Invalid recipe ID.')


def install_security(app):
    app.config['MAX_CONTENT_LENGTH']=int(os.getenv('SNAPP_MAX_JSON_PAYLOAD_BYTES','524288'))
    app.config['RATELIMIT_ENABLED']=os.getenv('SNAPP_RATE_LIMIT_ENABLED','1' if production() else '0')=='1'
    limiter=Limiter(key_func=lambda:request.remote_addr or 'unknown',app=app,
        storage_uri=os.getenv('SNAPP_RATE_LIMIT_STORAGE_URI') or os.getenv('REDIS_URL','memory://'),
        default_limits=[os.getenv('SNAPP_RATE_LIMIT_DEFAULT','120 per minute')],
        headers_enabled=True,swallow_errors=False)
    exempt={'health','ready','index','static'}
    @limiter.request_filter
    def exempt_health():return request.method=='OPTIONS' or request.endpoint in exempt
    @app.before_request
    def protect_request():
        request.snapp_request_id=uuid.uuid4().hex[:16]
        request.snapp_started=time.perf_counter()
        if production() and (request.path.startswith('/dev/') or request.path=='/chat'):
            return jsonify(error='Endpoint unavailable.',request_id=request.snapp_request_id),404
        if request.method=='OPTIONS':return None
        if request.endpoint and request.endpoint not in PUBLIC_ENDPOINTS and not request.endpoint.endswith('_options'):
            if not request.path.startswith('/internal/'):
                return jsonify(error='Endpoint unavailable.',request_id=request.snapp_request_id),403
        if request.path.startswith('/internal/'):
            from review_workflow import require_admin
            if not require_admin(request.headers)[0]:
                return jsonify(error='Unauthorized.',request_id=request.snapp_request_id),401
        if request.method=='POST':
            data=request.get_json(silent=True)
            if not isinstance(data,dict):return jsonify(error='Request body must be a JSON object.',request_id=request.snapp_request_id),400
            try:bounded_json(data);validate_fields(data)
            except ValueError as exc:return jsonify(error=str(exc),request_id=request.snapp_request_id),400
    @app.after_request
    def response_security(response):
        # Existing endpoint-specific errors may contain provider exception text.
        if production() and response.status_code >= 400:
            body=response.get_json(silent=True)
            if isinstance(body,dict):
                body.pop('details',None)
                if response.status_code>=500:body={'error':'Service temporarily unavailable.'}
                body['request_id']=getattr(request,'snapp_request_id',uuid.uuid4().hex[:16])
                response.set_data(app.json.dumps(body));response.content_type='application/json'
        response.headers['X-Request-ID']=getattr(request,'snapp_request_id','')
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'"
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        if request.method!='GET' or request.path.startswith('/internal/') or request.headers.get('Authorization'):
            response.headers['Cache-Control']='no-store'
        if production():response.headers['Strict-Transport-Security']='max-age=31536000'
        return response
    @app.errorhandler(HTTPException)
    def http_error(exc):
        response=jsonify(error='Too many requests. Try again shortly.' if exc.code==429 else 'Request rejected.',request_id=getattr(request,'snapp_request_id',None))
        response.status_code=exc.code
        if exc.code==429:response.headers['Retry-After']='60'
        return response
    return limiter


def apply_route_limits(app,limiter):
    for rule in app.url_map.iter_rules():
        if 'POST' in rule.methods and not rule.rule.startswith('/internal/'):
            app.view_functions[rule.endpoint]=limiter.limit(os.getenv('SNAPP_RATE_LIMIT_COMPUTE','30 per minute'),override_defaults=False)(app.view_functions[rule.endpoint])
