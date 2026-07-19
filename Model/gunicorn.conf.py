from __future__ import annotations

import os
import threading


def post_worker_init(worker):
    if os.getenv("SNAPP_DISABLE_MATCHER_WARMUP", "").lower() in {"1", "true", "yes"}:
        return
    import matcher_warmup
    from ops_metrics import log_event

    diagnostics = matcher_warmup.module_diagnostics(include_private_ids=True)
    message = (
        "gunicorn_post_worker_init "
        f"pid={os.getpid()} "
        f"ppid={os.getppid()} "
        f"thread={threading.current_thread().name} "
        f"module_name={diagnostics.get('module_name')} "
        f"manager_id={diagnostics.get('manager_id')} "
        f"state_id={diagnostics.get('state_id')} "
        f"status={diagnostics.get('warmup_state_status')} "
        f"warmup_completed={diagnostics.get('warmup_state_completed')}"
    )
    log_event(message, event_name="gunicorn_post_worker_init", **diagnostics)
    matcher_warmup.start_background_warmup()
