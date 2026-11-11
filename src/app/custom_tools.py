"""Tasks 7 and 8: four tools. Names, arguments, outputs, errors, metric and log names are FIXED (the autograder checks them).

The heavy parts are PROVIDED (kb/store.py: stats / outline / delete_document, kb/pipeline.py: ingest_file).
You write the tool wrappers: signature + docstring (the docstring is the prompt: say WHEN to use it, describe each argument),
validation, ToolException with `ERROR[CODE]: what happened. Next step: what to do.`, the metric, the log line, `handle_tool_error = True`.
All four are `async def` (blocking calls go through asyncio.to_thread). They act on the CALLING USER's knowledge base:
`runtime.context.user_id` (task 6), never on another user's. build_custom_tools(kb) returns all four.
Look at kb/tools.py for the pattern (ToolRuntime, ToolException, handle_tool_error).

---------------------------------------------------------------------------------- task 7.1  kb_stats(top_keywords: int = 5) -> str
  output  "<D> documents, <S> sections, <C> chunks. Top keywords: k1, k2, ..."   from kb.stats(user_id); at most `top_keywords` keywords
          empty knowledge base: "The knowledge base is empty."
  error   top_keywords outside 1..20  ->  ERROR[INVALID_INPUT]

---------------------------------------------------------------------------------- task 7.2  document_outline(doc_name: str) -> str
  The structure of one document: use it when the user asks what a document contains, how it is organised, or which section covers
  something (then search that section). Resolve doc_name with kb.resolve_doc_name(user_id, doc_name), find the doc_id in
  kb.documents(user_id), read the sections with kb.outline(user_id, doc_id).
  output  first line   "Outline of '<exact file name>' (<N> sections):"          (always the word "sections")
          then one line per section, in reading order, 1-based position:
              "<i>. [L<level>] <heading> (p.<a>-<b>): <summary>"
          the page part is " (p.<a>-<b>)" when page_start != page_end, " (p.<a>)" when they are equal, and left out when the
          document has no pages (page_start is None); then ": <summary>"
  error   no such document in THIS user's knowledge base  ->  ERROR[UNKNOWN_DOCUMENT]  (list the valid names in the message)

---------------------------------------------------------------------------------- task 7.3  observability, every call, ok AND error
  metric  kb_stats: counter "kbstats.calls"    document_outline: counter "outline.calls"
          record with attributes {"status": "ok" | "error"}  (Prometheus: agent_outline_calls_total, ...)
          metrics.get_meter("agent").create_counter(...)   (see how app/telemetry.py creates TOOL_CALLS)
  log     log.info("kb_stats_done", tool="kb_stats", status=..., duration_ms=<int>)
          log.info("document_outline_done", tool="document_outline", status=..., duration_ms=<int>, sections=<int, 0 on error>)
          (`from app.telemetry import log`; never log document text)
  Grafana (recommended, not graded): src/app/dashboards/outline.json with a panel for outline.calls by status and a logs panel
          ({service_name="extraction-agent"} | json | event="document_outline_done").

---------------------------------------------------------------------------------- task 8.1  delete_document(doc_name: str) -> str
  Removes one document from the user's knowledge base. doc_name is a file name from the KNOWLEDGE BASE list.
  Resolve it with kb.resolve_doc_name(user_id, doc_name); find the document's doc_id in kb.documents(user_id);
  delete with kb.delete_document(user_id, doc_id).
  output  "Deleted '<exact file name>'. <N> documents left."
  error   no such document in THIS user's knowledge base  ->  ERROR[UNKNOWN_DOCUMENT]  (list the valid names in the message)

---------------------------------------------------------------------------------- task 8.2  update_document(doc_name: str, source: str) -> str
  Replaces a document with a new version the user uploaded. source = the file_id of the NEW upload (like ingest_document).
  Order matters: ingest the new file FIRST under the OLD file name (kb/pipeline.ingest_file, files.resolve), and only when that
  succeeded delete the old version by its doc_id: a failed update must leave the old document untouched.
  If the new file is identical to a document already in the knowledge base ingest_file returns it as `existing`: change nothing.
  output  "Updated '<exact file name>': <S> sections, <C> chunks."      identical content: "'<name>' is already up to date."
  errors  unknown doc_name -> ERROR[UNKNOWN_DOCUMENT];  bad/unknown file_id -> use app.errors.to_tool_exception on the DocError
          (it yields ERROR[FILE_NOT_FOUND]).
"""
import asyncio
import time

