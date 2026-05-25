"""Cursor Cloud Agents plugin for Hermes.

Registers 13 tools into the ``cursor`` toolset:
  cursor_agent_create, cursor_agent_list, cursor_agent_get,
  cursor_agent_send, cursor_agent_wait, cursor_agent_cancel,
  cursor_agent_resume, cursor_agent_archive, cursor_agent_unarchive,
  cursor_agent_delete, cursor_agent_artifacts,
  cursor_models_list, cursor_repos_list.

Requires: cursor-sdk (pip install cursor-sdk) + CURSOR_API_KEY in .env
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# User plugin self-import bootstrap
#
# The Hermes loader registers this module as  hermes_plugins.cursor  with
# __path__ = [plugin_dir].  Sub-modules (client.py, tools.py) are NOT
# automatically on sys.path, so we manually load them under the
# hermes_plugins.cursor namespace.
# ---------------------------------------------------------------------------

_PLUGIN_DIR = Path(__file__).resolve().parent


def _load_submodule(name: str) -> None:
    """Register plugin_dir/<name>.py under hermes_plugins.cursor.<name>."""
    full_path = _PLUGIN_DIR / f"{name}.py"
    if not full_path.exists():
        return
    ns_name = f"hermes_plugins.cursor.{name}"
    if ns_name in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(ns_name, full_path)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "hermes_plugins.cursor"
    sys.modules[ns_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]


_load_submodule("client")
_load_submodule("tools")

from hermes_plugins.cursor.client import check_cursor_available  # noqa: E402
from hermes_plugins.cursor.tools import (  # noqa: E402
    CURSOR_AGENT_ARCHIVE_SCHEMA,
    CURSOR_AGENT_ARTIFACTS_SCHEMA,
    CURSOR_AGENT_CANCEL_SCHEMA,
    CURSOR_AGENT_CREATE_SCHEMA,
    CURSOR_AGENT_DELETE_SCHEMA,
    CURSOR_AGENT_GET_SCHEMA,
    CURSOR_AGENT_LIST_SCHEMA,
    CURSOR_AGENT_RESUME_SCHEMA,
    CURSOR_AGENT_SEND_SCHEMA,
    CURSOR_AGENT_UNARCHIVE_SCHEMA,
    CURSOR_AGENT_WAIT_SCHEMA,
    CURSOR_MODELS_LIST_SCHEMA,
    CURSOR_REPOS_LIST_SCHEMA,
    _handle_cursor_agent_archive,
    _handle_cursor_agent_artifacts,
    _handle_cursor_agent_cancel,
    _handle_cursor_agent_create,
    _handle_cursor_agent_delete,
    _handle_cursor_agent_get,
    _handle_cursor_agent_list,
    _handle_cursor_agent_resume,
    _handle_cursor_agent_send,
    _handle_cursor_agent_unarchive,
    _handle_cursor_agent_wait,
    _handle_cursor_models_list,
    _handle_cursor_repos_list,
)

_TOOLS = [
    ("cursor_agent_create",    CURSOR_AGENT_CREATE_SCHEMA,    _handle_cursor_agent_create,    "robot"),
    ("cursor_agent_list",      CURSOR_AGENT_LIST_SCHEMA,      _handle_cursor_agent_list,      "list"),
    ("cursor_agent_get",       CURSOR_AGENT_GET_SCHEMA,       _handle_cursor_agent_get,       "search"),
    ("cursor_agent_send",      CURSOR_AGENT_SEND_SCHEMA,      _handle_cursor_agent_send,      "chat"),
    ("cursor_agent_wait",      CURSOR_AGENT_WAIT_SCHEMA,      _handle_cursor_agent_wait,      "wait"),
    ("cursor_agent_cancel",    CURSOR_AGENT_CANCEL_SCHEMA,    _handle_cursor_agent_cancel,    "stop"),
    ("cursor_agent_resume",    CURSOR_AGENT_RESUME_SCHEMA,    _handle_cursor_agent_resume,    "play"),
    ("cursor_agent_archive",   CURSOR_AGENT_ARCHIVE_SCHEMA,   _handle_cursor_agent_archive,   "archive"),
    ("cursor_agent_unarchive", CURSOR_AGENT_UNARCHIVE_SCHEMA, _handle_cursor_agent_unarchive, "unarchive"),
    ("cursor_agent_delete",    CURSOR_AGENT_DELETE_SCHEMA,    _handle_cursor_agent_delete,    "trash"),
    ("cursor_agent_artifacts", CURSOR_AGENT_ARTIFACTS_SCHEMA, _handle_cursor_agent_artifacts, "folder"),
    ("cursor_models_list",     CURSOR_MODELS_LIST_SCHEMA,     _handle_cursor_models_list,     "brain"),
    ("cursor_repos_list",      CURSOR_REPOS_LIST_SCHEMA,      _handle_cursor_repos_list,      "repos"),
]


def register(ctx) -> None:
    """Register all Cursor tools. Called once by the Hermes plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="cursor",
            schema=schema,
            handler=handler,
            check_fn=check_cursor_available,
            requires_env=["CURSOR_API_KEY"],
            emoji=emoji,
        )
