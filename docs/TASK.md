# The assessment: four tasks, one score

You get the working Document Agent. You **extend** it. The autograder runs on every push to `main`, with a scripted
model (no API key needed on GitHub), so results are deterministic. Run it yourself first: `bash scripts/local_eval.sh`.

## Score: 10 points, pass = all 10 (all four tasks are required; your best score is kept)
| Check id | Points | What it proves |
|---|---|---|
| `tool-registered` | 1 | your new tool is part of the agent (`/health` lists it) |
| `tool-works` | 1 | valid arguments work |
| `tool-errors` | 1 | invalid arguments return `ERROR[CODE]: ... Next step: ...` |
| `tool-metric` | 1 | your tool records **its own** OpenTelemetry metric |
| `tool-log` | 1 | your tool writes a structured log line per call (ok and error) |
| `baseline` | 1 | nothing broke: upload, ingest, search, citations, 422 for bad files |
| `shared-kb` | 1 | a document uploaded in chat A is searchable from chat B |
| `kb-persists` | 1 | the shared knowledge base survives a container restart |
| `sqlite-memory` | 2 | chat memory survives a container restart (SQLite checkpointer) |

Starting score: 1/10 (only `baseline`). Each check is independent; partial credit is kept.

## Task 1: add a tool
Edit `src/app/custom_tools.py`. Write a function with `@tool`, return it from `build_custom_tools(kb)`.
- The docstring is the prompt: say **when** to use it and describe each argument.
- It must work **offline and deterministically** (the grader has no internet): no live web APIs in the graded path.
- Invalid input must raise `ToolException("ERROR[CODE]: what happened. Next step: what to do.")` and your tool must have
  `handle_tool_error = True` (see `src/app/kb/tools.py` for the pattern, `src/app/errors.py` for codes).
- Ideas: knowledge-base statistics, a unit/currency converter with a fixed table, a keyword lister for one document,
  a "compare two documents" helper, a reading-time estimator.

## Task 2: observability for your tool
- **Metric**: create your own instrument (`metrics.get_meter("agent").create_counter("yourtool.calls")`, or a histogram) and
  record on **every** call. Do not reuse built-in names (`tool.calls`, `llm.tokens`, ...). Prometheus will show it as `agent_yourtool_calls_total`.
- **Log**: one line per call: `log.info("your_event", tool="your_tool", status="ok"|"error", duration_ms=<number>)`
  (`from app.telemetry import log`). Log `status="error"` when you reject input. Never log prompts or document text.
- **Declare** them in `src/app/assessment.json`:
  ```json
  {"tool": "your_tool", "example_args": {"x": 1}, "invalid_args": {"x": -1}, "metric": "yourtool.calls", "log_event": "your_event"}
  ```
  `example_args` must succeed, `invalid_args` must be rejected.
- **Grafana** (not auto-graded, mentioned in review): add `src/app/dashboards/yours.json` with a panel for your metric and one for your
  logs (`{service_name="extraction-agent"} | json | event="your_event"`). Docker mounts it into Grafana under the folder *Student*.
  Tip: build the panel in Grafana, then *Share > Export > JSON*.
- Check yourself: `curl localhost:8000/debug/telemetry` shows your metric and log events after you used the tool.

## Task 3: SQLite chat memory
`src/app/persistence.py` returns an in-memory checkpointer, so a restart erases every conversation. Replace it with a
SQLite-backed one on the file in `CHECKPOINT_DB`. Hints are in the file. Test it by hand:
chat, `docker compose restart api`, then ask "what did I just say?" in the same chat thread.

## Task 4: one shared knowledge base
Today a document belongs to the chat session that uploaded it. Make the knowledge base **shared**: a document uploaded in any
chat is searchable (and listed in the agent's knowledge-base summary) in every other chat. Chat **memory** stays per thread.
Find every place that uses the session id for the knowledge base: `grep -rn session_id src/app`. Think about:
the ingestion tool, the search tool, the summary the agent reads each turn, the `/kb/{session_id}` endpoints, de-duplication.
The index lives in Qdrant and SQLite on disk, so it also survives restarts.

## How the grader drives your app (so you can reproduce it)
In CI the API runs with `LLM_MODE=fake` (a scripted model, `src/app/fake_llm.py`). You can use it by hand too:
```bash
LLM_MODE=fake EMBEDDER=fake ASSESSMENT_DEBUG=1 docker compose up -d --build api     # scripted model; then:
curl -s localhost:8000/agent -H 'content-type: application/json' \
  -d '{"message":"call your_tool {\"x\": 1}","thread_id":"t1"}'
```
Messages the scripted model understands: `ingest <file_id>`, `search <text>`, `call <tool> <json args>`, `recall`.
The grader: runs phase 1, **restarts the container with the same data volume**, runs phase 2. Your data must live under `/data`
(see `CHECKPOINT_DB`, `KB_DB`, `QDRANT_URL=path:/data/qdrant` in the Dockerfile `runner` target).

## Rules
- Edit only `src/app/` (and README.md, .gitignore). Everything else is locked and compared byte for byte.
- You may not add dependencies (`pyproject.toml` is locked). Everything you need is installed: `langgraph-checkpoint-sqlite`, `aiosqlite`, OpenTelemetry, ...
- Your own work: solutions are compared across students.
- Do not hard-code the grader's behavior (for example detecting `LLM_MODE=fake`); reviewers read the code.
