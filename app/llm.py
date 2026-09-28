"""Optional Claude call using only the standard library (no SDK needed)."""
import json, os, urllib.request


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def ask_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    body = {
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.load(r)
    text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    return json.loads(text[text.index("{"): text.rindex("}") + 1])
