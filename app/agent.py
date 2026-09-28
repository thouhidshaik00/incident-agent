"""Incident Response Agent: detect signals -> recall similar incidents -> diagnose -> act."""
import re, statistics
from . import llm

SIGNALS = [
    (r"too many (clients|connections)|connection (is not available|pool)|pool exhausted|acquiring connection", "Database connection pool exhaustion", ["connection-pool", "database"]),
    (r"oomkilled|outofmemory|out of memory|exit code 137", "Out-of-memory kills", ["oom", "memory"]),
    (r"crashloopbackoff|back-off restarting", "Crash-looping containers", ["crashloop", "kubernetes"]),
    (r"deployed v?\d|rollout|release|config push", "Recent deploy / change", ["deploy", "rollback"]),
    (r"x509|certificate|ssl handshake|tls", "TLS / certificate problem", ["certificate", "tls", "x509"]),
    (r"no space left|disk usage|100% on", "Disk full", ["disk", "storage"]),
    (r"redis|cache miss|thundering", "Cache layer trouble", ["redis", "cache"]),
    (r"\b502\b|bad gateway|no live upstreams", "Gateway 502s", ["502", "nginx"]),
    (r"\b504\b|gateway timeout|origin", "Origin / gateway timeouts", ["504", "cdn"]),
    (r"name resolution|unknownhost|coredns", "DNS resolution failures", ["dns", "coredns"]),
    (r"consumer lag|rebalance", "Streaming consumer lag", ["kafka", "lag"]),
    (r"replication lag|replica", "Replica lag", ["replica"]),
    (r"\b503\b|5xx|latency|timed out|timeout", "Elevated errors / latency", ["latency", "timeout", "503"]),
]


def detect_signals(text):
    found, tags = [], []
    for pat, label, t in SIGNALS:
        m = re.search(pat, text, re.I)
        if m:
            line = next((l for l in text.splitlines() if re.search(pat, l, re.I)), m.group(0))
            found.append({"label": label, "evidence": line.strip()[:160]})
            tags += t
    return found, tags


def guess_service(text):
    m = re.search(r"service[=:]\s*([\w-]+)", text) or re.search(r"\[([\w-]+-(?:api|service|worker|gateway|connector|frontend))\]", text)
    return m.group(1) if m else "unknown-service"


def analyze(memory, text):
    signals, tags = detect_signals(text)
    matches = memory.search(text, k=3, boost_tags=tags)
    service = guess_service(text)
    top = matches[0] if matches else None
    second = matches[1]["score"] if len(matches) > 1 else 0
    conf = min(96, int(45 + top["score"] * 110 + (top["score"] - second) * 100)) if top else 10
    ttrs = [m["ttr_minutes"] for m in matches if m["score"] > 0.15]
    eta = int(statistics.median(ttrs) * 0.35) if ttrs else None  # memory-guided fixes are faster than cold starts

    result = {"service": service, "signals": signals, "matches": matches, "tags": tags,
              "eta_minutes": eta, "mode": "offline"}

    if top:
        result["diagnosis"] = {"summary": f"Pattern matches {top['id']} ({top['title']}).",
                               "root_cause": top["root_cause"], "confidence": conf,
                               "severity": top["severity"]}
        result["steps"] = list(top["resolution"])
        result["runbook"] = top["runbook"]
    else:
        result["diagnosis"] = {"summary": "No similar incident in memory.", "root_cause": "Unknown - investigate manually",
                               "confidence": 10, "severity": "SEV3"}
        result["steps"] = ["Check recent deploys and config changes", "Inspect error logs and saturation metrics", "Escalate to on-call lead"]
        result["runbook"] = ""

    d = result["diagnosis"]
    result["slack_update"] = (f":rotating_light: [{d['severity']}] {service} incident. Suspected cause: {d['root_cause']}. "
                              f"Mitigation starting per {result['runbook'] or 'manual triage'}"
                              f"{f', ETA ~{eta} min' if eta else ''}. Next update in 15 min.")

    if llm.available() and matches:
        try:
            ctx = "\n\n".join(f"[{m['id']}] {m['title']}\nSymptoms: {m['symptoms']}\nRoot cause: {m['root_cause']}\n"
                              f"Fix: {'; '.join(m['resolution'])}\nTTR: {m['ttr_minutes']} min" for m in matches)
            out = llm.ask_json(
                "You are an SRE incident commander with memory of past incidents. Reply ONLY with JSON: "
                '{"summary": str, "root_cause": str, "confidence": int 0-100, "severity": "SEV1|SEV2|SEV3", '
                '"steps": [str], "slack_update": str}. Ground the answer in the past incidents and cite their IDs. '
                "Adapt steps to the current alert (different service names/values), do not copy blindly.",
                f"CURRENT ALERT / LOGS:\n{text}\n\nSIMILAR PAST INCIDENTS:\n{ctx}")
            result["diagnosis"] = {"summary": out["summary"], "root_cause": out["root_cause"],
                                   "confidence": int(out["confidence"]), "severity": out["severity"]}
            result["steps"] = out["steps"]
            result["slack_update"] = out["slack_update"]
            result["mode"] = "claude"
        except Exception as e:  # never fail the demo: fall back to offline result
            result["llm_error"] = str(e)[:200]
    return result
