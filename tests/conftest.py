import json
import os
from pathlib import Path

import httpx
import pytest

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
ASSESSMENT_ID = os.getenv("ASSESSMENT_ID", "local")

# test function name -> (stable check id, display name, points)
CHECKS = {
    "test_tool_registered": ("tool-registered", "Your new tool is registered with the agent", 1),
    "test_tool_works": ("tool-works", "Your tool works with valid arguments", 1),
    "test_tool_error_contract": ("tool-errors", "Your tool reports bad input as ERROR[CODE]", 1),
    "test_tool_metric": ("tool-metric", "Your tool records its own metric", 1),
    "test_tool_log": ("tool-log", "Your tool writes a structured log line", 1),
    "test_baseline_intact": ("baseline", "Upload, ingest, search and citations still work", 1),
    "test_shared_kb": ("shared-kb", "A document uploaded in one chat is searchable from another", 1),
    "test_kb_persists_after_restart": ("kb-persists", "The shared knowledge base survives a restart", 1),
    "test_memory_persists_after_restart": ("sqlite-memory", "Chat memory survives a restart (SQLite checkpointer)", 2),
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
