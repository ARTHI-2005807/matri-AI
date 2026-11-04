"""PROVIDED (task 5): the Graphviz story-chart builder. It is plain Python, no LangChain, no telemetry.

You write the TOOL around it in custom_tools.py: the @tool signature and docstring, turning StoryError into ToolException,
the metric and the log line. The exact output format is documented in docs/TASK.md and checked by the autograder.
"""
from pydantic import BaseModel

MAX_NODES = 12


class Edge(BaseModel):
    source: str
    target: str
    label: str = ""


class StoryError(Exception):
    def __init__(self, code: str, what: str, next_step: str):
        super().__init__(f"ERROR[{code}]: {what} Next step: {next_step}")
        self.code = code


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def build_dot(title: str, nodes: list[str], edges: list[Edge]) -> str:
    """-> one fenced ```dot block. Raises StoryError (its str() is the full 'ERROR[CODE]: ... Next step: ...' text)."""
    if len(nodes) < 2:
        raise StoryError("TOO_FEW_NODES", f"a story chart needs at least 2 beats, got {len(nodes)}.", "send 2 to 12 beats.")
    if len(nodes) > MAX_NODES:
        raise StoryError("TOO_MANY_NODES", f"{len(nodes)} beats is more than the {MAX_NODES} allowed.", f"merge beats and send at most {MAX_NODES}.")
    if any(not n.strip() for n in nodes):
        raise StoryError("EMPTY_LABEL", "a beat has no text.", "give every beat a short description.")
    if len(set(nodes)) != len(nodes):
        raise StoryError("DUPLICATE_NODE", "two beats have the same text.", "make each beat's text unique.")
    ids = {text: f"n{i}" for i, text in enumerate(nodes, start=1)}
    for e in edges:
        for end in (e.source, e.target):
            if end not in ids:
                raise StoryError("UNKNOWN_NODE", f"edge refers to '{end}', which is not one of the beats.", "use the exact text of a beat as source and target.")
    links = edges or [Edge(source=a, target=b) for a, b in zip(nodes, nodes[1:])]
    lines = [f'digraph "{_esc(title)}" {{', "  rankdir=LR;", "  node [shape=box, style=rounded];"]
    lines += [f'  {ids[text]} [label="{_esc(text)}"];' for text in nodes]
    lines += [f"  {ids[e.source]} -> {ids[e.target]}" + (f' [label="{_esc(e.label)}"];' if e.label else ";") for e in links]
    lines.append("}")
    return "```dot\n" + "\n".join(lines) + "\n```"
