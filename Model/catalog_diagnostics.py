"""Credential-safe diagnostics for the backend inventory boundary."""
import json
import logging
import os
import re
from contextlib import contextmanager

from flask import has_request_context, request
from ops_metrics import log_event


def safe_message(value):
    text = str(value)
    for name, secret in os.environ.items():
        if secret and re.search(r'key|token|secret|password|redis_url', name, re.I):
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)(?:https?|rediss?)://\S+', '[REDACTED_URL]', text)
    text = re.sub(r'(?i)\b(?:authorization|apikey)\b[^\r\n]*', '[REDACTED]', text)
    text = re.sub(r'(?i)\b(?:Bearer|Basic)\s+\S+', '[REDACTED]', text)
    text = re.sub(r'\b(?:eyJ[\w.-]+|sb_(?:secret|publishable)_[\w-]+)', '[REDACTED]', text)
    return text.replace('\n', ' ').replace('\r', ' ')[:500]


def log_catalog_error(exc, component, table=None):
    fields = {
        'exception_class': type(exc).__name__,
        'safe_message': safe_message(exc),
        'component': getattr(exc, 'catalog_component', component),
        'target_table': getattr(exc, 'catalog_table', table),
        'request_id': getattr(request, 'snapp_request_id', None) if has_request_context() else None,
    }
    fields.update(getattr(exc, 'catalog_http', {}))
    # Include fields in the text too: the development formatter drops structured extras.
    log_event('store_catalog_error ' + json.dumps(fields, sort_keys=True),
              level=logging.ERROR, **fields)


@contextmanager
def catalog_operation(component, table=None):
    try:
        yield
    except Exception as exc:
        if not hasattr(exc, 'catalog_component'):
            exc.catalog_component = component
            exc.catalog_table = table
        log_catalog_error(exc, component, table)
        raise
