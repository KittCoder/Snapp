"""Cached, bounded production dependency probe. No credentials in output."""
import os,time,threading,json
from urllib.request import Request,urlopen
from security_config import configuration_errors
_lock=threading.Lock()
_cached=(0,False)


def dependencies_ready():
    global _cached
    if configuration_errors():return False
    with _lock:
        if time.monotonic()-_cached[0] < 30:return _cached[1]
        try:
            from redis import Redis
            Redis.from_url(os.getenv('SNAPP_RATE_LIMIT_STORAGE_URI') or os.environ['REDIS_URL'],socket_connect_timeout=2,socket_timeout=2).ping()
            host=os.environ['TYPESENSE_HOST'];port=os.getenv('TYPESENSE_PORT','443')
            if any(c in host for c in '/@?#') or not port.isdigit():return False
            req=Request('https://'+host+':'+port+'/health',headers={'X-TYPESENSE-API-KEY':os.environ['TYPESENSE_API_KEY']})
            with urlopen(req,timeout=2) as response:ok=json.load(response).get('ok') is True
        except Exception:ok=False
        _cached=(time.monotonic(),ok)
        return ok
