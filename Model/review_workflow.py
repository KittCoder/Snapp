from __future__ import annotations

import fcntl
import hmac
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from product_compatibility import DEFAULT_OVERRIDES_PATH, default_overrides, get_product_match_service
from product_retrieval import normalize_text


AUDIT_LOG_PATH = Path(__file__).resolve().parent / "product_match_override_audit.jsonl"
LOCK_PATH = Path(__file__).resolve().parent / ".product_match_overrides.lock"
MUTATION_TYPES = {
    "approve_match": "approved_matches",
    "forbid_product": "forbidden_products",
    "define_alias": "aliases",
    "assign_canonical": "canonical_overrides",
    "acceptable_substitution": "substitutions",
    "mark_incompatible_family": "incompatible_families",
}


def admin_token_configured() -> bool:
    return bool(os.getenv("SNAPP_ADMIN_TOKEN"))


def require_admin(headers: dict[str, str]) -> tuple[bool, str]:
    expected = os.getenv("SNAPP_ADMIN_TOKEN", "")
    if not expected:
        return False, "SNAPP_ADMIN_TOKEN is not configured."
    supplied = headers.get("X-SNAPP-Admin-Token") or ""
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        return False, "Invalid admin token."
    return True, ""


def load_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict[str, Any]:
    if not path.exists():
        return default_overrides()
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    merged = default_overrides()
    merged.update(payload)
    for key in default_overrides():
        if key != "version" and not isinstance(merged.get(key), list):
            raise ValueError(f"override field {key} must be a list")
    return merged


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")
        temp_name = file.name
    os.replace(temp_name, path)


def validate_override_item(action: str, body: dict[str, Any]) -> dict[str, Any]:
    query = normalize_text(body.get("query") or body.get("normalized_query") or "")
    reason = str(body.get("reason") or "").strip()
    if not query:
        raise ValueError("query is required")
    if not reason:
        raise ValueError("reason is required")
    item: dict[str, Any] = {"query": query, "reason": reason}
    if action in {"approve_match", "forbid_product", "acceptable_substitution"}:
        product_id = str(body.get("product_id") or "").strip()
        if not product_id:
            raise ValueError("product_id is required")
        item["product_id"] = product_id
    elif action == "define_alias":
        canonical = normalize_text(body.get("canonical") or "")
        if not canonical:
            raise ValueError("canonical is required")
        item["alias"] = query
        item["canonical"] = canonical
        item.pop("query", None)
    elif action == "assign_canonical":
        canonical = normalize_text(body.get("canonical") or "")
        if not canonical:
            raise ValueError("canonical is required")
        item["canonical"] = canonical
    elif action == "mark_incompatible_family":
        family = normalize_text(body.get("family") or "")
        if not family:
            raise ValueError("family is required")
        item["family"] = family
    else:
        raise ValueError("unsupported override action")
    return item


def mutate_override(
    action: str,
    body: dict[str, Any],
    *,
    actor: str,
    path: Path = DEFAULT_OVERRIDES_PATH,
    audit_path: Path = AUDIT_LOG_PATH,
) -> dict[str, Any]:
    if action == "remove":
        key = str(body.get("key") or "")
        index = body.get("index")
        if key not in default_overrides() or key == "version":
            raise ValueError("valid override key is required")
        if not isinstance(index, int):
            raise ValueError("index is required")
        item = None
    else:
        key = MUTATION_TYPES.get(action)
        if not key:
            raise ValueError("unsupported override action")
        item = validate_override_item(action, body)

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        overrides = load_overrides(path)
        previous = json.loads(json.dumps(overrides.get(key) or []))
        if action == "remove":
            if index < 0 or index >= len(overrides[key]):
                raise ValueError("override index is out of range")
            removed = overrides[key].pop(index)
            new_value = json.loads(json.dumps(overrides[key]))
        else:
            overrides[key].append(item)
            removed = None
            new_value = json.loads(json.dumps(overrides[key]))
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        overrides["version"] = f"overrides-{timestamp.replace(':', '').replace('-', '')}"
        if path.exists():
            backup = path.with_suffix(path.suffix + f".{int(time.time())}.bak")
            backup.write_bytes(path.read_bytes())
        atomic_json_write(path, overrides)
        audit_record = {
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "key": key,
            "reason": str(body.get("reason") or ""),
            "previous_value": previous,
            "new_value": new_value,
            "removed_value": removed,
            "durability": "local-file; commit or persistent storage required for Render durability",
        }
        with audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(audit_record, sort_keys=True) + "\n")
        service = get_product_match_service()
        service.overrides._data = None
        service.overrides.load_error = None
        service.cache.clear()
        if getattr(getattr(service, "retriever", None), "query_cache", None):
            service.retriever.query_cache.clear()
        try:
            from basket_quantity import get_basket_builder

            get_basket_builder().clear_caches()
        except Exception:
            pass
        fcntl.flock(lock_file, fcntl.LOCK_UN)
    return {"version": overrides["version"], "audit": audit_record}


def override_summary(path: Path = DEFAULT_OVERRIDES_PATH) -> dict[str, Any]:
    overrides = load_overrides(path)
    return {
        "version": overrides.get("version"),
        "counts": {
            key: len(value)
            for key, value in overrides.items()
            if isinstance(value, list)
        },
        "durability": "local-file; commit generated override/audit changes or use persistent storage on Render",
    }
