#!/usr/bin/env python3
"""Read-only remote recipe deployment gate; credentials never printed."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Model'))
from recipe_search_typesense import TypesenseConfig,typesense_request

def main():
    c=TypesenseConfig();collection=typesense_request(c,'GET',f'/collections/{c.collection}')
    fields={f['name'] for f in collection['fields']}
    required={'embedding','instructions','ingredients'}
    # Existing approved schema uses ingredients_text plus structured_ingredients.
    if 'ingredients' not in fields:required.remove('ingredients');required.add('ingredients_text')
    assert collection['num_documents']==28522,'Recipe count must equal28522'
    assert required<=fields,'Required schema fields absent'
    r=typesense_request(c,'GET',f'/collections/{c.collection}/documents/search',query={'q':'*','query_by':'title','per_page':5})
    docs=[x['document'] for x in r['hits']];assert docs,'Collection empty'
    assert all('instructions' in d and 'embedding' in d for d in docs),'Sample instruction/embedding absent'
    assert any(isinstance(d.get('ingredients'),list) or isinstance(d.get('structured_ingredients'),list) for d in docs),'Structured ingredients absent'
    print(json.dumps({'collection':c.collection,'num_documents':collection['num_documents'],'embedding':True,'instructions':True,'structured_ingredients':True,'sample_size':len(docs)}))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Recipe index verification failed: '+type(e).__name__,file=sys.stderr);raise SystemExit(1)
