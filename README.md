# Agentic AI assessment: integrate the Document Agent

A working AI agent you run on **your own computer** with **your own free Groq API key**. It chats, uses tools
(SQL, charts, web, OpenML), reads documents you upload (PDF, DOCX, text, scans), answers with citations, and sends
logs, metrics and traces to Grafana. Your job: **finish the integration** (seven tasks), then push to GitHub. Automated tests grade your work.

```
Gradio UI :7860 --> FastAPI agent :8000 --> Groq (LLM) · Qdrant (vectors) · SQLite · MCP notes and tasks server
                          |
                          +--> OpenTelemetry Collector --> Tempo (traces) · Prometheus (metrics) · Loki (logs) --> Grafana :3000
```

## Your seven tasks (34 points; details and grading in [docs/TASK.md](docs/TASK.md))
You write the **integration**; the building blocks are provided (`users.py`, `taskstore.py`, `kb.stats`, `kb.outline`, `kb.delete_document`).
1. **Define the agent**: the 21 tools, a dynamic prompt with the user's knowledge base, context and checkpointer wiring
2. **Async**: no blocking calls inside the tools
3. **SQLite chat memory**: define the checkpointer and integrate it in the app
4. **Alembic migration + user management**: register, log in, `/me`, logout, delete account; one knowledge base per user, shared by all of their chats, invisible to others
5. **Two tools with observability**: `kb_stats` and `document_outline`, each with a metric and a structured log line
6. **Manage the knowledge base with tools**: `delete_document`, `update_document`
7. **Notes and tasks MCP server with per-user auth**: register the tools, check the bearer token in the server, forward it from the agent

## What you have to do (in short)
1. **Set up** (below): your own private repo from the template, your Groq key, `bash scripts/check_setup.sh`, `docker compose up --build -d`.
2. **Make the checks pass:** the app runs, but the seven tasks above are yours. You write only the integration (wiring, small wrappers, docstrings, one migration); the hard parts are provided. Start with task 1 and follow the order in [docs/TASK.md](docs/TASK.md).
3. **Check yourself:** `bash scripts/local_eval.sh` runs the grader on your machine: your score and why each failed check fails.
4. **Push to `main`:** the GitHub run **evaluate** grades you; open its **Summary** tab.
5. **Submit the run URL and a read-only token** through the form before **12 Nov 2026, 23:59 IST** ([docs/SUBMIT.md](docs/SUBMIT.md)). Partial points count and your best attempt is kept.

