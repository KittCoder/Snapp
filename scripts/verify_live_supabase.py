"""Operator-run disposable REST/RLS probe. Never prints provider bodies or secrets.

Requires reviewed migrations and admin access; prompts keep keys out of argv/history.
This does not apply migrations or certify dashboard settings/browser auth flows.
"""
import argparse
import getpass
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


TABLES = {
    "user_info": ("id", "username", {"username": "security_fixture"}),
    "user_pantry_items": ("user_id", "name", {"name": "security_fixture", "quantity": "1 item"}),
    "user_stores": ("user_id", "name", {"store_key": "security_fixture", "name": "security_fixture"}),
    "user_scheduled_meals": ("user_id", "meal_name", {"meal_name": "security_fixture", "scheduled_day": "Unscheduled", "meal_data": {}}),
    "user_favorite_recipes": ("user_id", "recipe_name", {"recipe_key": "security_fixture", "recipe_name": "security_fixture", "recipe_data": {}}),
}


class Failure(Exception):
    pass


def require(condition, label):
    if not condition:
        raise Failure(label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-url", required=True)
    parser.add_argument("--expected-project-ref", required=True)
    parser.add_argument("--check-expired-token", action="store_true",
                        help="Prompt for a genuinely expired token issued by this project")
    args = parser.parse_args()
    require(args.project_url == "https://" + args.expected_project_ref + ".supabase.co", "project_ref_mismatch")
    public_key = getpass.getpass("Project publishable/anon key (hidden): ")
    admin_key = getpass.getpass("Project service-role/secret admin key (hidden): ")
    expired = getpass.getpass("Genuinely expired project access token (hidden): ") if args.check_expired_token else None
    run = uuid.uuid4().hex
    users = []
    sessions = []
    rows = {}
    passed = False
    cleanup_ok = True

    def request(method, path, body=None, token=None, admin=False, raw_header=None):
        headers = {"apikey": admin_key if admin else public_key, "Content-Type": "application/json", "Prefer": "return=representation"}
        if admin:
            # Legacy service-role JWTs require Bearer; new secret keys use apikey.
            if admin_key.startswith("eyJ"):
                headers["Authorization"] = "Bearer " + admin_key
        elif raw_header is not None:
            headers["Authorization"] = raw_header
        elif token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(args.project_url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                status, data = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, data = error.code, error.read()
        except (urllib.error.URLError, TimeoutError):
            raise Failure("network_failure") from None
        try:
            result = json.loads(data) if data else None
        except (ValueError, UnicodeError):
            raise Failure("unexpected_response_format") from None
        return status, result

    def record(table, uid):
        owner, _, template = TABLES[table]
        row = dict(template, **{owner: uid})
        if owner != "id":
            row["id"] = str(uuid.uuid4())
        for key in ("store_key", "recipe_key"):
            if key in row:
                row[key] = run + "_" + row["id"]
        return row

    def path(table, row):
        return "/rest/v1/" + table + "?id=eq." + row["id"]

    def read(table, row, token):
        status, result = request("GET", path(table, row), token=token)
        require(status == 200 and isinstance(result, list) and len(result) == 1, table + ":own_read")
        return result[0]

    try:
        for label in ("a", "b"):
            email = "snapp-security-" + run + "-" + label + "@example.invalid"
            password = secrets.token_urlsafe(40)
            status, user = request("POST", "/auth/v1/admin/users", {"email": email, "password": password, "email_confirm": True}, admin=True)
            require(status in (200, 201) and isinstance(user, dict) and user.get("id"), "create_disposable_user")
            users.append(user["id"])
            status, session = request("POST", "/auth/v1/token?grant_type=password", {"email": email, "password": password})
            require(status == 200 and session.get("access_token"), "password_login")
            sessions.append(session)
        a, b = users
        ta, tb = [s["access_token"] for s in sessions]
        for table, (owner, field, _) in TABLES.items():
            rows[table] = [record(table, uid) for uid in users]
            for row, token in zip(rows[table], (ta, tb)):
                # Profile creation triggers can populate the disposable user's row.
                if table == "user_info":
                    status, existing = request("GET", path(table, row), token=token)
                    require(status == 200, table + ":profile_read")
                    if existing:
                        status, _ = request("DELETE", path(table, row), token=token)
                        require(status in (200, 204), table + ":profile_fixture_reset")
                status, result = request("POST", "/rest/v1/" + table, row, token=token)
                require(status == 201 and result and len(result) == 1, table + ":own_insert")
            ar, br = rows[table]
            original_b = read(table, br, tb)
            status, result = request("GET", path(table, br), token=ta)
            require((status == 200 and result == []) or status in (401, 403), table + ":cross_read")
            print(table + " cross_read status=" + str(status) + " blocked")
            status, result = request("PATCH", path(table, br), {field: "unauthorized_mutation"}, token=ta)
            require((status == 200 and result == []) or status in (401, 403), table + ":cross_update")
            require(read(table, br, tb) == original_b, table + ":cross_update_survival")
            print(table + " cross_update status=" + str(status) + " blocked; B unchanged")
            status, result = request("DELETE", path(table, br), token=ta)
            require((status in (200, 204) and result in ([], None)) or status in (401, 403), table + ":cross_delete")
            require(read(table, br, tb) == original_b, table + ":cross_delete_survival")
            print(table + " cross_delete status=" + str(status) + " blocked; B survives")
            # Remove B's profile to prevent duplicate-PK errors masking RLS failures.
            if table == "user_info":
                status, _ = request("DELETE", path(table, br), token=tb)
                require(status in (200, 204), table + ":own_delete_B")
            status, result = request("POST", "/rest/v1/" + table, record(table, b), token=ta)
            require(status == 403 and isinstance(result, dict) and result.get("code") == "42501", table + ":insert_spoof")
            status, result = request("PATCH", path(table, ar), {owner: b}, token=ta)
            require(status == 403 and isinstance(result, dict) and result.get("code") == "42501", table + ":owner_change")
            require(read(table, ar, ta)[owner] == a, table + ":owner_unchanged")
            status, result = request("PATCH", path(table, ar), {field: "security_updated"}, token=ta)
            require(status == 200 and result and read(table, ar, ta)[field] == "security_updated", table + ":own_update")
            for label, token, header in (("missing", None, None), ("invalid", "invalid-token", None), ("malformed", None, "Basic invalid")):
                status, _ = request("GET", path(table, ar), token=token, raw_header=header)
                require(status in (401, 403), table + ":token_" + label)
            if expired:
                status, _ = request("GET", path(table, ar), token=expired)
                require(status in (401, 403), table + ":expired_token")
            status, _ = request("DELETE", path(table, ar), token=ta)
            require(status in (200, 204), table + ":own_delete")
            status, result = request("GET", path(table, ar), token=ta)
            require(status == 200 and result == [], table + ":own_delete_verified")
            print(table + " insert_spoof/owner_change blocked; own CRUD passed; token failures safe")
        for table in ("canonical_ingredients", "ingredient_aliases", "grocery_product_features"):
            for token in (None, ta):
                status, _ = request("GET", "/rest/v1/" + table + "?limit=1", token=token)
                require(status in (401, 403), table + ":server_only_reference")
            print(table + " server-only reference access denied as designed")
        status, refreshed = request("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": sessions[0]["refresh_token"]})
        require(status == 200 and refreshed.get("access_token"), "session_refresh")
        status, _ = request("GET", "/auth/v1/user", token=refreshed["access_token"])
        require(status == 200, "valid_auth_token")
        status, _ = request("POST", "/auth/v1/logout", token=refreshed["access_token"])
        require(status in (200, 204), "logout")
        status, _ = request("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": refreshed["refresh_token"]})
        require(status in (400, 401, 403), "logged_out_refresh_rejected")
        print("REST login/refresh/logout passed; expired_token=" + ("passed" if expired else "NOT_TESTED"))
        print("Frontend browser flow and deployed Flask public-data smoke remain manual")
        passed = True
    except Failure as error:
        print("FAILED check=" + str(error))
    except Exception:
        # Suppress traceback/provider payloads and exception messages containing secrets.
        print("FAILED unexpected_local_error")
    finally:
        # Delete only this run's known auth IDs; FK cascade removes their fixtures.
        # Explicit owner cleanup also covers live schemas without ON DELETE CASCADE.
        for uid in users:
            try:
                for table, (owner, _, _) in TABLES.items():
                    status, _ = request("DELETE", "/rest/v1/" + table + "?" + owner + "=eq." + uid, admin=True)
                    require(status in (200, 204), "cleanup_records")
                status, _ = request("DELETE", "/auth/v1/admin/users/" + uid, admin=True)
                require(status in (200, 204), "cleanup_user")
                status, result = request("GET", "/auth/v1/admin/users/" + uid, admin=True)
                require(status == 404, "cleanup_user_verified")
            except Exception:
                cleanup_ok = False
                print("MANUAL_CLEANUP_REQUIRED disposable_user_id=" + uid)
        print("cleanup=" + ("passed" if cleanup_ok else "blocked"))
    return 0 if passed and cleanup_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as error:
        print("FAILED check=" + str(error))
        sys.exit(1)
