"""Black-box tests: they only talk HTTP to your running API (a scripted model replaces the LLM, see src/app/fake_llm.py).

phase1 runs first; then the CI restarts your container; then phase2 checks that state survived.
Run them yourself against `docker compose up`:   BASE_URL=http://localhost:8000 uv run pytest tests/ -m phase1
(the restart-dependent tests need the restart too: `bash scripts/local_eval.sh` does the whole thing exactly like CI)
"""
import json
import re
import uuid
from pathlib import Path

import pytest

RESULTS = Path("results")
STATE = RESULTS / "state.json"

BASELINE_TOOLS = {"get_weather", "web_fetch", "sql_query", "make_chart", "openml_search", "openml_download",
                  "pandas_query", "ingest_document", "search_knowledge_base", "add_note", "list_notes"}
BASELINE_METRICS = {"http.requests", "http.request.duration", "llm.requests", "llm.tokens", "llm.cost.usd", "llm.duration",
                    "tool.calls", "tool.duration", "ingest.documents", "ingest.duration", "ocr.pages", "kb.searches", "run.steps"}
BASELINE_EVENTS = {"http_request", "tool_start", "tool_end", "llm_call", "llm_error", "agent_done", "ingest_done", "ingest_failed",
                   "file_uploaded", "startup_complete", "request_failed", "structured_output_retry", "segment_window_fallback"}


def rand() -> str:
    return uuid.uuid4().hex[:8]


def ask(client, thread: str, message: str) -> dict:
    r = client.post("/agent", json={"message": message, "thread_id": thread})
    assert r.status_code == 200, f"/agent returned {r.status_code}: {r.text[:300]}"
    return r.json()


def upload(client, session: str, name: str, text: str) -> str:
    r = client.post("/upload", data={"session_id": session}, files={"file": (name, text.encode())})
    assert r.status_code == 200, f"/upload returned {r.status_code}: {r.text[:300]}"
    return r.json()["file_id"]


def ingest(client, session: str, name: str, text: str) -> dict:
    file_id = upload(client, session, name, text)
    out = ask(client, session, f"ingest {file_id}")
    assert "Ingested" in out["answer"] or "already in the knowledge base" in out["answer"], out["answer"]
    return out


def tool_steps(resp: dict, tool: str) -> list[dict]:
    return [s for s in resp["steps"] if s["tool"] == tool]


def declaration(client) -> dict:
    r = client.get("/debug/assessment")
    assert r.status_code == 200, "GET /debug/assessment failed: is src/app/assessment.json present and valid JSON?"
    d = r.json()
    for key in ("tool", "metric", "log_event"):
        assert d.get(key), f"assessment.json: '{key}' is empty"
    assert isinstance(d.get("example_args"), dict) and isinstance(d.get("invalid_args"), dict)
    assert d["invalid_args"], "assessment.json: 'invalid_args' must be an example that your tool rejects"
    return d


def call_tool(client, decl: dict, args: dict) -> dict:
    return ask(client, f"call-{rand()}", f"call {decl['tool']} {json.dumps(args)}")


# ------------------------------------------------------------------ phase 1 (before the restart)
@pytest.mark.phase1
def test_tool_registered(client):
    health = client.get("/health").json()
    decl = declaration(client)
    assert BASELINE_TOOLS <= set(health["tools"]), "a built-in tool disappeared"
    assert decl["tool"] not in BASELINE_TOOLS, "pick a NEW tool name"
    assert decl["tool"] in health["tools"], f"'{decl['tool']}' is not in /health tools: did you add it to CUSTOM_TOOLS?"


@pytest.mark.phase1
def test_tool_works(client):
    decl = declaration(client)
    out = call_tool(client, decl, decl["example_args"])
    steps = tool_steps(out, decl["tool"])
    assert steps, f"the agent did not run '{decl['tool']}': {out['answer'][:200]}"
    assert steps[0]["result"] and not steps[0]["result"].startswith("ERROR["), steps[0]["result"][:300]


@pytest.mark.phase1
def test_tool_error_contract(client):
    decl = declaration(client)
    out = call_tool(client, decl, decl["invalid_args"])
    steps = tool_steps(out, decl["tool"])
    assert steps, "the agent did not run your tool"
    result = steps[0]["result"]
    assert re.match(r"ERROR\[[A-Z_]+\]: .+Next step: .+", result, re.S), f"expected 'ERROR[CODE]: ... Next step: ...', got: {result[:300]}"


def metric_total(client, name: str) -> float:
    """Sum of everything recorded under one metric name (counter values, or histogram counts)."""
    metrics = client.get("/debug/telemetry").json()["metrics"]
    return sum(p.get("value", p.get("count", 0)) for m in metrics if m["name"] == name for p in m["points"])


