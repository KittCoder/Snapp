"""Fixed English golden set; real parser/retrieval with deterministic wire fixtures.

No claims about live ranking are made by the fixture pass. --live uses configured
Typesense separately. Run capture BEFORE edits and compare AFTER edits.
"""
import argparse, hashlib, json, statistics, sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'Model'), str(ROOT/'Model/tests')]
import recipe_chat as chat
import recipe_search_typesense as search
from recipe_chat_language_cases import language_cases
from test_recipe_chat import Wire

def run(live=False, wrapper=False):
    records, latencies = [], []
    cases = language_cases()
    for case in cases:
        state = None
        wire = Wire()
        service = chat.configured_service() if live else chat.RecipeChatService()
        with patch.object(search, 'typesense_request', side_effect=wire) if not live else __import__('contextlib').nullcontext():
            for turn in case['turns']:
                if wrapper:
                    from recipe_chat_multilingual import handle_message
                    result=handle_message(service,turn['message'],state)
                else: result = service.handle_message(turn['message'], state)
                state = result['state']
                records.append({'case':case['name'], 'message':turn['message'],
                    'state':{k:v for k,v in state.items() if k in chat.RecipeChatState.__dataclass_fields__}, 'parsed':result['parsed_constraints'], 'intent':result['intent'],
                    'result_ids':[r['id'] for r in result['results']],
                    'selected_id':(result['selected_recipe'] or {}).get('id'),
                    'query':result['search_metadata']['typesense_query']})
                latencies.append(result['search_metadata']['latency_ms'])
    return {'mode':'live' if live else 'fixture', 'cases':len(cases), 'turns':len(records),
            'records':records, 'median_ms':statistics.median(latencies),
            'p95_ms':sorted(latencies)[int(len(latencies)*.95)]}

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture');parser.add_argument('--compare');parser.add_argument('--output');parser.add_argument('--live',action='store_true');parser.add_argument('--typesense-config');parser.add_argument('--wrapper',action='store_true');args=parser.parse_args()
    if args.typesense_config:
        import configparser, os
        config=configparser.ConfigParser();config.read(args.typesense_config)
        for section in config.values():
            if 'api-key' in section: os.environ['TYPESENSE_API_KEY']=section['api-key']
    result=run(args.live,args.wrapper)
    if args.compare:
        prior=json.loads(Path(args.compare).read_text()); changes=[]
        for i,(before,after) in enumerate(zip(prior['records'],result['records'])):
            if before != after: changes.append({'turn':i,'before':before,'after':after})
        if len(prior['records']) != len(result['records']): changes.append({'error':'turn count changed'})
        result['differences']=changes
        print(json.dumps({k:result[k] for k in ('mode','cases','turns','median_ms','p95_ms')}|{'differences':len(changes),'baseline_median_ms':prior['median_ms'],'baseline_p95_ms':prior['p95_ms']}))
    if args.capture or args.output: Path(args.capture or args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    if args.compare and result['differences']: sys.exit(1)
