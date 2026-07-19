from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None, timeout: float = 20.0) -> tuple[int, dict, float]:
    body = None
    final_headers = {"Content-Type": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    started = time.perf_counter()
    try:
        with urlopen(Request(url, data=body, headers=final_headers, method=method), timeout=timeout) as response:
            text = response.read().decode("utf-8")
            return response.status, json.loads(text or "{}"), round((time.perf_counter() - started) * 1000, 2)
    except HTTPError as exc:
        text = exc.read().decode("utf-8")
        try:
            data = json.loads(text or "{}")
        except json.JSONDecodeError:
            data = {"error": text}
        return exc.code, data, round((time.perf_counter() - started) * 1000, 2)
    except URLError as exc:
        return 0, {"error": str(exc)}, round((time.perf_counter() - started) * 1000, 2)


def fail(message: str, details: dict | None = None) -> None:
    print(json.dumps({"status": "failed", "error": message, "details": details or {}}, indent=2), file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a local or deployed SNAPP API instance.")
    parser.add_argument("--base-url", default="http://localhost:5000")
    parser.add_argument("--admin-token", default="")
    parser.add_argument("--ten-recipe-latency-ms", type=float, default=3000.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    results = {}

    status, data, latency = request_json(f"{base}/health", timeout=10)
    results["health"] = {"status": status, "latency_ms": latency, "body": data}
    if status != 200 or data.get("status") != "ok":
        fail("/health failed", results)

    status, data, latency = request_json(f"{base}/ready", timeout=30)
    results["ready"] = {"status": status, "latency_ms": latency, "semantic_readiness": data.get("semantic_readiness"), "body": data}
    if status != 200:
        fail("/ready failed", results)

    dish_payload = {
        "meal_prompt": "chicken dinner",
        "household_size": 2,
        "pantry_items": [],
        "dietary_restrictions": "",
    }
    status, data, latency = request_json(f"{base}/dishes", method="POST", payload=dish_payload, timeout=60)
    results["dishes_first"] = {"status": status, "latency_ms": latency, "dish_count": len(data.get("dishes") or [])}
    if status != 200 or not data.get("dishes"):
        fail("/dishes smoke request failed", results)
    if any(
        conflict.get("classification") == "hard_reject"
        for dish in data.get("dishes") or []
        for ingredient in dish.get("ingredients_to_buy") or []
        for conflict in ingredient.get("conflicts") or []
    ):
        fail("hard conflict appeared in dishes response", results)

    status, data, latency = request_json(f"{base}/dishes", method="POST", payload=dish_payload, timeout=60)
    results["dishes_repeated"] = {"status": status, "latency_ms": latency, "dish_count": len(data.get("dishes") or [])}
    if status != 200:
        fail("repeated /dishes request failed", results)

    if args.admin_token:
        status, data, latency = request_json(
            f"{base}/internal/diagnostics",
            headers={"X-SNAPP-Admin-Token": args.admin_token},
            timeout=30,
        )
        results["diagnostics"] = {
            "status": status,
            "latency_ms": latency,
            "artifact_ok": data.get("artifact_validation", {}).get("ok"),
            "metrics_present": bool(data.get("metrics")),
        }
        if status != 200 or not data.get("artifact_validation", {}).get("ok"):
            fail("protected diagnostics failed", results)

    print(json.dumps({"status": "ok", "results": results}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
