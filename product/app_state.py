"""Shared state for the Hotel AgentOps app: which store, which hotel, and cached day records."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from product import core
from product.store import MemoryStore, StoreError, SupabaseStore


def secret(name: str):
    try:
        return st.secrets.get(name)
    except Exception:                                  # no secrets file
        return None


def database_configured() -> bool:
    return bool(secret("SUPABASE_URL") and secret("SUPABASE_SECRET_KEY"))


def get_store(mode: str | None = None):
    mode = mode or st.session_state.get("ha_mode")
    if mode == "live":
        return SupabaseStore(secret("SUPABASE_URL"), secret("SUPABASE_SECRET_KEY"),
                             salt=secret("APP_SALT") or secret("SUPABASE_URL"))
    return MemoryStore(st.session_state.setdefault("ha_memory", {}))


def hotel() -> dict | None:
    return st.session_state.get("ha_hotel")


def is_demo() -> bool:
    return st.session_state.get("ha_mode") == "demo"


def open_workspace(mode: str, hotel_row: dict) -> None:
    st.session_state.ha_mode = mode
    st.session_state.ha_hotel = hotel_row
    st.session_state.pop("ha_days", None)


def close_workspace() -> None:
    for k in [k for k in st.session_state.keys() if k.startswith(("ha_", "td_", "co_", "cp_", "su_"))]:
        if k != "ha_memory":
            del st.session_state[k]


def days(refresh: bool = False) -> list[dict]:
    h = hotel()
    if h is None:
        return []
    if refresh or "ha_days" not in st.session_state:
        st.session_state.ha_days = get_store().list_days(h["id"])
    return st.session_state.ha_days


def invalidate() -> None:
    st.session_state.pop("ha_days", None)


def profile() -> dict:
    return hotel()["profile"]


def save_profile(new_profile: dict, name: str | None = None, actor: str = "") -> None:
    h = hotel()
    store = get_store()
    store.update_profile(h["id"], new_profile, name=name)
    store.log(h["id"], actor or new_profile.get("approver") or "manager", "profile_updated",
              {"fields": sorted(new_profile.keys())})
    h["profile"] = new_profile
    if name:
        h["name"] = name


def today() -> str:
    if is_demo() and profile().get("demo_anchor_date"):
        return profile()["demo_anchor_date"]
    return dt.date.today().isoformat()


def performance_for(service_date: str) -> dict:
    return core.performance(profile(), days(), service_date)


def guard(fn):
    """Run a page body; show database problems as a clear message instead of a stack trace."""
    try:
        fn()
    except StoreError as ex:
        st.error(str(ex))
        st.caption("Your work on this page was not saved. Fix the issue above and try again.")


def ai_available() -> bool:
    return bool(secret("GEMINI_API_KEY"))


def ai_config():
    """AI agents for this workspace, or None to use the rule-based agents. Proposals are cached per workspace so the
    preview and the saved plan use the same agent outputs."""
    if not ai_available() or profile().get("agent_mode", "ai") != "ai":
        return None
    from product import agent as llm
    from product.ai_agents import AIConfig
    models = [m for m in [secret("GEMINI_MODEL")] if m] + list(llm.FALLBACK_MODELS)
    cache = st.session_state.setdefault(f"ha_ai_cache_{hotel()['id']}", {})
    state = st.session_state.setdefault("ha_ai_state", {})
    return AIConfig(api_key=secret("GEMINI_API_KEY"), models=models, cache=cache, state=state)
