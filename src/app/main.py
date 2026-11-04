import sqlite3
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.telemetry import (  # first: providers must exist before LangChain runs
    DEBUG, LOG_BUFFER, metrics_snapshot, RUN_STEPS, HTTP_DURATION, HTTP_REQUESTS, configure_logging, log, run_config, setup_telemetry,
    shutdown_telemetry,
)

setup_telemetry()
configure_logging()
HTTPXClientInstrumentor().instrument()  # outgoing HTTP (URL ingestion, Groq) becomes child spans

from app.agent import build_agent, charts_from, clean_answer, steps_from
from app.context import Ctx
from app.errors import DocError, http_status
from app.kb import files
from app.kb.store import KnowledgeBase
from app.persistence import open_checkpointer
from app.schemas import AgentRequest, AgentResponse, KBResponse, UploadResponse
from app.tools_s1 import CHARTS_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kb = KnowledgeBase()  # loads the embedder, opens Qdrant + SQLite
    # TODO(task 3): integrate the checkpointer. `open_checkpointer()` (persistence.py) is an async CONTEXT MANAGER that you
    #   write: open it here, pass the saver to build_agent(..., checkpointer=saver), and keep it open until shutdown
    #   (everything from build_agent to `yield` goes inside the `async with`). Today the agent has no memory at all.
    agent, tools = await build_agent(app.state.kb)
    app.state.agent, app.state.tools = agent, tools
    app.state.tool_names = [t.name for t in tools]
    log.info("startup_complete", tools=app.state.tool_names)
    yield
    shutdown_telemetry()


app = FastAPI(title="Agentic AI assessment - Document Agent (tools + knowledge base + MCP)", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
app.mount("/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")


@app.middleware("http")
async def observe(request: Request, call_next):
    """Per-request: request_id in every log line, API-hit metrics by route/method/status."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid)
    t0, status = time.perf_counter(), 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["x-request-id"] = rid
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", request.url.path)  # template, not raw path
        elapsed = time.perf_counter() - t0
        attrs = {"http.route": route, "http.method": request.method, "http.status_code": str(status)}
        if route != "/health":
            HTTP_REQUESTS.add(1, attrs)
            HTTP_DURATION.record(elapsed, attrs)
            log.info("http_request", route=route, method=request.method, status=status,
                     duration_ms=round(elapsed * 1000))


# TODO(task 4): users and authentication. See users.py for the contract. In short: POST /users, POST /login, GET /me, POST /logout,
#   DELETE /users/me, a FastAPI dependency that turns `Authorization: Bearer <token>` into the current user (401 otherwise) and is used by /agent, /upload and /kb;
#   /agent passes context=Ctx(session_id=..., user_id=...); a thread belongs to its first user (403 for anybody else).


@app.get("/health")
async def health(request: Request):
    return {"status": "ok", "tools": request.app.state.tool_names}


@app.post("/agent", response_model=AgentResponse)
async def agent(req: AgentRequest, request: Request):
    """The agent decides: Session 1 tools, ingest_document, search_knowledge_base (cites document and section), MCP notes."""
    structlog.contextvars.bind_contextvars(thread_id=req.thread_id)
    result = await _guard(
        request.app.state.agent.ainvoke(
            {"messages": [{"role": "user", "content": req.message}]},
            config=run_config(thread_id=req.thread_id),
            context=Ctx(session_id=req.thread_id),
        )
    )
    msgs = result["messages"]
    # only this turn: everything after the last human message
    turn = msgs[max(i for i, m in enumerate(msgs) if m.type == "human"):]
    steps = steps_from(turn)
    RUN_STEPS.record(len(steps))
    log.info("agent_done", steps=len(steps), tools=[s["tool"] for s in steps], answer_chars=len(str(msgs[-1].content)))
    return AgentResponse(answer=clean_answer(str(msgs[-1].content)), steps=steps, charts=charts_from(turn))


@app.post("/upload", response_model=UploadResponse)
async def upload(request: Request, file: UploadFile = File(...), session_id: str = Form(...)):
    """Store a file for this session. It is NOT indexed yet: the agent calls ingest_document(file_id)."""
    data = await file.read(files.MAX_BYTES + 1)
    try:
        file_id, path = files.save_upload(session_id, file.filename or "file", data)
    except DocError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.message} {exc.next_step}") from exc
    log.info("file_uploaded", filename=path.name.split("__", 1)[1], size=len(data))
    return UploadResponse(file_id=file_id, filename=path.name.split("__", 1)[1], size=len(data))


@app.get("/kb/{session_id}", response_model=KBResponse)
async def kb_state(session_id: str, request: Request):
    """What this session's knowledge base holds, and exactly what the agent is told about it."""
    kb: KnowledgeBase = request.app.state.kb
    try:
        files.safe_session(session_id)
    except DocError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    prof = kb.get_profile(session_id) or {"overview": None, "keywords": []}
    return KBResponse(**prof, documents=kb.documents(session_id), prompt_block=kb.prompt_block(session_id))


@app.delete("/kb/{session_id}")
async def kb_reset(session_id: str, request: Request):
    request.app.state.kb.reset(files.safe_session(session_id))
    return {"status": "cleared"}


async def _guard(awaitable):
    try:
        return await awaitable
    except Exception as exc:
        log.error("request_failed", error_type=type(exc).__name__, error=str(exc)[:1000])
        status, message, headers = http_status(exc)  # safe text: no internals leak to the client
        raise HTTPException(status_code=status, detail=message, headers=headers) from exc


if DEBUG:  # ASSESSMENT_DEBUG=1: what the autograder (and you) can inspect

    @app.get("/debug/telemetry")
    async def debug_telemetry():
        """Metrics recorded so far (in memory) and the most recent structured log events."""
        return {"metrics": metrics_snapshot(), "logs": list(LOG_BUFFER)[-300:]}

    @app.get("/debug/tools")
    async def debug_tools(request: Request):
        """Every registered tool and whether it is async (has a coroutine): the autograder checks the async conversion here."""
        return [{"name": t.name, "async": getattr(t, "coroutine", None) is not None} for t in request.app.state.tools]

    @app.get("/debug/schema")
    async def debug_schema():
        """Tables and columns of the users database and the Alembic revision it is at (the autograder checks your migration here)."""
        from app.users import users_db_path

        con = sqlite3.connect(users_db_path())
        try:
            tables = {t: [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
                      for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            revision = [r[0] for r in con.execute("SELECT version_num FROM alembic_version")] if "alembic_version" in tables else []
        finally:
            con.close()
        return {"tables": tables, "alembic_revision": revision}