**About the red cross:** the GitHub run turns red until all 34 checks pass. That is intended. It still records your score (open the run's **Summary** tab); submit it anyway, partial points count and your best attempt is kept (see [docs/SUBMIT.md](docs/SUBMIT.md)).

## What you need on your computer
| Tool | Check | Install |
|---|---|---|
| Docker (with Compose) | `docker --version` | https://www.docker.com/products/docker-desktop/ |
| uv (Python manager) | `uv --version` | https://docs.astral.sh/uv/getting-started/installation/ |
| Git | `git --version` | https://git-scm.com/ |
| A Groq API key (free) | opens a page | https://console.groq.com/keys (sign up, **Create API Key**, copy it) |

About 4 GB of free RAM and 5 GB of disk. Windows: use **WSL 2** (Docker Desktop's default) and run the commands in the WSL terminal.
macOS / Linux: any terminal.

### About the Groq key
- The free tier is enough. Limits you will notice: a few thousand tokens per request and a daily token cap.
  If you see "rate limited" in the chat, wait a minute (the agent tells you how long).
- The key stays on **your** machine in `.env` (git ignores it). **Never commit it, never paste it in the submission form.**
- The autograder on GitHub **does not use your key**: it runs your code with a scripted model. So your key only powers your own experiments.

## Set it up (about 15 minutes, once)
```bash
# 1. your copy of the project: on GitHub press "Use this template" > "Create a new repository" (Private, your own account)
git clone https://github.com/<you>/<your-repo>
cd <your-repo>

# 2. install the local safety hooks (they stop you editing locked files); installs only pre-commit, about a second
uv run --only-group hooks pre-commit install

# 3. add your Groq key
cp .env.example .env            # then open .env and paste your key after GROQ_API_KEY=

# 4. check everything is ready (Docker running, key valid, ports free)
bash scripts/check_setup.sh

# 5. start it (the first build downloads models: 5-10 minutes)
docker compose up --build -d
```
Open **http://localhost:7860** (the chat UI) and **http://localhost:3000** (Grafana, dashboard *Agent - API, tokens, models, tools*).
Stop everything with `docker compose down`.

If port 6333 is taken on your machine: `QDRANT_PORT=6335 docker compose up -d`.

### Try it (5 minutes)
0. After task 4 the UI asks you to **register and log in** (Account box, right side); before that it works anonymously.
1. In the UI, upload `samples/attention-is-all-you-need.pdf` and wait about a minute (it reads, splits into sections, embeds).
2. Ask *"How does multi-head attention work?"*: the answer cites `[document › section, page]`.
3. Ask *"Top 5 artists in the Chinook database as a bar chart"*: SQL + chart, no document search (see the **Steps** and **Chart** tabs).
4. Upload `samples/react-reasoning-and-acting-scanned.pdf` (an image-only PDF): the knowledge base tab shows *OCR pages*.
5. Open Grafana: API hits, tokens per model, tool calls, ingest latency, logs. Click a log line's `trace_id` to jump to the trace.

## Where things are
| Path | What |
|---|---|
| `src/app/` | **the only place you edit** (plus this README and `.gitignore`) |
| `src/app/custom_tools.py` | tasks 5 and 6: your four tools |
| `src/app/main.py` | tasks 3, 4 and 7.4: lifespan, users and auth endpoints, the token in `Ctx` |
| `src/app/migrations/` | task 4.1: your Alembic migration |
| `src/app/persistence.py` | task 3: chat memory (checkpointer) |
| `src/app/mcp_server/server.py` | task 7: the notes and tasks MCP server (storage provided) |
| `src/app/users.py`, `src/app/mcp_server/taskstore.py` | provided building blocks |
| `src/app/kb/` | the knowledge base: extract text (OCR), sections, embeddings, Qdrant store, tools |
| `src/app/agent.py` | tasks 1 and 7.4: the agent, its prompt, the tool list, the MCP token interceptor |
| `src/app/telemetry.py` | metrics, structured logs, the LangChain callback |
| `src/app/dashboards/` | task 5.3: your Grafana dashboard JSON |
| everything else | **locked**: tests, Docker files, observability config, UI. Changing it makes your submission invalid |

## Your development loop
```bash
# edit src/app/...
docker compose up -d --build api notes-mcp   # rebuild and restart the API and the MCP server (about 20 s once images are cached)
docker compose logs -f api             # JSON logs; Ctrl-C to leave
curl localhost:8000/debug/telemetry    # metrics and recent log events your code recorded (what the grader reads)
bash scripts/local_eval.sh             # the full autograder on your machine, exactly like GitHub (builds 2 images; a few minutes)
```
`local_eval.sh` prints your score with one PASS/FAIL line per check. Fix, re-run, then push.

## Submit
Push to `main`, wait for the GitHub Action, and submit the run URL: see **[docs/SUBMIT.md](docs/SUBMIT.md)**.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `check_setup.sh` says Groq key rejected | copy the key again from console.groq.com/keys; no quotes or spaces in `.env` |
| Chat says "rate limited" / "too large" | wait the time it says; start a new session in the UI for "too large" |
| `all predefined address pools have been fully subnetted` | a VPN confuses Docker: disconnect it, or run `docker network prune` |
| Port already in use | `docker compose down`, or stop the other program (`check_setup.sh` names the port) |
| Commit blocked: "Locked files differ" | you changed a locked file; the message shows the `git restore` command |
| Ingestion is slow | a scanned page takes about 10-15 s (OCR); text PDFs take seconds. Use the small `samples/` files |
| Grafana is empty | send some chat messages first; metrics appear within 10-20 s |
| Task or note tools fail with `UNAUTHENTICATED` | log in first; then check the interceptor forwards the token (task 7.4) and `docker compose ps` shows `notes-mcp` running |
| `/login` or MCP says a table does not exist | the migration did not run: `docker compose run --rm migrate` and look at its output |

Use this file for your own notes: how you solved each task, a screenshot of your Grafana panel. It is not graded, but graders may read it.
