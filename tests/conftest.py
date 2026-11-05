import json
import os
from pathlib import Path

import httpx
import pytest

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
ASSESSMENT_ID = os.getenv("ASSESSMENT_ID", "local")

# test function name -> (stable check id, display name, points)
CHECKS = {
    # task 1: the agent definition
    "test_agent_tools": ("agent-tools", "1.1 The agent has exactly the 21 required tools", 1),
    "test_agent_prompt": ("agent-prompt", "1.2 The dynamic prompt shows the current knowledge base to the model", 1),
    "test_baseline_intact": ("baseline", "1.3 Context wiring: upload, ingest, search, citations and SQL work end to end", 1),
    # task 2: async
    "test_async_runtime": ("async-tools", "2.1 get_weather, web_fetch, sql_query, search_knowledge_base are async tools", 1),
    "test_async_static": ("async-blocking", "2.2 no blocking calls inside those async tools", 1),
    # task 3: chat memory
    "test_memory_live": ("memory-live", "3.1 The checkpointer is integrated: a thread remembers, another thread does not", 1),
    "test_memory_persists_after_restart": ("sqlite-memory", "3.2 Chat memory survives a restart (SQLite)", 1),
    # task 4: migration, users, per-user knowledge base
    "test_migration_roundtrip": ("migration-roundtrip", "4.1 Alembic: upgrade creates the tables, downgrade drops them, upgrade again", 1),
    "test_migration_schema": ("migration-schema", "4.1 The running database is at the migration revision with the required columns", 1),
    "test_users_register_login": ("users-login", "4.2 POST /users and POST /login (409, 422, 401 cases, hashed passwords)", 1),
    "test_users_manage": ("users-manage", "4.3 GET /me and POST /logout (the token is revoked)", 1),
    "test_users_delete": ("users-delete", "4.3 DELETE /users/me removes the account and its knowledge base", 1),
    "test_users_auth": ("users-auth", "4.3 Every protected route answers 401 without a valid token", 1),
    "test_user_kb_shared_across_chats": ("user-kb", "4.4 One knowledge base per user, shared by all of their chats", 1),
    "test_user_isolation": ("user-isolation", "4.5 Other users cannot see, search, delete or reach it (403 on foreign threads)", 1),
    "test_user_state_persists_after_restart": ("user-persists", "4.6 Users, tokens, threads and knowledge bases survive a restart", 1),
    # task 5: new tools + observability
    "test_kb_stats": ("kb-stats", "5.1 kb_stats: numbers, error contract, metric and log", 1),
    "test_outline_output": ("outline-output", "5.2 document_outline returns the documented outline (levels, order, pages)", 2),
    "test_outline_errors": ("outline-errors", "5.2 document_outline: ERROR[UNKNOWN_DOCUMENT], never another user's document", 1),
    "test_outline_metric": ("outline-metric", "5.3 outline.calls counter on every call (ok and error)", 1),
    "test_outline_log": ("outline-log", "5.3 document_outline_done structured log line on every call", 1),
    # task 6: knowledge-base management tools
    "test_delete_works": ("delete-works", "6.1 delete_document removes the document, only for its owner", 1),
    "test_delete_errors": ("delete-errors", "6.1 delete_document: ERROR[UNKNOWN_DOCUMENT], never another user's document", 1),
    "test_update_works": ("update-works", "6.2 update_document replaces the content under the same name", 1),
    "test_update_errors": ("update-errors", "6.2 update_document: error codes, old version untouched on failure", 1),
    # task 7: notes and tasks MCP server, per-user auth
    "test_mcp_tools": ("mcp-tools", "7.1 The eight MCP tools work through the agent, as the logged-in user (token forwarded)", 1),
    "test_mcp_auth": ("mcp-auth", "7.2 The MCP server rejects missing, malformed and unknown tokens", 2),
    "test_mcp_isolation": ("mcp-isolation", "7.2 Notes and tasks are private per user", 1),
    "test_mcp_task_lifecycle": ("mcp-lifecycle", "7.3 Task lifecycle: statuses, filtering, summary, error codes", 1),
    "test_mcp_notes": ("mcp-notes", "7.3 Notes: add, list, delete, error codes", 1),
    "test_mcp_token_hygiene": ("mcp-token-hygiene", "7.4 The token is never in a tool argument, step, answer or log line", 1),
    "test_mcp_persists_after_restart": ("mcp-persists", "7.5 Notes and tasks survive a restart of the MCP server and the API", 1),
}

RESULTS = Path("results")
_outcomes: dict[str, bool] = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "phase1: runs before the container restart")
    config.addinivalue_line("markers", "phase2: runs after the container restart")


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as c:
        yield c


def pytest_runtest_logreport(report):
    if report.when == "call":
        _outcomes[report.nodeid.split("::")[-1]] = report.passed
    elif report.when in ("setup", "teardown") and report.failed:
        _outcomes[report.nodeid.split("::")[-1]] = False


def pytest_sessionfinish(session, exitstatus):
    """Two pytest runs (before / after a container restart) share results/outcomes.json; summary.json merges both."""
    RESULTS.mkdir(exist_ok=True)
    store = RESULTS / "outcomes.json"
    merged = {**(json.loads(store.read_text()) if store.exists() else {}), **_outcomes}
    store.write_text(json.dumps(merged))
    checks = [
        {"id": cid, "name": name, "passed": merged.get(func, False), "points": pts}
        for func, (cid, name, pts) in CHECKS.items()
    ]
    summary = {
        "assessmentId": ASSESSMENT_ID,
        "commitSha": os.getenv("GITHUB_SHA", ""),
        "totalPoints": sum(c["points"] for c in checks),
        "earnedPoints": sum(c["points"] for c in checks if c["passed"]),
        "checks": checks,
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2))
