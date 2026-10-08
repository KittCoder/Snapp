import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recipe_search_typesense as s


def hit(i, title='Stew', ingredients=None):
    return {'document': {'id': str(i), 'title': title, 'ingredient_names': ingredients or ['beef', 'salt']}}


def response(hits, found=None):
    return {'results': [{'hits': hits, 'found': len(hits) if found is None else found, 'search_time_ms': 2}]}


class HybridTests(unittest.TestCase):
    def test_schema_local_only(self):
        field = next(f for f in s.typesense_collection_schema()['fields'] if f['name'] == 'embedding')
        self.assertEqual(field['type'], 'float[]')
        self.assertEqual(field['num_dim'], 384)
        self.assertEqual(field['embed']['model_config'], {'model_name': 'ts/all-MiniLM-L12-v2'})
        self.assertEqual(field['embed']['from'], s.KEYWORD_FIELDS.split(','))
        self.assertNotIn('instructions', json.dumps(field))

    def test_query_and_filters(self):
        with patch.object(s, 'typesense_request', return_value=response([])) as request:
            result = s.search_recipes('chicken dinner without cheese under 30 minutes', min_time=5, dietary=['vegetarian'], alpha=.7)
        params = request.call_args.kwargs['body']['searches'][0]
        self.assertEqual(params['query_by'], s.KEYWORD_FIELDS + ',embedding')
        self.assertIn('alpha:0.7', params['vector_query'])
        self.assertEqual(params['q'], 'dinner')
        self.assertEqual(params['filter_by'], s.build_typesense_filter(s.SearchState.from_value(result['state'])))
        self.assertEqual(result['state']['max_time'], 30)
        self.assertEqual(result['state']['min_time'], 5)
        self.assertEqual(result['state']['include_ingredients'], ['chicken'])
        self.assertEqual(result['state']['exclude_ingredients'], ['cheese'])
        self.assertIn('categories:=`vegetarian`', params['filter_by'])

    def test_cleanup_and_ingredient_phrases(self):
        for query, ingredient in [('chicken dinner','chicken'), ('beef stew','beef'), ('salmon recipe','salmon'), ('egg breakfast','egg'), ('pasta lunch','pasta'), ('lentils soup','lentils')]:
            cleaned, parsed = s.parse_natural_language_query(query)
            self.assertIn(ingredient, parsed['include_ingredients'])
            self.assertNotIn(ingredient, cleaned)
        self.assertEqual(s.parse_natural_language_query('warm winter meal with beef')[0], 'warm winter meal')
        for query in ['quick healthy winter dinner', 'light creamy meal', 'no bake dessert']:
            self.assertFalse(s.parse_natural_language_query(query)[1]['include_ingredients'])
        self.assertEqual(s.parse_natural_language_query('with rice and beans')[1]['include_ingredients'], ['rice', 'beans'])

    def test_dedup_ingredients_and_limit(self):
        hits = [hit(1), hit(2, 'STEW!', ['salt','beef','salt']), hit(3, ingredients=['chicken']), hit(4, 'Soup')]
        with patch.object(s, 'typesense_request', return_value=response(hits)):
            result = s.search_recipes('winter', limit=2)
        self.assertEqual([x['id'] for x in result['results']], ['1','3'])
        self.assertEqual(result['duplicates_removed'], 1)
        self.assertEqual([x['rank'] for x in result['results']], [1,2])

    def test_backfill_pages(self):
        pages = [response([hit(i) for i in range(50)], 51), response([hit(51, 'Soup')], 51)]
        with patch.object(s, 'typesense_request', side_effect=pages) as request:
            result = s.search_recipes('winter', limit=2)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(result['duplicates_removed'], 49)
        self.assertEqual(request.call_count, 2)

    def test_embedding_fallback_preserves_filters(self):
        params = []
        def request(*args, **kwargs):
            params.append(dict(kwargs['body']['searches'][0]))
            if len(params) == 1:
                return {'results': [{'error': 'embedding field unavailable'}]}
            return response([hit(1)])
        with patch.object(s, 'typesense_request', side_effect=request):
            result = s.search_recipes('winter with beef under 30 minutes')
        self.assertTrue(result['fallback'])
        self.assertEqual(result['mode'], 'keyword')
        self.assertEqual(params[0]['filter_by'], params[1]['filter_by'])
        self.assertNotIn('embedding', params[1]['query_by'])
        self.assertNotIn('vector_query', params[1])

    def test_unavailable_service_and_strict_benchmark(self):
        for error in [s.TypesenseUnavailable('offline'), s.EmbeddingUnavailable('embedding')]:
            with patch.object(s, 'typesense_request', side_effect=error) as request:
                with self.assertRaises(s.TypesenseUnavailable):
                    s.search_recipes('winter', allow_fallback=False)
            self.assertEqual(request.call_count, 1)

    def test_key_not_in_errors_repr_or_results(self):
        config = s.TypesenseConfig(api_key='secret-test-key')
        error = HTTPError('http://localhost', 400, 'bad', {}, io.BytesIO(b'secret-test-key'))
        with patch.object(s, 'urlopen', side_effect=error):
            with self.assertRaises(s.TypesenseUnavailable) as raised:
                s.typesense_request(config, 'GET', '/health')
        self.assertNotIn(config.api_key, str(raised.exception))
        self.assertNotIn(config.api_key, repr(config))
        with patch.object(s, 'typesense_request', return_value=response([])):
            self.assertNotIn(config.api_key, json.dumps(s.search_recipes('winter', config=config)))

    def test_import_adds_only_derived_filter_metadata(self):
        original = {'id': '1', 'title': 'Soup', 'ingredient_names': ['milk']}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'documents.jsonl'
            source = json.dumps(original) + '\n'
            path.write_text(source)
            with patch.object(s, 'typesense_request', return_value='{"success":true}') as request:
                result = s.import_documents(s.TypesenseConfig(), path)
            indexed = json.loads(request.call_args.kwargs['body'])
            self.assertEqual(indexed, {**original, 'has_named_dairy': True, 'ingredient_filter_tokens': ['milk']})
            self.assertEqual(path.read_text(), source)
            self.assertEqual(result['successes'], 1)
            self.assertNotIn('embedding', indexed)

    def test_punctuation_and_plural_filters(self):
        self.assertEqual(s.ingredient_filter_tokens(['tomato-basil sauce', 'tomatoes']), ['basil', 'sauce', 'tomato'])
        self.assertEqual(s.ingredient_filter('tomatoes', exclude=True), 'ingredient_filter_tokens:!=`tomato`')
        self.assertEqual(s.ingredient_filter('eggs'), 'ingredient_filter_tokens:=`egg`')

    def test_keyword_mode_and_empty_search(self):
        with patch.object(s, 'typesense_request', return_value=response([])) as request:
            result = s.search_recipes('winter', mode='keyword')
        params = request.call_args.kwargs['body']['searches'][0]
        self.assertEqual(params['query_by'], s.KEYWORD_FIELDS)
        self.assertNotIn('vector_query', params)
        self.assertEqual(result['results'], [])
        self.assertFalse(result['fallback'])

    def test_dairy_name_exclusions_preserve_plant_alternatives(self):
        names = s.dairy_ingredient_names()
        self.assertIn('milk', names)
        self.assertIn('cheddar cheese', names)
        self.assertNotIn('coconut milk', names)
        self.assertNotIn('peanut butter', names)
        cleaned, parsed = s.parse_natural_language_query('something creamy but dairy free')
        self.assertIn('creamy', cleaned)
        self.assertEqual(parsed['dietary'], ['dairy_free'])
        self.assertIn('has_named_dairy:=false', s.build_typesense_filter(s.SearchState(dietary=['dairy_free'])))

    def test_explicit_time_override_and_filter_only(self):
        with patch.object(s, 'typesense_request', return_value=response([])):
            result = s.search_recipes('with beef under 30 minutes', max_time=15)
        self.assertEqual(result['effective_query'], '*')
        self.assertEqual(result['state']['max_time'], 15)
        self.assertEqual(result['mode'], 'keyword')


if __name__ == '__main__':
    unittest.main()
