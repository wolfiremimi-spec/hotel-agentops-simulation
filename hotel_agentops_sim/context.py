"""Context layer (case study layer 2): loads the 8 required sources, scores completeness,
detects stale and failed feeds, and gives each agent a least-privilege view.

No real systems are connected. Sources are read from the modeled scenario file, and
'failures' lets a test remove a source or simulate an API failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import ToolCall

STALE_AFTER_HOURS = {"inventory": 12, "shelf_life": 12}      # NA-07


class ContextPermissionError(PermissionError):
    """Raised when an agent reads a source outside its permissions."""


@dataclass
class ContextSnapshot:
    sources: dict                      # name -> data (only sources that loaded)
    status: dict                       # name -> ok | missing | fallback | stale
    required: list[str]
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def present(self) -> list[str]:
        return [s for s in self.required if self.status.get(s) in ("ok", "fallback", "stale")]

    @property
    def completeness(self) -> float:
        return len(self.present) / len(self.required)

    @property
    def missing(self) -> list[str]:
        return [s for s in self.required if self.status.get(s) == "missing"]

    @property
    def stale(self) -> list[str]:
        return [s for s in self.required if self.status.get(s) == "stale"]

    @property
    def fallback(self) -> list[str]:
        return [s for s in self.required if self.status.get(s) == "fallback"]

    def view(self, allowed: list[str]) -> "AgentView":
        return AgentView(self, allowed)


class AgentView:
    """Read-only window onto the context. Reading a source outside `allowed` raises."""

    def __init__(self, snapshot: ContextSnapshot, allowed: list[str]):
        self._snap, self.allowed = snapshot, list(allowed)

    def get(self, source: str):
        if source not in self.allowed:
            raise ContextPermissionError(f"read of '{source}' denied (allowed: {', '.join(self.allowed)})")
        return self._snap.sources.get(source)

    def has(self, source: str) -> bool:
        return source in self.allowed and self._snap.sources.get(source) is not None


class ContextManager:
    """Builds the shared context for one service."""

    @staticmethod
    def load(hotel_data: dict, required: list[str], failures: dict | None = None) -> ContextSnapshot:
        failures = failures or {}
        sources, status, calls = {}, {}, []
        for name in required:
            mode = failures.get(name)
            data = hotel_data.get(name)
            if data is None or mode == "missing":
                calls.append(ToolCall(f"read:{name}", ok=True, note="source returned no data"))
                status[name] = "missing"
                continue
            if mode == "api_failure":
                calls.append(ToolCall(f"read:{name}", ok=False, note="API error: timeout"))
                calls.append(ToolCall(f"read:{name}:cache", ok=True, note="fallback to last cached extract"))
                sources[name], status[name] = data, "fallback"
                continue
            calls.append(ToolCall(f"read:{name}", ok=True))
            age = data.get("as_of_hours", 0) if isinstance(data, dict) else 0
            if mode == "stale" or age > STALE_AFTER_HOURS.get(name, 10**9):
                sources[name], status[name] = data, "stale"
            else:
                sources[name], status[name] = data, "ok"
        return ContextSnapshot(sources=sources, status=status, required=list(required), tool_calls=calls)
