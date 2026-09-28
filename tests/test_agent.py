import json, os, tempfile, unittest
from app import agent
from app.memory import Memory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class T(unittest.TestCase):
    def setUp(self):
        self.mem = Memory(os.path.join(tempfile.mkdtemp(), "t.db"), os.path.join(ROOT, "data", "seed_incidents.json"))
        self.sc = json.load(open(os.path.join(ROOT, "data", "scenarios.json")))

    def test_scenarios_match_expected_past_incident(self):
        for sc, expected in zip(self.sc, ["INC-101", "INC-102", "INC-103"]):
            r = agent.analyze(self.mem, sc["logs"])
            self.assertEqual(r["matches"][0]["id"], expected, sc["name"])

    def test_memory_learns_new_incident(self):
        self.mem.add({"title": "Quantum flux capacitor overload", "service": "flux-svc", "symptoms": "flux capacitor overload zorblax",
                      "root_cause": "zorblax misconfig", "resolution": ["reset zorblax"], "tags": [], "ttr_minutes": 10, "agent_assisted": 1})
        r = agent.analyze(self.mem, "alert: zorblax overload on flux capacitor")
        self.assertEqual(r["matches"][0]["title"], "Quantum flux capacitor overload")


if __name__ == "__main__":
    unittest.main()
