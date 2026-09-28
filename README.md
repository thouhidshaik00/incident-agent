# IncidentMemory - AI Incident Response Agent with memory

**Problem:** When production breaks, engineers waste the first 20-40 minutes rediscovering fixes the team already found in earlier incidents. Knowledge sits in old Slack threads and post-mortems nobody reads at 3 AM.

**Solution:** An agent that remembers every past incident (symptoms, root cause, fix, runbook, time to resolve). When a new alert arrives it recalls the most similar incidents, diagnoses the likely root cause with a confidence score, proposes an actionable fix checklist, drafts the status update, and estimates time to resolve. After the fix, the engineer closes the loop and the agent learns.

## Run

```bash
cd incident-agent
python3 -m app.server            # Windows: python -m app.server
# open http://localhost:8000
```

Optional Claude reasoning (recommended for the demo):
```bash
export ANTHROPIC_API_KEY=sk-ant-...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python3 -m app.server
```
Run tests: `python3 -m unittest discover -s tests -t .`

## How it works
1. `app/memory.py` - SQLite store + TF-IDF vector retrieval. Feedback (helpful / not helpful) re-ranks past incidents = learning.
2. `app/agent.py` - signal detection (regex), memory recall, diagnosis, action plan, Slack draft. With an API key, Claude reasons over the recalled incidents and adapts the fix to the new service.
3. `app/server.py` - stdlib HTTP API + UI. `static/index.html` - dashboard.

## 3-minute demo script
1. Show the memory panel: 10 past incidents, average fix time.
2. Click **Inventory API timeouts** -> Analyze. Point out: never seen `inventory-api` before, yet it recalls INC-101 (pool exhaustion), gives the fix and ETA.
3. Enter title, minutes = 9, click **Save to memory**. Stats show assisted fix time vs manual.
4. Click **Billing calls all failing** -> cert expiry recalled from INC-103.
5. Close: "Every team at a company gets a memory that never forgets and never sleeps."

## Ideas to extend (mention in Q&A)
Pagerduty/Datadog webhook ingestion, Slack bot, embeddings (pgvector), auto-run safe runbook steps behind approval.
