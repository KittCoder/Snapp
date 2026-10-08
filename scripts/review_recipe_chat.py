#!/usr/bin/env python3
"""Read-only live review of the local recipe chat service. Never logs credentials."""
from __future__ import annotations

import argparse
import hashlib
from copy import deepcopy
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Model'))
from recipe_chat import configured_service
from recipe_chat_language_cases import language_cases
from recipe_search_typesense import typesense_request

CONVERSATIONS = {
    'A_chicken_to_beef': ['I want chicken for dinner', 'under 30 minutes', 'no cheese', 'actually beef instead'],
    'B_warm_winter': ['I want a warm winter meal', 'with beef', 'something quicker'],
    'C_breakfast_selection': ['breakfast with eggs', 'show me the second one', 'does it use milk?', 'How long does it take?', 'What ingredients are in it?', 'How do I make it?', 'How many servings?'],
    'D_creamy_pasta': ['I want pasta', 'no tomato', 'something creamy'],
    'E_vegetarian': ['something spicy with rice', 'make it vegetarian'],
    'F_clear_time': ['beef dinner', 'under 30 minutes', 'forget the time limit'],
    'G_missing_reference': ['show me number 3'],
    'comparison': ['warm dinner with chicken', 'Which is fastest?', 'Which one has fewer ingredients?', 'Compare the first two.', 'Which is healthiest?'],
    'replacement': ['chicken with rice', 'no cheese', 'actually beef instead', 'replace rice with pasta'],
    'constraint_removal': ['pasta dinner without tomato under 30 minutes', 'remove no tomato', 'forget the time limit', 'remove category'],
    'unavailable_facts': ['cheapest dinner', 'the first one', 'How many servings?', 'Is it vegetarian?'],
    'new_search': ['chicken under 30 minutes', 'the last one', 'new search for breakfast with eggs', 'the second one'],
}


def latency_summary(values):
    if not values:
        return None
    ordered = sorted(values)
    return {'samples': len(values), 'median_ms': round(statistics.median(values), 2),
            'p95_ms': round(ordered[max(0, math.ceil(len(values) * .95) - 1)], 2)}


def run_review(service, language_benchmark=False):
    report = {'status': 'complete', 'model_configured': service.model is not None,
              'conversations': [], 'latency_note': 'Single sequential local run; includes first-turn costs. Document lookups count toward Typesense wall time.'}
    try:
        collection = typesense_request(service.config, 'GET', '/collections/' + service.config.collection)
        report['indexed_documents'] = collection.get('num_documents')
        embedding = next((f for f in collection.get('fields', []) if f.get('name') == 'embedding'), {})
        report['embedding'] = {'dimensions': embedding.get('num_dim'),
                               'model': embedding.get('embed', {}).get('model_config', {}).get('model_name')}
    except Exception:
        report['index_inspection'] = 'Unavailable; verify local Typesense connection and environment configuration.'
    cases = language_cases() if language_benchmark else [
        {'name': name, 'turns': [{'message': message, 'expect': {}} for message in messages]}
        for name, messages in CONVERSATIONS.items()]
    report['benchmark'] = 'conversational_language' if language_benchmark else 'original'
    report['scenario_count'] = len(cases)
    for case in cases:
        name = case['name']
        state, turns = None, []
        for spec in case['turns']:
            message = spec['message']
            before = deepcopy(state)
            started = time.perf_counter()
            try:
                result = service.handle_message(message, state)
            except Exception:
                report['status'] = 'incomplete'
                turns.append({'user_message': message, 'state_before': before, 'state_after': before,
                              'error': 'Chat request failed. Verify local Typesense configuration.',
                              'total_backend_latency_ms': round((time.perf_counter() - started) * 1000, 2)})
                break
            state = result['state']
            turns.append({'user_message': message, 'intent': result['intent'], 'state_before': before,
                          'state_after': deepcopy(state), 'parsed_constraints': result['parsed_constraints'],
                          'cleaned_semantic_query': result['parsed_constraints'].get('cleaned_semantic_query', ''),
                          'expected_interpretation': spec['expect'],
                          'typesense_query': result['search_metadata']['typesense_query'],
                          'returned_recipes': [{'id': r['id'], 'title': r.get('title')} for r in result['results']],
                          'selected_recipe': result['selected_recipe'], 'assistant_response': result['message'],
                          'typesense_latency_ms': result['search_metadata']['typesense_latency_ms'],
                          'total_backend_latency_ms': result['search_metadata']['latency_ms'],
                          'search_metadata': result['search_metadata']})
        report['conversations'].append({'name': name, 'turns': turns})
    all_turns = [t for c in report['conversations'] for t in c['turns'] if 'intent' in t]
    searches = [t for t in all_turns if t['typesense_query'] is not None]
    report['turn_count'] = len(all_turns)
    report['search_count'] = len(searches)
    report['latency'] = {
        'all_turns_backend': latency_summary([t['total_backend_latency_ms'] for t in all_turns]),
        'search_turns_backend': latency_summary([t['total_backend_latency_ms'] for t in searches]),
        'search_turns_typesense': latency_summary([t['typesense_latency_ms'] for t in searches]),
    }
    return report


def turn_fingerprint(turn):
    # Ratings refer to a reviewed trace, never blindly to a phrase after code or
    # index changes. Latency is excluded because it varies on every execution.
    fields = ('user_message', 'intent', 'state_before', 'state_after',
              'cleaned_semantic_query', 'typesense_query', 'returned_recipes', 'assistant_response')
    trace = {key: turn.get(key) for key in fields}
    return hashlib.sha256(json.dumps(trace, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def apply_manual_ratings(report, path):
    ratings = json.loads(path.read_text()) if path.exists() else {'turns': {}}
    counts = {label: 0 for label in ('GOOD', 'MINOR', 'BAD', 'UNREVIEWED')}
    for conversation in report['conversations']:
        for index, turn in enumerate(conversation['turns']):
            key = f"{conversation['name']}:{index}"
            rating = ratings.get('turns', {}).get(key, {})
            if rating.get('fingerprint') != turn_fingerprint(turn):
                rating = {'classification': 'UNREVIEWED', 'reason': 'No manual rating for this exact trace.'}
            label = rating.get('classification', 'UNREVIEWED')
            if label not in counts:
                label = 'UNREVIEWED'
            turn['manual_review'] = {'classification': label, 'reason': rating.get('reason', '')}
            counts[label] += 1
    total = sum(counts.values())
    report['manual_quality_review'] = {
        'rubric': ratings.get('rubric', 'Manual ratings pending.'),
        'counts': counts,
        'good_percent': round(100 * counts['GOOD'] / total, 2) if total else 0,
        'bad_percent': round(100 * counts['BAD'] / total, 2) if total else 0,
        'target_met': bool(total and not counts['UNREVIEWED'] and counts['GOOD'] / total >= .9 and counts['BAD'] / total <= .05),
        'limitations': ratings.get('limitations', []),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--ratings', type=Path, help='Manual ratings file; changed traces remain unreviewed')
    parser.add_argument('--language-benchmark', action='store_true', help='Run the fixed natural-language conversation benchmark')
    args = parser.parse_args()
    report = run_review(configured_service(), args.language_benchmark)
    if args.language_benchmark:
        apply_manual_ratings(report, args.ratings or ROOT / 'scripts/fixtures/recipe_chat_language_ratings.json')
    output = args.output or ROOT / ('recipe_chat_language_review.json' if args.language_benchmark else 'recipe_chat_review.json')
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: report.get(key) for key in ('status', 'indexed_documents', 'turn_count', 'search_count', 'latency', 'manual_quality_review')}, indent=2))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
