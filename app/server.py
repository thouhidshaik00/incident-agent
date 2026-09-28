"""Tiny HTTP server (standard library only). Run: python -m app.server"""
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from . import agent, llm
from .memory import Memory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = Memory(os.path.join(ROOT, "data", "memory.db"), os.path.join(ROOT, "data", "seed_incidents.json"))
SCENARIOS = json.load(open(os.path.join(ROOT, "data", "scenarios.json")))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(open(os.path.join(ROOT, "static", "index.html"), "rb").read(), ctype="text/html; charset=utf-8")
        if self.path == "/api/incidents": return self.send(MEM.all())
        if self.path == "/api/stats": return self.send(dict(MEM.stats(), llm=llm.available()))
        if self.path == "/api/scenarios": return self.send(SCENARIOS)
        self.send({"error": "not found"}, 404)

    def do_POST(self):
        try:
            data = self.body()
            if self.path == "/api/analyze":
                return self.send(agent.analyze(MEM, data.get("logs", "")))
            if self.path == "/api/resolve":
                inc = {"title": data["title"], "service": data.get("service", "unknown"), "severity": data.get("severity", "SEV2"),
                       "symptoms": data.get("logs", "")[:1500], "root_cause": data["root_cause"],
                       "resolution": [s for s in data.get("resolution", []) if s.strip()], "runbook": data.get("runbook", ""),
                       "ttr_minutes": int(data.get("ttr_minutes", 0)), "tags": data.get("tags", []), "agent_assisted": 1}
                new_id = MEM.add(inc)
                if data.get("matched_id") and data.get("helpful") is not None:
                    MEM.feedback(data["matched_id"], bool(data["helpful"]))
                return self.send({"saved": new_id})
            if self.path == "/api/reset":
                MEM.seed()
                return self.send({"ok": True})
            self.send({"error": "not found"}, 404)
        except Exception as e:
            self.send({"error": str(e)}, 400)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Incident Response Agent -> http://localhost:{port}  (Claude: {'ON' if llm.available() else 'OFF, offline mode'})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
