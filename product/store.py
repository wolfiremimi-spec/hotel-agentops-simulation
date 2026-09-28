"""Storage for hotel workspaces: Supabase (Postgres over its REST API) in production, memory for the demo.

Both stores have the same methods. Access to a workspace is by a private access code; only its SHA-256 hash is
stored. The Supabase secret key is read from Streamlit secrets on the server and never reaches the browser.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import secrets
import uuid

import requests

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"          # no 0/O or 1/I


class StoreError(Exception):
    pass


def new_access_code() -> str:
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3))


def normalize_code(code: str) -> str:
    raw = "".join(ch for ch in (code or "").upper() if ch.isalnum())
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def hash_code(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{normalize_code(code)}".encode()).hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class MemoryStore:
    """Session-only store (demo workspace, or when no database is configured)."""
    persistent = False

    def __init__(self, container: dict, salt: str = "memory"):
        self.db = container.setdefault("hotels", {})
        self.salt = salt

    def create_hotel(self, name: str, profile: dict) -> tuple[str, str]:
        code, hid = new_access_code(), str(uuid.uuid4())
        self.db[hid] = {"id": hid, "name": name, "access_hash": hash_code(code, self.salt), "profile": copy.deepcopy(profile),
                        "days": {}, "audit": [], "created_at": _now()}
        return hid, code

    def open_hotel(self, code: str) -> dict | None:
        h = hash_code(code, self.salt)
        row = next((r for r in self.db.values() if r["access_hash"] == h), None)
        return {"id": row["id"], "name": row["name"], "profile": copy.deepcopy(row["profile"])} if row else None

    def get_hotel(self, hotel_id: str) -> dict | None:
        row = self.db.get(hotel_id)
        return {"id": row["id"], "name": row["name"], "profile": copy.deepcopy(row["profile"])} if row else None

    def update_profile(self, hotel_id: str, profile: dict, name: str | None = None) -> None:
        self.db[hotel_id]["profile"] = copy.deepcopy(profile)
        if name:
            self.db[hotel_id]["name"] = name

    def list_days(self, hotel_id: str) -> list[dict]:
        return [copy.deepcopy(d) for _, d in sorted(self.db[hotel_id]["days"].items())]

    def get_day(self, hotel_id: str, service_date: str) -> dict | None:
        d = self.db[hotel_id]["days"].get(service_date)
        return copy.deepcopy(d) if d else None

    def save_day(self, hotel_id: str, service_date: str, **fields) -> dict:
        days = self.db[hotel_id]["days"]
        d = days.setdefault(service_date, {"service_date": service_date, "status": "draft", "inputs": None, "run": None,
                                           "closeout": None, "created_at": _now()})
        d.update(copy.deepcopy(fields))
        d["updated_at"] = _now()
        return copy.deepcopy(d)

    def delete_day(self, hotel_id: str, service_date: str) -> None:
        self.db[hotel_id]["days"].pop(service_date, None)

    def log(self, hotel_id: str, actor: str, action: str, detail: dict | None = None) -> None:
        self.db[hotel_id]["audit"].append({"at": _now(), "actor": actor, "action": action, "detail": detail or {}})

    def list_audit(self, hotel_id: str, limit: int = 500) -> list[dict]:
        return list(reversed(self.db[hotel_id]["audit"]))[:limit]


class SupabaseStore:
    """Postgres via Supabase's REST API (PostgREST). Server-side only."""
    persistent = True

    def __init__(self, url: str, key: str, salt: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.salt = salt
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):                      # legacy service_role JWT also needs the bearer header
            self.headers["Authorization"] = f"Bearer {key}"

    def _req(self, method: str, table: str, params: dict | None = None, body=None, prefer: str | None = None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            r = requests.request(method, f"{self.base}/{table}", params=params, json=body, headers=headers, timeout=20)
        except requests.RequestException as ex:
            raise StoreError(f"Could not reach the database ({type(ex).__name__}).") from ex
        if r.status_code in (401, 403):
            raise StoreError("The database rejected the app's key. Check SUPABASE_SECRET_KEY in the app's secrets.")
        if r.status_code == 404:
            raise StoreError("The database tables are missing. Run product/schema.sql in the Supabase SQL editor.")
        if r.status_code >= 400:
            raise StoreError(f"Database error (HTTP {r.status_code}): {r.text[:200]}")
        return r.json() if r.text else None

    def create_hotel(self, name: str, profile: dict) -> tuple[str, str]:
        code = new_access_code()
        rows = self._req("POST", "hotels", body={"name": name, "access_hash": hash_code(code, self.salt), "profile": profile},
                         prefer="return=representation")
        return rows[0]["id"], code

    def open_hotel(self, code: str) -> dict | None:
        rows = self._req("GET", "hotels", params={"access_hash": f"eq.{hash_code(code, self.salt)}",
                                                  "select": "id,name,profile"})
        return rows[0] if rows else None

    def get_hotel(self, hotel_id: str) -> dict | None:
        rows = self._req("GET", "hotels", params={"id": f"eq.{hotel_id}", "select": "id,name,profile"})
        return rows[0] if rows else None

    def update_profile(self, hotel_id: str, profile: dict, name: str | None = None) -> None:
        body = {"profile": profile, "updated_at": _now()}
        if name:
            body["name"] = name
        self._req("PATCH", "hotels", params={"id": f"eq.{hotel_id}"}, body=body, prefer="return=minimal")

    def list_days(self, hotel_id: str) -> list[dict]:
        return self._req("GET", "service_days", params={"hotel_id": f"eq.{hotel_id}", "order": "service_date.asc",
                                                        "select": "service_date,status,inputs,run,closeout,created_at,updated_at"})

    def get_day(self, hotel_id: str, service_date: str) -> dict | None:
        rows = self._req("GET", "service_days", params={"hotel_id": f"eq.{hotel_id}", "service_date": f"eq.{service_date}",
                                                        "select": "service_date,status,inputs,run,closeout,created_at,updated_at"})
        return rows[0] if rows else None

    def save_day(self, hotel_id: str, service_date: str, **fields) -> dict:
        body = {"hotel_id": hotel_id, "service_date": service_date, "updated_at": _now(), **fields}
        rows = self._req("POST", "service_days", params={"on_conflict": "hotel_id,service_date"}, body=body,
                         prefer="resolution=merge-duplicates,return=representation")
        return rows[0]

    def delete_day(self, hotel_id: str, service_date: str) -> None:
        self._req("DELETE", "service_days", params={"hotel_id": f"eq.{hotel_id}", "service_date": f"eq.{service_date}"},
                  prefer="return=minimal")

    def log(self, hotel_id: str, actor: str, action: str, detail: dict | None = None) -> None:
        self._req("POST", "audit_events", body={"hotel_id": hotel_id, "actor": actor, "action": action, "detail": detail or {}},
                  prefer="return=minimal")

    def list_audit(self, hotel_id: str, limit: int = 500) -> list[dict]:
        return self._req("GET", "audit_events", params={"hotel_id": f"eq.{hotel_id}", "order": "at.desc",
                                                        "limit": str(limit), "select": "at,actor,action,detail"})
