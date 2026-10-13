"""Fail-closed deployment preflight, without printing configuration values."""
import os
from urllib.parse import urlparse


def configuration_errors(env=None):
    e=env if env is not None else os.environ
    if e.get('SNAPP_ENV')!='production':return []
    errors=[]
    if e.get('FLASK_DEBUG','0').lower() not in {'0','false',''}:errors.append('FLASK_DEBUG must be disabled')
    origins=e.get('ALLOWED_ORIGINS',e.get('CORS_ORIGINS','')).split(',')
    if not origins or any(not v or urlparse(v).scheme!='https' or urlparse(v).path not in {'','/'} for v in origins):errors.append('Explicit HTTPS ALLOWED_ORIGINS required')
    if '*' in ','.join(origins):errors.append('Wildcard origins forbidden')
    if not e.get('SNAPP_ADMIN_TOKEN') or len(e.get('SNAPP_ADMIN_TOKEN',''))<32:errors.append('Strong SNAPP_ADMIN_TOKEN required')
    if not e.get('TYPESENSE_API_KEY'):errors.append('TYPESENSE_API_KEY required')
    if e.get('TYPESENSE_PROTOCOL')!='https' or not e.get('TYPESENSE_HOST'):errors.append('HTTPS TYPESENSE_HOST required')
    if urlparse(e.get('SUPABASE_URL','')).scheme!='https':errors.append('HTTPS SUPABASE_URL required')
    if not (e.get('SNAPP_RATE_LIMIT_STORAGE_URI') or e.get('REDIS_URL','')).startswith(('redis://','rediss://')):errors.append('Shared Redis rate-limit storage required')
    if e.get('SNAPP_DEPENDENCY_READINESS','1')!='1':errors.append('Production dependency readiness must be enabled')
    if e.get('SNAPP_RATE_LIMIT_ENABLED','1')!='1':errors.append('Production rate limits must be enabled')
    return errors


if __name__=='__main__':
    errors=configuration_errors()
    for error in errors:print(error)
    raise SystemExit(1 if errors else 0)
