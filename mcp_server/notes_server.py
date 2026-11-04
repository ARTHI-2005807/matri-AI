"""A tiny MCP server: save and list notes (action items). Same decorator idea as @tool."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

NOTES_FILE = Path(os.getenv("NOTES_FILE", "notes.json"))
mcp = FastMCP("notes", host="0.0.0.0", port=9000)


def _load() -> list[dict]:
    return json.loads(NOTES_FILE.read_text()) if NOTES_FILE.exists() else []


@mcp.tool()
def add_note(title: str, body: str) -> str:
    """Save a note (e.g. one action item) and return its id."""
    notes = _load()
    note = {
        "id": len(notes) + 1,
        "title": title,
        "body": body,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    NOTES_FILE.write_text(json.dumps([*notes, note], indent=2))
    return f"saved note #{note['id']}"


@mcp.tool()
def list_notes() -> list[dict]:
    """List all saved notes."""
    return _load()


if __name__ == "__main__":
    # stdio for local dev (spawned by the agent); streamable-http inside docker-compose
    mcp.run(transport="streamable-http" if "--http" in sys.argv else "stdio")
