"""Tasks 5 and 6: four tools. Names, arguments, outputs, errors, metric and log names are FIXED (the autograder checks them).

The heavy parts are PROVIDED (story.py: build_dot, kb/store.py: stats / delete_document, kb/pipeline.py: ingest_file).
You write the tool wrappers: signature + docstring (the docstring is the prompt: say WHEN to use it, describe each argument),
validation, ToolException with `ERROR[CODE]: what happened. Next step: what to do.`, the metric, the log line, `handle_tool_error = True`.
All four are `async def` (blocking calls go through asyncio.to_thread). They act on the CALLING USER's knowledge base:
`runtime.context.user_id` (task 4), never on another user's. build_custom_tools(kb) returns all four.
Look at kb/tools.py for the pattern (ToolRuntime, ToolException, handle_tool_error).

---------------------------------------------------------------------------------- task 5.1  kb_stats(top_keywords: int = 5) -> str
  output  "<D> documents, <S> sections, <C> chunks. Top keywords: k1, k2, ..."   from kb.stats(user_id); at most `top_keywords` keywords
          empty knowledge base: "The knowledge base is empty."
  error   top_keywords outside 1..20  ->  ERROR[INVALID_INPUT]

---------------------------------------------------------------------------------- task 5.2  story_diagram(title: str, nodes: list[str], edges: list[Edge] = []) -> str
  output  exactly what story.build_dot returns (one fenced ```dot block). `Edge` is story.Edge.
  errors  build_dot raises StoryError; its text is already `ERROR[CODE]: ... Next step: ...`: re-raise it as ToolException.
  Use it when the user asks for a story, plot, timeline or process as a chart / diagram / flowchart.

---------------------------------------------------------------------------------- task 5.3  observability, every call, ok AND error
  metric  kb_stats: counter "kbstats.calls"    story_diagram: counter "story.diagrams"
          record with attributes {"status": "ok" | "error"}  (Prometheus: agent_story_diagrams_total, ...)
          metrics.get_meter("agent").create_counter(...)   (see how app/telemetry.py creates TOOL_CALLS)
  log     log.info("kb_stats_done", tool="kb_stats", status=..., duration_ms=<int>)
          log.info("story_diagram_done", tool="story_diagram", status=..., duration_ms=<int>, nodes=<int, 0 on error>)
          (`from app.telemetry import log`; never log the story text)
  Grafana (reviewed, not auto-graded): src/app/dashboards/story.json with a panel for story.diagrams by status and a logs panel
          ({service_name="extraction-agent"} | json | event="story_diagram_done").

---------------------------------------------------------------------------------- task 6.1  delete_document(doc_name: str) -> str
  Removes one document from the user's knowledge base. doc_name is a file name from the KNOWLEDGE BASE list.
  Resolve it with kb.resolve_doc_name(user_id, doc_name); find the document's doc_id in kb.documents(user_id);
  delete with kb.delete_document(user_id, doc_id).
  output  "Deleted '<exact file name>'. <N> documents left."
  error   no such document in THIS user's knowledge base  ->  ERROR[UNKNOWN_DOCUMENT]  (list the valid names in the message)

---------------------------------------------------------------------------------- task 6.2  update_document(doc_name: str, source: str) -> str
  Replaces a document with a new version the user uploaded. source = the file_id of the NEW upload (like ingest_document).
  Order matters: ingest the new file FIRST under the OLD file name (kb/pipeline.ingest_file, files.resolve), and only when that
  succeeded delete the old version by its doc_id: a failed update must leave the old document untouched.
  If the new file is identical to a document already in the knowledge base ingest_file returns it as `existing`: change nothing.
  output  "Updated '<exact file name>': <S> sections, <C> chunks."      identical content: "'<name>' is already up to date."
  errors  unknown doc_name -> ERROR[UNKNOWN_DOCUMENT];  bad/unknown file_id -> use app.errors.to_tool_exception on the DocError
          (it yields ERROR[FILE_NOT_FOUND]).
"""
from langchain_core.tools import tool  # noqa: F401  (you will need it)

from app.kb.store import KnowledgeBase


def build_custom_tools(kb: KnowledgeBase) -> list:
    # TODO(tasks 5 and 6): define kb_stats, story_diagram, delete_document and update_document here and return all four
    return []
