import os,sys,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask,jsonify
import model
from request_security import install_security,apply_route_limits
from security_config import configuration_errors


class SecurityTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'SNAPP_DISABLE_MATCHER_WARMUP':'1'});self.env.start();self.client=model.app.test_client()
 def tearDown(self):self.env.stop()
 def test_public_health(self):self.assertEqual(self.client.get('/health').status_code,200)
 def test_private_rejects_fake_identity_and_auth(self):
  for headers in [{},{'Authorization':'Bearer fake'},{'Authorization':'Basic invalid'},{'X-SNAPP-Admin-Token':'expired'}]:
   with self.subTest(headers=list(headers)):
    self.assertEqual(self.client.get('/internal/metrics?user_id=other',headers=headers).status_code,401)
 def test_admin_authorization(self):
  with patch.dict(os.environ,{'SNAPP_ADMIN_TOKEN':'x'*40}):
   self.assertEqual(self.client.get('/internal/metrics',headers={'X-SNAPP-Admin-Token':'x'*40}).status_code,200)
 def test_production_dev_legacy_disabled(self):
  with patch.dict(os.environ,{'SNAPP_ENV':'production'}):
   for path in ['/dev/product-match','/dev/product-candidates']:
    self.assertEqual(self.client.get(path).status_code,404)
   self.assertEqual(self.client.post('/chat',json={'message':'hi'}).status_code,404)
 def test_hostile_inputs(self):
  cases=[('/api/recipes/chat',{'message':'a'*301}),('/api/recipes/chat',{'message':{}}),('/api/recipes/chat',{'message':'hi','pantry_items':['a']*201}),('/api/recipes/detail',{'recipe_id':'../../etc/passwd'}),('/api/recipes/detail',{'recipe_id':'1','locale':'evil'}),('/api/recipes/search',{'query':'x','limit':float('nan')}),('/api/recipes/search',{'query':'x','include_ingredients':{'filter_by':'id:*'}}),('/dishes',{'meal_prompt':{}}),('/api/recipes/search',{'query':'rice','limit':10**1000}),('/api/recipes/chat',{'message':'hi','pantry_items':[{'name':{},'quantity':'1'}]})]
  for path,body in cases:
   with self.subTest(path=path,body=list(body)):
    self.assertEqual(self.client.post(path,json=body).status_code,400)
 def test_body_cap(self):
  self.assertEqual(self.client.post('/api/recipes/chat',data='x'*600000,content_type='application/json').status_code,413)
 def test_headers_and_request_id(self):
  r=self.client.get('/health',headers={'X-Request-ID':'injected-value'});self.assertNotEqual(r.headers['X-Request-ID'],'injected-value');self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
  self.assertNotIn('Access-Control-Allow-Origin',self.client.get('/health',headers={'Origin':'https://snapp-attacker.vercel.app'}).headers)
  self.assertEqual(self.client.get('/health',headers={'Origin':'https://snapp-1d5j.vercel.app'}).headers['Access-Control-Allow-Origin'],'https://snapp-1d5j.vercel.app')
 def test_http_codes_preserved(self):
  self.assertEqual(self.client.get('/does-not-exist').status_code,404)
  self.assertEqual(self.client.get('/api/recipes/chat').status_code,405)
 def test_production_error_redaction(self):
  with patch.dict(os.environ,{'SNAPP_ENV':'production'}),patch.object(model,'find_grocery_stores',side_effect=RuntimeError('secret database password')):
   r=self.client.get('/grocery-stores?zip=10024');self.assertEqual(r.status_code,503);self.assertNotIn('password',r.get_data(as_text=True));self.assertIn('request_id',r.json)
 def test_deployment_fail_closed(self):
  self.assertTrue(configuration_errors({'SNAPP_ENV':'production'}))
 def test_rate_limits_and_ip_isolation(self):
  with patch.dict(os.environ,{'SNAPP_ENV':'development','SNAPP_RATE_LIMIT_ENABLED':'1','SNAPP_RATE_LIMIT_DEFAULT':'100 per minute','SNAPP_RATE_LIMIT_COMPUTE':'2 per minute'}):
   app=Flask('rate-test');limiter=install_security(app)
   @app.post('/api/recipes/search',endpoint='recipe_search')
   def handler():return jsonify(ok=True)
   apply_route_limits(app,limiter);client=app.test_client()
   self.assertEqual(client.post('/api/recipes/search',json={}).status_code,200)
   self.assertEqual(client.post('/api/recipes/search',json={}).status_code,200)
   r=client.post('/api/recipes/search',json={});self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)
   self.assertEqual(client.post('/api/recipes/search',json={},environ_overrides={'REMOTE_ADDR':'192.0.2.5'}).status_code,200)
 def test_logging_redaction(self):
  from ops_metrics import log_event,logger
  with patch.object(logger,'log') as log:
   log_event('test',Authorization='Bearer stolen',nested={'access_token':'stolen','safe':'line\nbreak'})
   value=str(log.call_args);self.assertNotIn('stolen',value);self.assertIn('line break',value)

if __name__=='__main__':unittest.main()

class DependencyBoundaryTests(unittest.TestCase):
 def test_readiness_rejects_missing_production_config(self):
  from security_readiness import dependencies_ready
  with patch.dict(os.environ,{'SNAPP_ENV':'production','SNAPP_ADMIN_TOKEN':''}):self.assertFalse(dependencies_ready())
 def test_filter_quoting_cannot_escape_literal(self):
  from recipe_search_typesense import quote_filter_value
  result=quote_filter_value('rice\\` || id:*')
  self.assertEqual(result.count('`'),2);self.assertNotIn('\\',result)