def event_count(client, event: str) -> int:
    return sum(1 for line in client.get("/debug/telemetry").json()["logs"] if line.get("event") == event)


@pytest.mark.phase1
def test_tool_metric(client):
    decl = declaration(client)
    metric = decl["metric"]
    assert metric not in BASELINE_METRICS and not metric.startswith("http.server."), f"'{metric}' already exists: add a NEW instrument"
    call_tool(client, decl, decl["example_args"])
    before = metric_total(client, metric)
    assert before > 0, f"metric '{metric}' has no data after calling the tool"
    call_tool(client, decl, decl["example_args"])
    assert metric_total(client, metric) > before, f"metric '{metric}' did not grow with another call: record it on EVERY call"


@pytest.mark.phase1
def test_tool_log(client):
    decl = declaration(client)
    event = decl["log_event"]
    assert event not in BASELINE_EVENTS, f"'{event}' is an existing event: use your own name"
    call_tool(client, decl, decl["example_args"])
    call_tool(client, decl, decl["invalid_args"])
    logs = client.get("/debug/telemetry").json()["logs"]
    mine = [line for line in logs if line.get("event") == event]
    assert mine, f"no log line with event '{event}'. Events seen: {sorted({l.get('event') for l in logs} - BASELINE_EVENTS)}"
    assert all(line.get("tool") == decl["tool"] for line in mine), "log lines need tool=<your tool name>"
    assert {line.get("status") for line in mine} >= {"ok", "error"}, "log status='ok' for good calls and status='error' for rejected ones"
    assert all(isinstance(line.get("duration_ms"), (int, float)) for line in mine), "log lines need a numeric duration_ms"
    before = event_count(client, event)
    call_tool(client, decl, decl["example_args"])
    assert event_count(client, event) > before, "one log line per call, every call"


@pytest.mark.phase1
def test_baseline_intact(client):
    session = f"base-{rand()}"
    token = f"quokka{rand()}"
    out = ingest(client, session, f"notes-{rand()}.md", f"# Quokka facts\n\nThe {token} is a small marsupial found in Australia.\n")
    assert tool_steps(out, "ingest_document")
    found = ask(client, session, f"search {token}")
    result = tool_steps(found, "search_knowledge_base")[0]["result"]
    assert re.search(r"Passage 1 \[[^\]]+\.md › [^\]]+\]", result), f"citation format changed: {result[:300]}"
    assert token in result
    sql = ask(client, session, 'call sql_query {"database": "chinook", "query": "SELECT COUNT(*) AS n FROM Artist"}')
    assert "row_count" in tool_steps(sql, "sql_query")[0]["result"], "the Session 1 SQL tool is broken (are the bundled databases in data/ still there?)"
    r = client.post("/upload", data={"session_id": session}, files={"file": ("malware.exe", b"MZ")})
    assert r.status_code == 422, "unsupported files must be rejected with 422"
    assert client.get(f"/kb/{session}").status_code == 200


@pytest.mark.phase1
def test_shared_kb(client):
    """Uploaded in chat A, found from chat B. (Also stores the token so phase 2 can look for it after a restart.)"""
    token = f"zebracorn{rand()}"
    ingest(client, f"alice-{rand()}", f"zebra-{rand()}.md", f"# Zebra notes\n\nThe secret word is {token} and nothing else.\n")
    other = f"bob-{rand()}"
    kb = client.get(f"/kb/{other}").json()
    assert kb["documents"], "a different chat session sees no documents: the knowledge base is still per session"
    found = ask(client, other, f"search {token}")
    steps = tool_steps(found, "search_knowledge_base")
    assert steps and token in steps[0]["result"], "chat B cannot find chat A's document"
    RESULTS.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    STATE.write_text(json.dumps({**state, "token": token}))


@pytest.mark.phase1
def test_memory_written(client):
    """Not graded by itself: plants a marker in a chat thread for the phase-2 memory check."""
    marker, thread = f"marker{rand()}", f"mem-{rand()}"
    ask(client, thread, f"my marker is {marker}")
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    STATE.write_text(json.dumps({**state, "marker": marker, "thread": thread}))


# ------------------------------------------------------------------ phase 2 (after `docker restart`)
@pytest.mark.phase2
def test_memory_persists_after_restart(client):
    state = json.loads(STATE.read_text())
    out = ask(client, state["thread"], "recall")
    assert state["marker"] in out["answer"], f"the chat forgot its history after a restart. Answer: {out['answer'][:200]}"


@pytest.mark.phase2
def test_kb_persists_after_restart(client):
    state = json.loads(STATE.read_text())
    found = ask(client, f"carol-{rand()}", f"search {state['token']}")
    steps = tool_steps(found, "search_knowledge_base")
    assert steps and state["token"] in steps[0]["result"], "the shared knowledge base lost the document after a restart"