from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool

from app.kb.store import KnowledgeBase
from app.context import Ctx
from app.errors import to_tool_exception
from app.kb import files
from app.kb.pipeline import ingest_file
from app.telemetry import log
from opentelemetry import metrics


def build_custom_tools(kb: KnowledgeBase) -> list:
    meter = metrics.get_meter("agent")
    stats_calls = meter.create_counter("kbstats.calls")
    outline_calls = meter.create_counter("outline.calls")

    def resolve(user_id, name):
        exact = kb.resolve_doc_name(user_id, name)
        docs = kb.documents(user_id)
        doc = next((d for d in docs if d["filename"] == exact), None)
        return exact, doc, docs

    @tool
    async def kb_stats(top_keywords: int = 5, runtime: ToolRuntime[Ctx] = None) -> str:
        t0 = time.perf_counter()
        status = "ok"
        try:
            if not 1 <= top_keywords <= 20:
                raise ToolException("ERROR[INVALID_INPUT]: top_keywords must be between 1 and 20. Next step: retry with a value from 1 to 20.")
            result = await asyncio.to_thread(kb.stats, runtime.context.user_id)
            if not result["documents"]:
                return "The knowledge base is empty."
            return f"{result['documents']} documents, {result['sections']} sections, {result['chunks']} chunks. Top keywords: {', '.join(result['keywords'][:top_keywords])}"
        except Exception:
            status = "error"
            raise
        finally:
            stats_calls.add(1, {"status": status})
            log.info("kb_stats_done", tool="kb_stats", status=status, duration_ms=round((time.perf_counter()-t0)*1000))

    @tool
    async def document_outline(doc_name: str, runtime: ToolRuntime[Ctx]) -> str:
        t0 = time.perf_counter()
        status, count = "ok", 0
        try:
            exact, doc, docs = await asyncio.to_thread(resolve, runtime.context.user_id, doc_name)
            if not doc:
                names = ", ".join(d["filename"] for d in docs) or "(none)"
                raise ToolException(f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. Next step: retry with a valid document name.")
            sections = await asyncio.to_thread(kb.outline, runtime.context.user_id, doc["doc_id"])
            count = len(sections)
            lines = [f"Outline of '{exact}' ({count} sections):"]
            for i, s in enumerate(sections, 1):
                pages = "" if s["page_start"] is None else f" (p.{s['page_start']}" + (f"-{s['page_end']})" if s["page_end"] != s["page_start"] else ")")
                lines.append(f"{i}. [L{s['level']}] {s['heading']}{pages}: {s['summary']}")
            return "\n".join(lines)
        except Exception:
            status = "error"
            raise
        finally:
            outline_calls.add(1, {"status": status})
            log.info("document_outline_done", tool="document_outline", status=status, duration_ms=round((time.perf_counter()-t0)*1000), sections=count)

    async def find_or_error(user_id, name):
        exact, doc, docs = await asyncio.to_thread(resolve, user_id, name)
        if not doc:
            names = ", ".join(d["filename"] for d in docs) or "(none)"
            raise ToolException(f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{name}'. Documents: {names}. Next step: retry with a valid document name.")
        return exact, doc

    @tool
    async def delete_document(doc_name: str, runtime: ToolRuntime[Ctx]) -> str:
        exact, doc = await find_or_error(runtime.context.user_id, doc_name)
        await asyncio.to_thread(kb.delete_document, runtime.context.user_id, doc["doc_id"])
        return f"Deleted '{exact}'. {len(kb.documents(runtime.context.user_id))} documents left."

    @tool
    async def update_document(doc_name: str, source: str, runtime: ToolRuntime[Ctx]) -> str:
        exact, doc = await find_or_error(runtime.context.user_id, doc_name)
        try:
            path, _ = files.resolve(runtime.context.session_id, source.strip())
            result, existing = await ingest_file(kb, runtime.context.user_id, path, exact, runtime.config)
        except Exception as exc:
            raise to_tool_exception(exc) from exc
        if existing:
            return f"'{exact}' is already up to date."
        await asyncio.to_thread(kb.delete_document, runtime.context.user_id, doc["doc_id"])
        return f"Updated '{exact}': {len(result.sections)} sections, {result.n_chunks} chunks."

    for t in (kb_stats, document_outline, delete_document, update_document):
        t.handle_tool_error = True
    return [kb_stats, document_outline, delete_document, update_document]
