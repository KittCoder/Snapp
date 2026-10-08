#!/usr/bin/env python3
"""Build query-time vocabulary from the unchanged canonical recipe export."""
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--documents', type=Path, default=ROOT / 'data/snapp_typesense_documents.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT / 'Model/ingredient_vocabulary.json')
    args = parser.parse_args()
    counts = Counter()
    with args.documents.open() as handle:
        for line in handle:
            if line.strip(): counts.update(name.lower() for name in json.loads(line)['ingredient_names'])
    args.output.write_text(json.dumps(dict(sorted(counts.items())), indent=2) + '\n')
    print(f'Saved {len(counts)} corpus ingredient names to {args.output}')


if __name__ == '__main__':
    main()
