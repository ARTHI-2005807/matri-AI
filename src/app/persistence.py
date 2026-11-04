"""Chat memory: the LangGraph checkpointer that remembers each conversation (thread_id).

TODO(task 2): chat memory must survive a restart of the API container.
  Today it is `InMemorySaver`: restart the container and every conversation is forgotten.
  Replace it with a SQLite-backed saver that stores to the file named by CHECKPOINT_DB.

Hints
  - the package `langgraph-checkpoint-sqlite` is already installed
  - the agent runs async, so you want the async saver; `AsyncSqliteSaver.from_conn_string(path)` is an async CONTEXT MANAGER
  - open it once at startup and keep it open until shutdown: main.py's lifespan wraps the whole app in `async with open_checkpointer()`
  - make sure the folder of CHECKPOINT_DB exists
"""
import os
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver

CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoints.sqlite")


@asynccontextmanager
async def open_checkpointer():
    yield InMemorySaver()  # TODO(task 2): replace with an AsyncSqliteSaver on CHECKPOINT_DB
