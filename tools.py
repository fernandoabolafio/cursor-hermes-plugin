"""Cursor Cloud Agent tools — schemas and handlers.

Architecture: the Cursor SDK uses a local bridge binary (cursor-sdk-bridge)
as a process-local gRPC proxy. All calls go through Client.launch_bridge()
which starts the bridge, then each operation passes api_key= explicitly.

The bridge is launched per-call (context manager) to keep things stateless
and avoid stale bridge processes. For long-running multi-step workflows,
callers can chain cursor_agent_create -> cursor_agent_send -> cursor_agent_wait.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

API_KEY_ENV = "CURSOR_API_KEY"
DEFAULT_MODEL = "composer-2.5"
BRIDGE_WORKSPACE = "/tmp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> str:
    return json.dumps({"ok": True, **(data if isinstance(data, dict) else {"result": data})})


def _err(msg: str) -> str:
    return json.dumps({"error": str(msg)})


def _api_key() -> str:
    k = os.environ.get(API_KEY_ENV, "").strip()
    if not k:
        raise RuntimeError(
            f"{API_KEY_ENV} is not set. Add it to ~/.hermes/.env:\n"
            f"  CURSOR_API_KEY=crsr_...\nThen restart Hermes or do /reset."
        )
    return k


def _bridge():
    """Context manager that yields a live Client connected via bridge."""
    from cursor_sdk import Client
    return Client.launch_bridge(workspace=BRIDGE_WORKSPACE, allow_api_key_env_fallback=True)


def _agent_info_dict(info) -> dict:
    return {
        "agent_id": getattr(info, "agent_id", None),
        "name": getattr(info, "name", None),
        "summary": getattr(info, "summary", None),
        "status": getattr(info, "status", None),
        "last_modified": getattr(info, "last_modified", None),
    }


def _run_dict(run) -> dict:
    return {
        "run_id": getattr(run, "id", None),
        "agent_id": getattr(run, "agent_id", None),
        "status": getattr(run, "status", None),
        "result": getattr(run, "result", None),
        "duration_ms": getattr(run, "duration_ms", None),
    }


# ---------------------------------------------------------------------------
# cursor_repos_list
# ---------------------------------------------------------------------------

CURSOR_REPOS_LIST_SCHEMA = {
    "name": "cursor_repos_list",
    "description": (
        "List GitHub/GitLab repositories connected to your Cursor account. "
        "Use these repo URLs when creating cloud agents with cursor_agent_create."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _handle_cursor_repos_list(args: Dict[str, Any], **_) -> str:
    try:
        key = _api_key()
        with _bridge() as client:
            repos = client.list_repositories(api_key=key)
            repo_list = [
                {
                    "url": getattr(r, "url", None),
                    "name": getattr(r, "name", None) or getattr(r, "full_name", None),
                    "provider": getattr(r, "provider", None),
                    "default_branch": getattr(r, "default_branch", None),
                }
                for r in repos
            ]
        return _ok({"repositories": repo_list, "count": len(repo_list)})
    except Exception as exc:
        logger.exception("cursor_repos_list failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_models_list
# ---------------------------------------------------------------------------

CURSOR_MODELS_LIST_SCHEMA = {
    "name": "cursor_models_list",
    "description": "List all available Cursor models. Use 'composer-2.5' unless told otherwise.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _handle_cursor_models_list(args: Dict[str, Any], **_) -> str:
    try:
        key = _api_key()
        with _bridge() as client:
            models = client.list_models(api_key=key)
            model_list = [
                {
                    "id": getattr(m, "id", str(m)),
                    "parameters": [
                        {"id": getattr(p, "id", None), "type": getattr(p, "type", None)}
                        for p in (getattr(m, "parameters", None) or [])
                    ],
                }
                for m in models
            ]
        return _ok({"models": model_list, "count": len(model_list)})
    except Exception as exc:
        logger.exception("cursor_models_list failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_create
# ---------------------------------------------------------------------------

CURSOR_AGENT_CREATE_SCHEMA = {
    "name": "cursor_agent_create",
    "description": (
        "Create and start a new Cursor Cloud Agent against a GitHub repo. "
        "Optionally sends an initial prompt and waits for result. "
        "Returns agent_id and (if wait=true) the run result text. "
        "Model defaults to composer-2.5."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "repo_url": {"type": "string", "description": "GitHub repo URL, e.g. https://github.com/org/repo"},
            "branch": {"type": "string", "description": "Branch to run against (default: 'main'). Required — Cursor cannot auto-detect the default branch.", "default": "main"},
            "model": {"type": "string", "description": "Model ID (default: composer-2.5)", "default": "composer-2.5"},
            "prompt": {"type": "string", "description": "Initial message to send immediately after creation."},
            "wait": {"type": "boolean", "description": "Block until run finishes (default true).", "default": True},
            "auto_create_pr": {"type": "boolean", "description": "Auto-open a PR when the run finishes.", "default": False},
            "work_on_current_branch": {"type": "boolean", "description": "Push to existing branch instead of new one.", "default": False},
            "env_vars": {"type": "object", "description": "Session-scoped env vars for the cloud agent."},
        },
        "required": ["repo_url"],
    },
}


def _handle_cursor_agent_create(args: Dict[str, Any], **_) -> str:
    try:
        from cursor_sdk import CloudAgentOptions, CloudRepository

        repo_url = args.get("repo_url", "").strip()
        if not repo_url:
            return _err("repo_url is required")

        model = args.get("model") or DEFAULT_MODEL
        branch = args.get("branch") or "main"
        prompt = (args.get("prompt") or "").strip()
        wait = args.get("wait", True)
        env_vars = args.get("env_vars") or None

        cloud_opts = CloudAgentOptions(
            repos=[CloudRepository(url=repo_url, starting_ref=branch)],
            auto_create_pr=bool(args.get("auto_create_pr", False)),
            work_on_current_branch=bool(args.get("work_on_current_branch", False)),
            env_vars=env_vars,
        )

        key = _api_key()
        with _bridge() as client:
            agent = client.create_agent(
                model=model,
                api_key=key,
                cloud=cloud_opts,
            )
            agent_id = agent.agent_id
            result: dict = {"agent_id": agent_id, "model": model, "repo_url": repo_url}

            if prompt:
                run = agent.send(prompt)
                result["run_id"] = getattr(run, "id", None)
                if wait:
                    run_result = run.wait()
                    result["status"] = getattr(run_result, "status", None)
                    result["text"] = run.text()
                else:
                    result["status"] = getattr(run, "status", None)
                    result["note"] = "Run started. Use cursor_agent_send with wait=true to get result."

        return _ok(result)
    except Exception as exc:
        logger.exception("cursor_agent_create failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_list
# ---------------------------------------------------------------------------

CURSOR_AGENT_LIST_SCHEMA = {
    "name": "cursor_agent_list",
    "description": "List Cursor Cloud Agents. Returns agent_id, name, summary, status, last_modified.",
    "parameters": {
        "type": "object",
        "properties": {
            "include_archived": {"type": "boolean", "description": "Include archived agents.", "default": False},
            "limit": {"type": "integer", "description": "Max results (default 50).", "default": 50},
        },
        "required": [],
    },
}


def _handle_cursor_agent_list(args: Dict[str, Any], **_) -> str:
    try:
        key = _api_key()
        include_archived = bool(args.get("include_archived", False))
        limit = int(args.get("limit", 50))

        with _bridge() as client:
            page = client.list_agents(runtime="cloud", include_archived=include_archived, api_key=key)
            agents = []
            count = 0
            for info in page.auto_paging_iter():
                if count >= limit:
                    break
                agents.append(_agent_info_dict(info))
                count += 1

        return _ok({"agents": agents, "count": len(agents)})
    except Exception as exc:
        logger.exception("cursor_agent_list failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_get
# ---------------------------------------------------------------------------

CURSOR_AGENT_GET_SCHEMA = {
    "name": "cursor_agent_get",
    "description": "Inspect a Cursor Cloud Agent by ID. Returns full agent info.",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The agent ID (e.g. bc-abc123)."},
        },
        "required": ["agent_id"],
    },
}


def _handle_cursor_agent_get(args: Dict[str, Any], **_) -> str:
    try:
        agent_id = args.get("agent_id", "").strip()
        if not agent_id:
            return _err("agent_id is required")
        key = _api_key()
        with _bridge() as client:
            info = client.get_agent(agent_id, api_key=key)
        return _ok(_agent_info_dict(info))
    except Exception as exc:
        logger.exception("cursor_agent_get failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_send
# ---------------------------------------------------------------------------

CURSOR_AGENT_SEND_SCHEMA = {
    "name": "cursor_agent_send",
    "description": (
        "Send a message to an existing Cursor Cloud Agent. "
        "Preserves full conversation context. Blocks until done by default."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The agent ID."},
            "message": {"type": "string", "description": "The message/prompt to send."},
            "wait": {"type": "boolean", "description": "Block until run finishes (default true).", "default": True},
            "model": {"type": "string", "description": "Optional per-send model override (default: composer-2.5)."},
        },
        "required": ["agent_id", "message"],
    },
}


def _handle_cursor_agent_send(args: Dict[str, Any], **_) -> str:
    try:
        from cursor_sdk import ModelSelection, SendOptions

        agent_id = args.get("agent_id", "").strip()
        message = args.get("message", "").strip()
        if not agent_id:
            return _err("agent_id is required")
        if not message:
            return _err("message is required")

        model_override = args.get("model") or DEFAULT_MODEL
        wait = args.get("wait", True)
        key = _api_key()

        with _bridge() as client:
            agent = client.resume_agent(agent_id)
            send_opts = SendOptions(model=ModelSelection(id=model_override))
            run = agent.send(message, send_opts)
            result = {"agent_id": agent_id, "run_id": getattr(run, "id", None)}
            if wait:
                run_result = run.wait()
                result["status"] = getattr(run_result, "status", None)
                result["text"] = run.text()
            else:
                result["status"] = getattr(run, "status", None)
                result["note"] = "Run started. Use cursor_agent_wait to poll."

        return _ok(result)
    except Exception as exc:
        logger.exception("cursor_agent_send failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_wait
# ---------------------------------------------------------------------------

CURSOR_AGENT_WAIT_SCHEMA = {
    "name": "cursor_agent_wait",
    "description": "Get the most recent run result for a Cursor Cloud Agent. Returns status and text output.",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The agent ID."},
        },
        "required": ["agent_id"],
    },
}


def _handle_cursor_agent_wait(args: Dict[str, Any], **_) -> str:
    try:
        agent_id = args.get("agent_id", "").strip()
        if not agent_id:
            return _err("agent_id is required")
        key = _api_key()
        with _bridge() as client:
            page = client.list_runs(agent_id, api_key=key, limit=1)
            items = list(page.auto_paging_iter())
            if not items:
                return _err(f"No runs found for agent {agent_id}")
            latest = items[0]
            return _ok({
                "agent_id": agent_id,
                "run_id": getattr(latest, "id", None),
                "status": getattr(latest, "status", None),
                "result": getattr(latest, "result", None),
                "duration_ms": getattr(latest, "duration_ms", None),
            })
    except Exception as exc:
        logger.exception("cursor_agent_wait failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_cancel
# ---------------------------------------------------------------------------

CURSOR_AGENT_CANCEL_SCHEMA = {
    "name": "cursor_agent_cancel",
    "description": "Cancel the active run of a Cursor Cloud Agent. Only works when status is 'running'.",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The agent ID."},
            "run_id": {"type": "string", "description": "The run ID to cancel. If omitted, cancels the most recent run."},
        },
        "required": ["agent_id"],
    },
}


def _handle_cursor_agent_cancel(args: Dict[str, Any], **_) -> str:
    try:
        agent_id = args.get("agent_id", "").strip()
        run_id = args.get("run_id", "").strip()
        if not agent_id:
            return _err("agent_id is required")
        key = _api_key()
        with _bridge() as client:
            if not run_id:
                page = client.list_runs(agent_id, api_key=key, limit=1)
                items = list(page.auto_paging_iter())
                if not items:
                    return _err(f"No runs found for agent {agent_id}")
                run_id = getattr(items[0], "id", None)
                if getattr(items[0], "status", None) != "running":
                    return _ok({
                        "agent_id": agent_id,
                        "run_id": run_id,
                        "status": getattr(items[0], "status", None),
                        "note": "Run is not currently running. Nothing cancelled.",
                    })
            client.cancel_run(run_id, agent_id=agent_id)
            return _ok({"agent_id": agent_id, "run_id": run_id, "cancelled": True})
    except Exception as exc:
        logger.exception("cursor_agent_cancel failed")
        return _err(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# cursor_agent_resume
# ---------------------------------------------------------------------------

CURSOR_AGENT_RESUME_SCHEMA = {
    "name": "cursor_agent_resume",
    "description": "Resume an existing Cursor Cloud Agent and send a follow-up message. Alias of cursor_agent_send.",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The agent ID to resume."},
            "message": {"type": "string", "description": "Follow-up message to send."},
            "wait": {"type": "boolean", "description": "Block until run finishes (default true).", "default": True},
        },
        "required": ["agent_id", "message"],
    },
}


def _handle_cursor_agent_resume(args: Dict[str, Any], **_) -> str:
    return _handle_cursor_agent_send(args)


# ---------------------------------------------------------------------------
# cursor_agent_archive / unarchive / delete
# ---------------------------------------------------------------------------

CURSOR_AGENT_ARCHIVE_SCHEMA = {
    "name": "cursor_agent_archive",
    "description": "Archive a Cursor Cloud Agent. Reversible with cursor_agent_unarchive.",
    "parameters": {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]},
}

CURSOR_AGENT_UNARCHIVE_SCHEMA = {
    "name": "cursor_agent_unarchive",
    "description": "Unarchive a previously archived Cursor Cloud Agent.",
    "parameters": {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]},
}

CURSOR_AGENT_DELETE_SCHEMA = {
    "name": "cursor_agent_delete",
    "description": "Permanently delete a Cursor Cloud Agent. Cannot be undone.",
    "parameters": {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]},
}


def _lifecycle_op(args: Dict[str, Any], op: str) -> str:
    try:
        from cursor_sdk import Agent

        agent_id = args.get("agent_id", "").strip()
        if not agent_id:
            return _err("agent_id is required")

        with _bridge() as client:
            agent = client.resume_agent(agent_id)
            fn = getattr(agent, op, None) or getattr(Agent, op, None)
            if fn is None:
                return _err(f"Operation '{op}' not available in this SDK version")
            # Agent.archive/unarchive/delete are classmethods taking agent_id
            if isinstance(fn, classmethod) or (hasattr(fn, "__func__") and hasattr(Agent, op)):
                getattr(Agent, op)(agent_id, client=client)
            else:
                fn()
        return _ok({"agent_id": agent_id, "operation": op, "success": True})
    except Exception as exc:
        logger.exception("cursor_agent_%s failed", op)
        return _err(f"{type(exc).__name__}: {exc}")


def _handle_cursor_agent_archive(args: Dict[str, Any], **_) -> str:
    return _lifecycle_op(args, "archive")


def _handle_cursor_agent_unarchive(args: Dict[str, Any], **_) -> str:
    return _lifecycle_op(args, "unarchive")


def _handle_cursor_agent_delete(args: Dict[str, Any], **_) -> str:
    return _lifecycle_op(args, "delete")


# ---------------------------------------------------------------------------
# cursor_agent_artifacts
# ---------------------------------------------------------------------------

CURSOR_AGENT_ARTIFACTS_SCHEMA = {
    "name": "cursor_agent_artifacts",
    "description": (
        "List files produced by a Cursor Cloud Agent. "
        "Optionally download a specific file to local disk."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The agent ID."},
            "download_path": {"type": "string", "description": "Remote artifact path to download."},
            "local_dest": {"type": "string", "description": "Local path to save downloaded file."},
        },
        "required": ["agent_id"],
    },
}


def _handle_cursor_agent_artifacts(args: Dict[str, Any], **_) -> str:
    try:
        agent_id = args.get("agent_id", "").strip()
        download_path = args.get("download_path", "")
        local_dest = args.get("local_dest", "")

        if not agent_id:
            return _err("agent_id is required")

        with _bridge() as client:
            agent = client.resume_agent(agent_id)
            artifacts = agent.list_artifacts()
            artifact_list = [
                {
                    "path": getattr(a, "path", None),
                    "size_bytes": getattr(a, "size_bytes", 0),
                    "updated_at": getattr(a, "updated_at", ""),
                }
                for a in artifacts
            ]

            result: dict = {"agent_id": agent_id, "artifacts": artifact_list, "count": len(artifact_list)}

            if download_path and local_dest:
                content = agent.download_artifact(download_path)
                dest = os.path.expanduser(local_dest)
                os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(content if isinstance(content, bytes) else content.encode())
                result["downloaded"] = {"remote": download_path, "local": dest}

        return _ok(result)
    except Exception as exc:
        logger.exception("cursor_agent_artifacts failed")
        return _err(f"{type(exc).__name__}: {exc}")
