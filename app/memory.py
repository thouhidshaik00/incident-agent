"""Incident memory: SQLite storage + TF-IDF retrieval + feedback-based learning."""
import json, math, os, re, sqlite3, threading, time
from collections import Counter

STOP = set("the a an and or of to in on at is are was were for with from by this that it as be after before during not no".split())
COLS = ["id", "title", "service", "severity", "symptoms", "root_cause", "resolution", "runbook",
        "ttr_minutes", "tags", "agent_assisted", "helpful", "unhelpful", "created_at"]


def tokens(text: str):
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1 and not w.isdigit()]
    return words + [a + "_" + b for a, b in zip(words, words[1:])]


class Memory:
    def __init__(self, path, seed_path):
        self.seed_path = seed_path
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS incidents(
            id TEXT PRIMARY KEY, title TEXT, service TEXT, severity TEXT, symptoms TEXT, root_cause TEXT,
            resolution TEXT, runbook TEXT, ttr_minutes INTEGER, tags TEXT, agent_assisted INTEGER DEFAULT 0,
            helpful INTEGER DEFAULT 0, unhelpful INTEGER DEFAULT 0, created_at REAL)""")
        if self.db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0:
            self.seed()

    def seed(self):
        with self.lock:
            self.db.execute("DELETE FROM incidents")
            for i, inc in enumerate(json.load(open(self.seed_path))):
                inc.setdefault("created_at", time.time() - (100 - i) * 86400)
                self._insert(inc)
            self.db.commit()

    def _insert(self, inc):
        self.db.execute(
            "INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (inc["id"], inc["title"], inc["service"], inc.get("severity", "SEV3"), inc.get("symptoms", ""),
             inc.get("root_cause", ""), json.dumps(inc.get("resolution", [])), inc.get("runbook", ""),
             int(inc.get("ttr_minutes", 0)), json.dumps(inc.get("tags", [])), int(inc.get("agent_assisted", 0)),
             int(inc.get("helpful", 0)), int(inc.get("unhelpful", 0)), inc.get("created_at", time.time())))

    def all(self):
        rows = self.db.execute(f"SELECT {','.join(COLS)} FROM incidents ORDER BY created_at DESC").fetchall()
        out = []
        for r in rows:
            d = dict(zip(COLS, r))
            d["resolution"] = json.loads(d["resolution"])
            d["tags"] = json.loads(d["tags"])
            out.append(d)
        return out

    def add(self, inc):
        with self.lock:
            n = self.db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            inc["id"] = f"INC-{101 + n}"
            self._insert(inc)
            self.db.commit()
        return inc["id"]

    def feedback(self, inc_id, helpful: bool):
        col = "helpful" if helpful else "unhelpful"
        with self.lock:
            self.db.execute(f"UPDATE incidents SET {col}={col}+1 WHERE id=?", (inc_id,))
            self.db.commit()

    def search(self, query, k=3, boost_tags=()):
        docs = self.all()
        texts = [" ".join([d["title"], d["service"], d["symptoms"], d["root_cause"],
                           " ".join(d["tags"]) * 2, " ".join(d["resolution"])]) for d in docs]
        toks = [Counter(tokens(t)) for t in texts]
        df = Counter(w for t in toks for w in t)
        n = len(docs)
        idf = lambda w: math.log((n + 1) / (df.get(w, 0) + 1)) + 1

        def vec(c): return {w: c * idf(w) for w, c in c.items()}
        def norm(v): return math.sqrt(sum(x * x for x in v.values())) or 1.0

        q = vec(Counter(tokens(query)))
        qn = norm(q)
        scored = []
        for d, t in zip(docs, toks):
            v = vec(t)
            cos = sum(x * v.get(w, 0) for w, x in q.items()) / (qn * norm(v))
            tag_hits = len(set(boost_tags) & set(d["tags"]))
            learn = max(0.7, min(1.4, 1 + 0.1 * (d["helpful"] - d["unhelpful"])))  # learning from feedback
            score = (cos + 0.06 * min(tag_hits, 3)) * learn
            scored.append((score, d))
        scored.sort(key=lambda x: -x[0])
        return [dict(d, score=round(s, 3)) for s, d in scored[:k] if s > 0.02]

    def stats(self):
        docs = self.all()
        manual = [d["ttr_minutes"] for d in docs if not d["agent_assisted"]]
        assisted = [d["ttr_minutes"] for d in docs if d["agent_assisted"]]
        avg = lambda x: round(sum(x) / len(x), 1) if x else None
        h = sum(d["helpful"] for d in docs); u = sum(d["unhelpful"] for d in docs)
        return {"total": len(docs), "avg_ttr_manual": avg(manual), "avg_ttr_assisted": avg(assisted),
                "assisted_count": len(assisted), "helpful": h, "unhelpful": u,
                "helpful_rate": round(100 * h / (h + u)) if h + u else None}
