"""Manual review persistence, separate from production matching."""
from __future__ import annotations
import csv
import fcntl
from contextlib import contextmanager
import hashlib
import io
import json
import os
import tempfile
import threading
from pathlib import Path

LABELS = ['CORRECT', 'ACCEPTABLE_SUBSTITUTE', 'WRONG', 'SHOULD_HAVE_MATCHED', 'AMBIGUOUS']
FIELDS = ['review_label', 'reviewer', 'review_notes', 'failure_cause', 'wrong_family', 'prepared_food_false_positive', 'structurally_correct']
CAUSES = ['wrong family', 'wrong subfamily', 'wrong species', 'wrong cut', 'wrong state/form', 'wrong dietary identity', 'wrong flavor', 'wrong fat/salt attribute', 'prepared-food leakage', 'brand noise', 'alias/taxonomy issue', 'embedding/lexical issue', 'unknown']


def atomic_write(path, content):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class ReviewStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.original = self.directory / 'review.csv'
        self.sidecar = self.directory / 'review_labels.json'
        self.labeled = self.directory / 'review_labeled.csv'
        self.lock = threading.Lock()
        self.source_hash = hashlib.sha256(self.original.read_bytes()).hexdigest()
        with self.original.open(newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            self.columns = reader.fieldnames
            self.rows = list(reader)
        self.ids = {r['case_id'] for r in self.rows}
        if len(self.ids) != len(self.rows):
            raise ValueError('Original sample has duplicate IDs')
        self.state = {'source_sha256': self.source_hash, 'revision': 0, 'labels': {}}
        with self.file_lock():
            if self.sidecar.exists():
                self.reload_state()
                # JSON is authoritative; repair CSV after an interrupted write.
                self.write_csv()
            elif self.labeled.exists():
                raise ValueError('Labeled CSV exists without its sidecar; refusing to overwrite it')

    @contextmanager
    def file_lock(self):
        with (self.directory / '.review_labels.lock').open('a') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def reload_state(self):
        if hashlib.sha256(self.original.read_bytes()).hexdigest() != self.source_hash:
            raise ValueError('Original review.csv changed; refusing to mix samples')
        if self.sidecar.exists():
            state = json.loads(self.sidecar.read_text())
            if state['source_sha256'] != self.source_hash:
                raise ValueError('Sidecar belongs to a different sample')
            if not isinstance(state['revision'], int) or state['revision'] < 0:
                raise ValueError('Invalid sidecar revision')
            for key, values in state['labels'].items():
                self.validate(key, values)
            self.state = state

    def validate(self, key, values):
        if key not in self.ids or set(values) - set(FIELDS):
            raise ValueError('Unknown case or review field')
        if any(not isinstance(v, str) for v in values.values()):
            raise ValueError('Review values must be strings')
        if values.get('review_label', '') not in [''] + LABELS:
            raise ValueError('Unknown review label')
        if values.get('failure_cause', '') not in [''] + CAUSES:
            raise ValueError('Unknown failure cause')
        for field in ['wrong_family', 'prepared_food_false_positive', 'structurally_correct']:
            if values.get(field, '') not in ['', 'yes', 'no']:
                raise ValueError('Review flags must be blank, yes or no')

    def merged(self):
        return [{**row, **self.state['labels'].get(row['case_id'], {})} for row in self.rows]

    def write_csv(self):
        text = io.StringIO(newline='')
        writer = csv.DictWriter(text, fieldnames=self.columns)
        writer.writeheader()
        writer.writerows(self.merged())
        atomic_write(self.labeled, text.getvalue())

    def snapshot(self):
        with self.lock, self.file_lock():
            self.reload_state()
            return {'revision': self.state['revision'], 'cases': self.merged(), 'labels': LABELS, 'causes': CAUSES}

    def save(self, key, values, revision):
        self.validate(key, values)
        with self.lock, self.file_lock():
            self.reload_state()
            if revision != self.state['revision']:
                raise RuntimeError('Review changed in another session. Reload before saving; your edits have not been overwritten.')
            state = {**self.state, 'labels': dict(self.state['labels']), 'revision': self.state['revision'] + 1}
            state['labels'][key] = {**state['labels'].get(key, {}), **values}
            atomic_write(self.sidecar, json.dumps(state, indent=2) + '\n')
            self.state = state
            self.write_csv()
            return self.state['revision']
