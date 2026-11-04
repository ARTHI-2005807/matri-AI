"""Your tool goes here.

TODO(task 1): add ONE new tool to the agent and make it observable.

How
  - write a function decorated with @tool (the docstring is the prompt: say WHEN to use it and describe each argument)
  - return it from build_custom_tools below; the agent and /health pick it up automatically
    (the function gets the shared KnowledgeBase `kb`, in case your tool needs it; build_kb_tools in kb/tools.py is a model to copy)
  - declare it in assessment.json (name, example arguments, invalid arguments, metric name, log event name)

The contract the autograder checks (see docs/TASK.md for the full text)
  1. valid arguments    -> the tool returns normally (a string)
  2. invalid arguments  -> it fails like our other tools: raise ToolException("ERROR[CODE]: what happened. Next step: ...")
                           (use app.errors.to_tool_exception or raise ToolException yourself) and set `your_tool.handle_tool_error = True`
  3. a NEW metric       -> create your own OpenTelemetry instrument (a counter or histogram) and record to it on every call;
                           its name goes in assessment.json under "metric" (see how app/telemetry.py creates `TOOL_CALLS`)
  4. a structured log   -> one log line per call: log.info("<your event>", tool="<tool name>", status="ok"|"error", duration_ms=<int>)
                           the event name goes in assessment.json under "log_event"  (`from app.telemetry import log`)

Ideas: a knowledge-base statistics tool, a unit converter, a text summary-length checker, a document keyword lister,
a currency lookup that calls a public API. Keep it small and deterministic: the autograder calls it without internet.
"""
from langchain_core.tools import tool  # noqa: F401  (you will need it)

from app.kb.store import KnowledgeBase


def build_custom_tools(kb: KnowledgeBase) -> list:
    # TODO(task 1): define your tool here (inside this function it can use `kb`) and return [your_tool]
    return []
