"""Plain data structures passed between the layers. Nothing here makes decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    ok: bool
    note: str = ""


@dataclass
class AgentOutput:
    agent: str
    question: str
    reads: list[str]
    outputs: dict[str, Any]
    confidence: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """One structured recommendation from the Orchestrator (the 13 fields in the brief, plus details)."""
    decision_id: str
    timestamp: str
    decision_type: str
    service: str
    agents: list[str]
    recommendation: str
    reason: str
    confidence: float
    risk_level: str            # LOW | MEDIUM | HIGH
    reversibility: str         # HIGH | MODERATE | LOW | IRREVERSIBLE
    context_completeness: float
    details: dict[str, Any] = field(default_factory=dict)
    expected_impact: str = ""
    # filled in by governance / approval / execution
    policy_status: str = "NOT CHECKED"
    required_authority: str = ""
    human_approval_required: bool = False
    final_status: str = "PENDING"


@dataclass
class GovernanceResult:
    authority: str             # EXECUTE | MANAGER_APPROVAL | HUMAN_DECISION | RECOMMEND_ONLY | ABSTAIN | BLOCK
    required_authority: str    # human-readable
    human_approval_required: bool
    escalate: bool
    policy_status: str
    rule_trace: list[str]


@dataclass
class HumanDecision:
    choice: str                # approve | modify | reject | more_context | none
    approver: str
    timestamp: str
    final_change_pct: float | None = None
    override: bool = False
    override_reason: str = ""
    note: str = ""


@dataclass
class Outcome:
    execution_status: str
    actual: dict[str, Any]
    waste_impact_kg: float | None = None
    guest_impact: str = ""
    financial_impact_usd: float | None = None
    summary: str = ""
