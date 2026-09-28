"""Loads the project parameters (extracted from the workbook) and the modeled scenario."""
from __future__ import annotations

import copy
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def load_parameters(path: Path | None = None) -> dict:
    return json.loads((path or DATA / "project_parameters.json").read_text())


def load_scenario(name: str = "scenario_d0418.json") -> dict:
    return json.loads((DATA / name).read_text())


def value(params: dict, key: str):
    """Return a parameter's value (every parameter is stored as {value, source})."""
    return params[key]["value"]


def thresholds(params: dict) -> dict:
    return {k: (v["value"], v["test"]) for k, v in params["readiness_thresholds"].items()}


def latest_evidence(params: dict) -> dict:
    ev = {k: v["value"] for k, v in params["latest_gate_evidence"].items()}
    return ev


def modified(scenario: dict, **changes) -> dict:
    """Copy of a scenario with nested changes, e.g. modified(s, hotel_data__pms_occupancy=None)."""
    s = copy.deepcopy(scenario)
    for dotted, new in changes.items():
        keys = dotted.split("__")
        node = s
        for k in keys[:-1]:
            node = node[k]
        if new is None:
            node.pop(keys[-1], None)
        else:
            node[keys[-1]] = new
    return s
