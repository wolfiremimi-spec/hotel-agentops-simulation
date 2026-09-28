"""Generic Gemini tool-calling loop (REST generateContent). The model plans and explains; tools do the work."""
from __future__ import annotations

import requests

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]


class AgentError(Exception):
    pass


def call_model(contents, system, declarations, api_key, models, state):
    tried, busy = [], False
    for model in dict.fromkeys([m for m in [state.get("model")] + list(models) if m]):
        tried.append(model)
        try:
            r = requests.post(f"{API_ROOT}/{model}:generateContent", timeout=60,
                              headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                              json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                                    "tools": [{"functionDeclarations": declarations}],
                                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1200}})
        except requests.RequestException as ex:
            raise AgentError(f"Could not reach the model service ({type(ex).__name__}).") from ex
        if r.status_code in (404, 429):
            busy = busy or r.status_code == 429
            continue                                             # retired, or not in this key's quota: try the next one
        if r.status_code in (401, 403):
            raise AgentError("The AI key was rejected. The site owner needs to check GEMINI_API_KEY.")
        if r.status_code >= 400:
            raise AgentError(f"The model service returned an error (HTTP {r.status_code}).")
        state["model"] = model
        return r.json()
    if busy:
        raise AgentError("The free AI quota is busy right now. Please wait a minute and try again.")
    raise AgentError("No available Gemini model answered (tried: " + ", ".join(tried) + ").")


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
            steps.append({"tool": name, "args": args, "result": result})
            fr = {"name": name, "response": {"result": result}}
            if call.get("id"):
                fr["id"] = call["id"]
            parts.append({"functionResponse": fr})
        history.append({"role": "user", "parts": parts})
    return "I ran out of steps before finishing. Try a narrower question.", steps
