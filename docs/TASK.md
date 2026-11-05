# The assessment: seven tasks, 34 points

You get a working Document Agent (FastAPI + LangChain agent + Gradio UI + knowledge base + observability stack).
You **integrate**: you do not write the hard parts, you wire them together. The building blocks are provided:

| Provided (read it, do not rewrite it) | What it gives you |
|---|---|
| `src/app/users.py` | `UserStore`: create / login / token lookup / revoke / delete user / claim thread (SQLite, hashed passwords) |
| `src/app/mcp_server/taskstore.py` | `TaskStore`: notes and tasks (todo / in_progress / done) per user, with the error codes |
| `src/app/kb/store.py` | `kb.stats`, `kb.outline`, `kb.delete_document` |
| `src/app/kb/pipeline.py`, `kb/files.py`, `errors.py` | `ingest_file`, upload resolution, `to_tool_exception` |
| `alembic.ini`, `alembic/`, `docker-compose.yml` (`migrate` service) | the Alembic setup and the one-shot migrate task |

The autograder runs on every push to `main` with a scripted model (no API key needed on GitHub), so results are deterministic.
Run it yourself first: `bash scripts/local_eval.sh`. The Gradio UI (`docker compose up`, http://localhost:7860) works as soon as the
tasks are done: register, log in, upload, chat, list and delete documents, ask how a document is organised, manage your tasks and notes.

**Pass = all 34 points.** Every sub-task is graded separately and your best score is kept. The starter scores 0: nothing works end to end until you define the agent (task 1).

## Task 1: define the agent (3 points) · `src/app/agent.py`
`build_agent` is a bare agent (Session 1 tools, one fixed prompt, no memory). Write the real one, step by step (the steps are in its docstring):
- **1.1 tools (1):** one list of exactly these 21 tools: `S1_TOOLS` (7) + `build_kb_tools(kb)` (2) + `await mcp_tools()` (8) + `build_custom_tools(kb)` (4)
- **1.2 dynamic prompt (1):** a `@dynamic_prompt` function that returns `SYSTEM_PROMPT` + the knowledge-base block of the **current user** on every model call
- **1.3 wiring (1):** `middleware=[...]`, `context_schema=Ctx` (tools read `runtime.context`), `checkpointer=checkpointer`; return `agent, tools`

## Task 2: async (2 points) · `src/app/tools_s1.py`, `src/app/kb/tools.py`
A blocking call inside a tool freezes every other request. Convert `get_weather`, `web_fetch`, `sql_query`, `search_knowledge_base` to `async def`; outputs stay identical.
- **2.1 (1):** all four are async tools (`GET /debug/tools`)
- **2.2 (1):** no blocking calls inside them: `web_fetch` downloads with `httpx.AsyncClient`, `sql_query` and `kb.search` run through `asyncio.to_thread` (`scripts/check_async.py` scans the code)

## Task 3: chat memory in SQLite (2 points) · `src/app/persistence.py`, `src/app/main.py`
- **3.1 define and integrate (1):** `open_checkpointer()` yields an `AsyncSqliteSaver` on `CHECKPOINT_DB` (make the folder); the `lifespan` in `main.py` opens it, passes it to `build_agent`, keeps it open until shutdown. A thread remembers; another thread does not.
- **3.2 survives a restart (1):** the grader restarts the container with the same volume and asks the thread again.

## Task 4: migration, users, one knowledge base per user (7 points)
- **4.1 Alembic migration (2) · `src/app/migrations/`:** write ONE migration (`alembic revision -m "create users"`) that creates the tables `users`, `tokens`, `threads` (columns in `users.py`) and drops them in `downgrade`. `docker compose` runs it in the `migrate` service before the API starts; CI runs `upgrade head`, `downgrade base`, `upgrade head` and checks the tables each time. Tables are created by the migration only, never by app code (`GET /debug/schema` shows the database and its revision).
- **4.2 register and log in (1) · `main.py`:** `POST /users` (201; 409 taken; 422 invalid) and `POST /login` (200 with a token; 401). Use `UserStore` through `asyncio.to_thread`.
- **4.3 account endpoints (2) · `main.py`:** `GET /me`, `POST /logout` (204, revokes only that token), `DELETE /users/me` (204; also `kb.reset(user_id)`); a FastAPI dependency turns `Authorization: Bearer <token>` into the current user and answers **401** otherwise. Protect `/agent`, `/upload`, `GET`/`DELETE /kb/{session_id}`, `/me`, `/logout`, `/users/me`.
- **4.4 one knowledge base per user (1):** add `user_id` to `Ctx`; `/agent` passes `Ctx(session_id=..., user_id=...)`; ingest, search, the dynamic prompt and `/kb/...` use the **user id** as the knowledge-base id. All chats of one user share it. Uploaded files stay in the chat folder.
- **4.5 isolation (1):** another user sees none of it. A chat `thread_id` belongs to the first user who uses it (`claim_thread`): `/agent` and `/upload` on someone else's thread answer **403**.
- **4.6 survives a restart (1):** users, tokens, thread claims and knowledge bases are on the volume (SQLite + Qdrant under `/data`).

## Task 5: two tools and their observability (6 points) · `src/app/custom_tools.py`
Write the tool wrappers; the logic is provided. Exact formats are in the file's docstring.
- **5.1 `kb_stats` (1):** `"<D> documents, <S> sections, <C> chunks. Top keywords: a, b."` (from `kb.stats`), `ERROR[INVALID_INPUT]` outside 1..20, counter `kbstats.calls`, log `kb_stats_done`.
- **5.2 `document_outline(doc_name)` (3):** the structure of one document, from `kb.outline`: first line `Outline of '<file>' (<N> sections):`, then `<i>. [L<level>] <heading> (p.<a>-<b>): <summary>` per section (output format: 2 points; `ERROR[UNKNOWN_DOCUMENT]`, also for another user's document: 1 point).
  Ask the real agent: *"How is the handbook organised?"* or *"Which section covers refunds?"*
- **5.3 observability (2):** counter `outline.calls` with `{"status": "ok"|"error"}` on every call (1); log line `document_outline_done` with `tool`, `status`, `duration_ms`, `sections` (0 on error) (1).
  Grafana (reviewed, not auto-graded): `src/app/dashboards/outline.json` with a panel for the counter and one for the logs.

## Task 6: manage the knowledge base with tools (4 points) · `src/app/custom_tools.py`
- **6.1 `delete_document(doc_name)` (2):** removes one document of the **calling user** (`kb.delete_document`); `"Deleted '<name>'. <N> documents left."`; unknown name (or another user's document) is `ERROR[UNKNOWN_DOCUMENT]`; search, the list and the prompt forget it.
- **6.2 `update_document(doc_name, source)` (2):** replaces a document with a newly uploaded version under the same name: ingest the new file first, delete the old one only afterwards; `"Updated '<name>': <S> sections, <C> chunks."`; identical content is `"'<name>' is already up to date."`; unknown document `ERROR[UNKNOWN_DOCUMENT]`; unknown `file_id` `ERROR[FILE_NOT_FOUND]`; a failed update leaves the old document untouched.

## Task 7: notes and tasks MCP server with per-user auth (8 points) · `src/app/mcp_server/server.py`, `src/app/agent.py`, `src/app/context.py`, `src/app/main.py`
The MCP server stores notes and tasks for each user. The storage is provided (`taskstore.py`); you integrate it.
- **7.1 register the eight tools (1):** `add_note`, `list_notes`, `delete_note`, `add_task`, `list_tasks`, `set_task_status`, `delete_task`, `task_summary`, each returning `json.dumps(...)` of what `TaskStore` returned; `TaskError` becomes `ToolError(str(error))`. They work through the agent.
- **7.2 auth in the server (3):** every tool runs as the calling user. Read `Authorization: Bearer <token>` from the HTTP request (`ctx.request_context.request.headers`, `ctx: Context` parameter), look it up with `UserStore().user_for_token`, answer `ERROR[UNAUTHENTICATED]: ... Next step: ...` otherwise. Never take a user id from a tool argument. The grader calls the server directly: all eight tools without a token, with a malformed one and with an unknown one (2 points); users cannot see or change each other's notes and tasks (1 point).
- **7.3 the lifecycle (2):** statuses `todo` / `in_progress` / `done` (`todo` cannot jump to `done`), filtering, summary, and the error codes `INVALID_STATUS`, `INVALID_TRANSITION`, `TASK_NOT_FOUND`, `NOTE_NOT_FOUND`, `INVALID_INPUT`: these come from `TaskStore`; you only have to pass them on (tasks 1 point, notes 1 point).
- **7.4 forward the token from the agent (1):** add `token` to `Ctx` (`/agent` fills it from the Authorization header) and write a `langchain-mcp-adapters` tool interceptor in `agent.py` that sets `Authorization: Bearer <runtime.context.token>` on every MCP call (`tool_interceptors=[...]`). The token must not appear in any tool argument, step, answer, prompt or log line.
- **7.5 survives a restart (1):** `MCP_DB` is on the data volume. `docker compose` runs the server as the `notes-mcp` service; CI starts it as a second container on the same volume and restarts both.

## Where the work is: 9 files, about 320 lines
Most of it is wiring and docstrings; the reference solution adds this much per file (code lines, docstrings included):

| File | Tasks | About |
|---|---|---|
| `src/app/agent.py` | 1, 7.4 | 22 lines: tool list, dynamic prompt, `create_agent`, the MCP token interceptor |
| `src/app/persistence.py` | 3 | 6 lines: `AsyncSqliteSaver` |
| `src/app/tools_s1.py`, `src/app/kb/tools.py` | 2 | 30 lines: `async def`, `httpx.AsyncClient`, `asyncio.to_thread` |
| `src/app/context.py` | 4.4, 7.4 | 3 lines: `user_id`, `token` |
| `src/app/main.py` | 3, 4, 7.4 | 60 lines: lifespan, `current_user`, 5 account endpoints, protect 4 routes, claim threads, pass the token |
| `src/app/migrations/0001_*.py` | 4.1 | 20 lines: three `op.create_table`, three `op.drop_table` |
| `src/app/custom_tools.py` | 5, 6 | 100 lines: four tools (the longest file; metric and log are 6 lines each) |
| `src/app/mcp_server/server.py` | 7.1, 7.2 | 75 lines: `current_user_id` plus eight small tool wrappers |

Plan for a day of work, in this order (each step makes more checks pass; run `bash scripts/local_eval.sh` after each):
1. Task 1 (agent.py): everything else depends on a working agent.
2. Task 3 (persistence.py + lifespan), then task 2 (async).
3. Task 4.1 (migration), then 4.2 to 4.6 (users, auth, per-user knowledge base).
4. Task 7 (MCP server, then the token interceptor): needs users to exist.
5. Tasks 5 and 6 (the four tools).
Tip: the provided files (`users.py`, `taskstore.py`, `kb/store.py`) are the documentation: read their docstrings first.

## Score table
| Task | Check ids |
|---|---|
| 1 | `agent-tools` `agent-prompt` `baseline` |
| 2 | `async-tools` `async-blocking` |
| 3 | `memory-live` `sqlite-memory` |
| 4 | `migration-roundtrip` `migration-schema` `users-login` `users-manage` `users-delete` `users-auth` `user-kb` `user-isolation` `user-persists` |
| 5 | `kb-stats` `outline-output` (2) `outline-errors` `outline-metric` `outline-log` |
| 6 | `delete-works` `delete-errors` `update-works` `update-errors` |
| 7 | `mcp-tools` `mcp-auth` (2) `mcp-isolation` `mcp-lifecycle` `mcp-notes` `mcp-token-hygiene` `mcp-persists` |

## How the grader drives your app (so you can reproduce it)
CI runs the migration round trip, starts the MCP server and the API (`LLM_MODE=fake`, a scripted model, `src/app/fake_llm.py`), runs phase 1, **restarts both containers with the same data volume**, runs phase 2.
Until `POST /users` exists the other checks run as an anonymous user, so each task is graded on its own. By hand:
```bash
docker compose up -d --build        # api, ui, notes-mcp, migrate, observability
TOKEN=$(curl -s localhost:8000/login -H 'content-type: application/json' -d '{"username":"me","password":"correct-horse"}' | jq -r .token)
curl -s localhost:8000/agent -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"add a task: write the report","thread_id":"t1"}'
```
With `LLM_MODE=fake` (a scripted model) you can drive any tool: `call <tool> <json args>`, `ingest <file_id>`, `search <text>`, `recall`, `showprompt`.
Your data must live under `/data` (`CHECKPOINT_DB`, `KB_DB`, `MCP_DB`, `QDRANT_URL=path:/data/qdrant` in the Dockerfile `runner` target; the users database sits next to `KB_DB`).

## Rules
- Edit only `src/app/` (and README.md, .gitignore). Everything else is locked and compared byte for byte.
- No new dependencies (`pyproject.toml` is locked); `alembic`, `langgraph-checkpoint-sqlite`, `aiosqlite`, `mcp`, OpenTelemetry are installed.
- Your own work: solutions are compared across students.
- Do not hard-code the grader's behavior (for example detecting `LLM_MODE=fake`); reviewers read the code.
