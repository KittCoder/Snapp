"""Inventory failures remain observable without credential-bearing tracebacks."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask, jsonify, request
import store_comparison_api as api
from catalog_diagnostics import safe_message
from supabase_store_catalog import SupabaseGateway, CatalogUnavailable


class CatalogDiagnosticsTests(unittest.TestCase):
    def test_provider_error_is_allowlisted_and_redacts_constructor_and_env_credentials(self):
        gateway = SupabaseGateway('https://example.test', 'constructor-secret')
        response = Mock(status_code=400, content=b'error')
        response.json.return_value = {'code': '42703', 'message': 'missing column constructor-secret',
                                      'details': 'untrusted details'}
        with patch('requests.sessions.Session.request', return_value=response), patch('catalog_diagnostics.log_event') as log:
            with self.assertRaises(CatalogUnavailable) as caught:
                gateway.select('stores', {})
        self.assertEqual(caught.exception.catalog_http['postgrest_code'], '42703')
        self.assertNotIn('constructor-secret', str(log.call_args))
        self.assertNotIn('untrusted details', str(log.call_args))
        with patch.dict(os.environ, {'REDIS_URL': 'redis://user:password@host:6379',
                                    'SUPABASE_SERVICE_ROLE_KEY': 'env-secret'}):
            message = safe_message('env-secret redis://user:password@host:6379 Bearer abc.def.ghi')
        for secret in ('env-secret', 'password', 'abc.def.ghi'):
            self.assertNotIn(secret, message)

    def test_registry_key_error_returns_503_with_request_correlated_log_for_both_routes(self):
        app = Flask(__name__)
        @app.before_request
        def context():
            request.snapp_request_id = 'test-request'
        def error(message, status):
            return jsonify({'error': message}), status
        api.register_store_comparison(app, lambda: ({'recipes': [], 'store_ids': []}, None),
                                      error, lambda: False)
        with patch.object(api, 'engine', side_effect=KeyError('metadata')), patch('catalog_diagnostics.log_event') as log:
            client = app.test_client()
            self.assertEqual(client.get('/api/stores').status_code, 503)
            self.assertEqual(client.post('/api/shopping/compare', json={}).status_code, 503)
        self.assertEqual(log.call_args.kwargs['request_id'], 'test-request')
        self.assertEqual(log.call_args.kwargs['exception_class'], 'KeyError')


if __name__ == '__main__':
    unittest.main()
