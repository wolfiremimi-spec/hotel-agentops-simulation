"""Generic Gemini tool-calling loop (REST generateContent). The model plans and explains; tools do the work."""
from __future__ import annotations

import json

import requests

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]


class AgentError(Exception):
    pass


def _reason(r) -> str:
    """Google's own error message (never contains the key), shortened."""
    try:
        msg = (r.json().get("error") or {}).get("message") or ""
    except ValueError:
        msg = r.text or ""
    return " ".join(msg.split())[:220]


THINKING_BUDGET = 512      # short reasoning: these are bounded, well-specified tasks; long thinking only adds seconds


def _body(contents, system, declarations, force, thinking):
    gen = {"temperature": 0.2, "maxOutputTokens": 8192}
    if thinking:
        gen["thinkingConfig"] = {"thinkingBudget": THINKING_BUDGET}
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
            "tools": [{"functionDeclarations": declarations}], "generationConfig": gen}
    if force:                                            # answer with this function now, no extra round trips
        body["toolConfig"] = {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [force]}}
    return body


def call_model(contents, system, declarations, api_key, models, state, force=None):
    tried, busy, last = [], False, ""
    plain = state.setdefault("plain_models", [])       # models that rejected the speed settings: call them plainly
    for model in dict.fromkeys([m for m in [state.get("model")] + list(models) if m]):
        tried.append(model)
        try:
            for attempt in (0, 1):
                fast = model not in plain
                r = requests.post(f"{API_ROOT}/{model}:generateContent", timeout=60,
                                  headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                                  json=_body(contents, system, declarations, force if fast else None, fast))
                if r.status_code == 400 and fast and attempt == 0:
                    plain.append(model)                  # e.g. a model without thinking control: retry without
                    continue
                break
        except requests.RequestException as ex:
            last = f"could not reach the model service ({type(ex).__name__})"
            continue
        if r.status_code in (401, 403):
            raise AgentError("The AI key was rejected (" + (_reason(r) or f"HTTP {r.status_code}") + "). "
                             "The site owner needs to check GEMINI_API_KEY in the app's Secrets.")
        if r.status_code >= 400:                                 # retired model, quota, overload or a model-specific
            busy = busy or r.status_code in (429, 503)           # request error: try the next model
            last = f"{model}: HTTP {r.status_code} {_reason(r)}".strip()
            if state.get("model") == model:
                state.pop("model", None)
            continue
        state["model"] = model
        return r.json()
    if busy:
        raise AgentError("The AI service is busy right now (free-tier limit). Please wait a minute and try again.")
    raise AgentError("No Gemini model answered. Last error: " + (last or "none") + " (tried: " + ", ".join(tried) + ").")


def run(question, history, system, declarations, tools, api_key, models=FALLBACK_MODELS, state=None, max_rounds=6):
    """Appends to `history` (Gemini contents). Returns (answer, steps). Raises AgentError; caller restores history."""
    state = state if state is not None else {}
    history.append({"role": "user", "parts": [{"text": question}]})
    steps = []
    for _ in range(max_rounds):
        data = call_model(history, system, declarations, api_key, models, state)
        cands = data.get("candidates") or []
        if not cands or not cands[0].get("content", {}).get("parts"):
            reason = (cands[0].get("finishReason") if cands else None) or data.get("promptFeedback", {}).get("blockReason")
            if reason == "MAX_TOKENS":
                raise AgentError("The answer ran too long. Try a narrower question.")
            raise AgentError(f"The model returned no answer ({reason or 'unknown reason'}). Try rephrasing.")
        content = cands[0]["content"]
        content.setdefault("role", "model")
        history.append(content)                                  # verbatim: keeps any thought signatures
        calls = [p["functionCall"] for p in content["parts"] if "functionCall" in p]
        if not calls:
            text = "".join(p.get("text", "") for p in content["parts"] if not p.get("thought")).strip()
            return text or "I could not produce an answer for that. Try rephrasing.", steps
        parts = []
        for call in calls:
            name, args = call.get("name"), call.get("args") or {}
            fn = tools.get(name)
            try:
                result = fn(args) if fn else {"error": f"Unknown tool {name}"}
            except Exception as ex:                              # a tool failed: tell the model, don't crash
                result = {"error": f"{type(ex).__name__}: {ex}"}
            result = json.loads(json.dumps(result, default=str))  # dates, numpy numbers etc. become plain JSON
            steps.append({"tool": name, "args": args, "result": result})
            fr = {"name": name, "response": {"result": result}}
            if call.get("id"):
                fr["id"] = call["id"]
            parts.append({"functionResponse": fr})
        history.append({"role": "user", "parts": parts})
    return "I ran out of steps before finishing. Try a narrower question.", steps
