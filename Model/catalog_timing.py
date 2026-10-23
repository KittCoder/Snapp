"""Opt-in server timings. Labels are code constants; no queries or credentials."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import os
import threading
import time

from flask import has_request_context, request
from ops_metrics import log_event

_trace = ContextVar('catalog_timing', default=None)
_store = ContextVar('catalog_timing_store', default=None)


class TimingTrace:
    def __init__(self):
        self.lock = threading.Lock()
        self.stages = {}

    def add(self, stage, elapsed):
        key = (_store.get(), stage)
        with self.lock:
            value = self.stages.setdefault(key, {'calls': 0, 'ms': 0.0})
            value['calls'] += 1
            value['ms'] += elapsed * 1000

    def summary(self):
        with self.lock:
            return [{'store_id': store, 'stage': stage, 'calls': value['calls'],
                     'ms': round(value['ms'], 3)}
                    for (store, stage), value in sorted(self.stages.items(), key=str)]


@contextmanager
def capture_timings():
    trace = TimingTrace()
    token = _trace.set(trace)
    try:
        yield trace
    finally:
        _trace.reset(token)


@contextmanager
def store_timing(store_id):
    token = _store.set(store_id)
    try:
        yield
    finally:
        _store.reset(token)


@contextmanager
def timing(stage):
    trace = _trace.get()
    if trace is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        trace.add(stage, time.perf_counter() - started)


def timed(stage):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            with timing(stage):
                return function(*args, **kwargs)
        return call
    return decorate


def profile_catalog_request(function):
    @wraps(function)
    def call(*args, **kwargs):
        if os.getenv('STORE_CATALOG_TIMING', '').lower() not in ('1', 'true', 'yes'):
            return function(*args, **kwargs)
        with capture_timings() as trace:
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                request_id = getattr(request, 'snapp_request_id', None) if has_request_context() else None
                log_event('store_catalog_timing', request_id=request_id,
                          wall_ms=round((time.perf_counter() - started) * 1000, 3))
                # Separate stores avoid the logger's 50-item list truncation on
                # thirteen-store requests. Timings are inclusive, not additive.
                groups = {}
                for stage in trace.summary():
                    groups.setdefault(stage['store_id'], []).append(stage)
                for store, stages in groups.items():
                    log_event('store_catalog_stage_timing', request_id=request_id,
                              store_id=store, stages=stages)
    return call
