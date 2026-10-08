#!/usr/bin/env python3
"""Verify corpus coverage and random real Recipe Chat results against Typesense."""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Model'))


def usable(value):
    return (isinstance(value, str) and bool(value.strip()) or
            isinstance(value, list) and any(isinstance(step, str) and step.strip() for step in value))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--seed', type=int, default=20261005)
    args = parser.parse_args()
    import model
    import recipe_search_typesense as search

    rows = list(search.iter_corpus(args.corpus))
    by_id = {search.stable_document_id(row): row for row in rows}
    present = sum(bool(usable(row.get('instructions'))) for row in rows)
    rng = random.Random(args.seed)
    rng.shuffle(rows)
    checked, seen = [], set()
    client = model.app.test_client()
    for row in rows[:200]:
        response = client.post('/api/recipes/chat', json={'message': 'find me ' + row['title']})
        if response.status_code != 200:
            raise RuntimeError('Live Recipe Chat search failed')
        results = response.get_json()['results']
        assert all('instructions' not in result and 'ingredients' not in result for result in results), 'Search detail payload leaked'
        rng.shuffle(results)
        selected = next((result for result in results if result['id'] not in seen), None)
        if selected is None:
            continue
        recipe_id = selected['id']
        seen.add(recipe_id)
        original = by_id[recipe_id]
        response = client.post('/api/recipes/detail', json={'recipe_id': recipe_id})
        detail = response.get_json().get('dish', {})
        instructions = detail.get('recipe', {}).get('instructions')
        valid = response.status_code == 200 and detail.get('recipe_id') == recipe_id
        equal = valid and instructions == (original.get('instructions') or '')
        checked.append({'id': recipe_id, 'title': selected.get('title'),
                        'instructions_available': bool(valid and usable(instructions)),
                        'corpus_missing': not bool(usable(original.get('instructions'))),
                        'lookup_failure': not valid or not equal,
                        'original_steps_preserved': equal})
        if len(checked) == args.samples:
            break
    report = {
        'corpus': str(args.corpus), 'total_recipes': len(rows),
        'recipes_with_instructions': present, 'recipes_without_instructions': len(rows) - present,
        'instruction_coverage_percent': 100 * present / len(rows),
        'seed': args.seed, 'sample_size': len(checked),
        'instructions_available': sum(row['instructions_available'] for row in checked),
        'true_corpus_missing': sum(row['corpus_missing'] for row in checked),
        'lookup_failures': sum(row['lookup_failure'] for row in checked),
        'samples': checked,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'samples'}, indent=2))
    return 0 if len(checked) == args.samples and report['lookup_failures'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
