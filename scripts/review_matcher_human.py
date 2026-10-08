#!/usr/bin/env python3
"""Local-only reviewer. Does not import or run the matcher."""
import argparse
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from matcher_review_store import ReviewStore

ROOT = Path(__file__).resolve().parents[1]
UI = Path(__file__).resolve().parent / 'matcher_review_ui'


def create_app(directory):
    store = ReviewStore(directory)
    app = Flask(__name__, static_folder=None)

    @app.before_request
    def local_requests_only():
        # Reject cross-origin writes and foreign Host headers to this local utility.
        host = request.host.split(':')[0]
        if host not in ('localhost', '127.0.0.1'):
            return jsonify(error='Local requests only'), 403
        if request.method == 'POST' and request.headers.get('Origin') not in (None, 'http://' + request.host):
            return jsonify(error='Cross-origin writes are disabled'), 403

    @app.get('/')
    def index():
        return send_from_directory(UI, 'index.html')

    @app.get('/review.js')
    def javascript():
        return send_from_directory(UI, 'review.js')

    @app.get('/api/cases')
    def cases():
        return jsonify(store.snapshot())

    @app.post('/api/label')
    def label():
        body = request.get_json()
        try:
            revision = store.save(body['case_id'], body['values'], body['revision'])
        except RuntimeError as error:
            return jsonify(error=str(error)), 409
        except (ValueError, KeyError, TypeError) as error:
            return jsonify(error=str(error)), 400
        return jsonify(revision=revision, saved=True)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=ROOT / 'data/matcher_validation')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    create_app(args.directory).run(host='127.0.0.1', port=args.port, debug=False, threaded=False)
