# cursor-hermes-plugin

A Hermes Agent plugin that brings full Cursor Cloud Agent management into your terminal — create, list, inspect, send messages, wait for results, cancel, resume, archive, and delete Cursor cloud agents without leaving Hermes.

## What this does

This plugin wraps the [Cursor Python SDK](https://cursor.com/docs/sdk/python) and exposes 13 tools that let your Hermes agent programmatically manage Cursor Cloud Agents. Write code, review PRs, run audits, fix bugs — delegate it all to Cursor's cloud sandbox while you keep the conversation in Hermes.

## Installation

```bash
# 1. Install cursor-sdk
cd /usr/local/lib/hermes-agent && venv/bin/pip install cursor-sdk

# 2. Clone the plugin
mkdir -p ~/.hermes/plugins
git clone https://github.com/fernandoabolafio/cursor-hermes-plugin.git ~/.hermes/plugins/cursor

# 3. Add your Cursor API key
echo 'CURSOR_API_KEY=crsr_your_key_here' >> ~/.hermes/.env

# 4. Enable the plugin
hermes config set plugins.enabled '["cursor"]'
# Then edit ~/.hermes/config.yaml and change it to YAML list format:
#   plugins:
#     enabled:
#       - cursor
```

Get your API key at [cursor.com/settings → Integrations](https://cursor.com/settings).

## Available Tools

| Tool | Description |
|------|-------------|
| `cursor_agent_create` | Create + start a cloud agent against a GitHub repo |
| `cursor_agent_list` | List all cloud agents |
| `cursor_agent_get` | Inspect an agent by ID |
| `cursor_agent_send` | Send a message to an existing agent |
| `cursor_agent_wait` | Poll for the latest run result |
| `cursor_agent_cancel` | Cancel an active run |
| `cursor_agent_resume` | Resume + send follow-up message |
| `cursor_agent_archive` | Archive an agent |
| `cursor_agent_unarchive` | Restore an archived agent |
| `cursor_agent_delete` | Permanently delete an agent |
| `cursor_agent_artifacts` | List / download workspace files |
| `cursor_models_list` | List available Cursor models |
| `cursor_repos_list` | List connected GitHub/GitLab repos |

All tools use **composer-2.5** by default (the recommended model for cloud agent tasks).

## Quick Start

Once installed and enabled, restart Hermes (or `/reset`) and you'll see `cursor` in `hermes tools list`. Then:

```
# What repos are connected?
cursor_repos_list()

# Create an agent to explore a repo
cursor_agent_create(
  repo_url="https://github.com/org/repo",
  branch="main",
  prompt="What does this project do?",
  wait=True
)

# Send follow-ups — conversation context is preserved
cursor_agent_send(
  agent_id="bc-abc123...",
  message="Add unit tests for src/auth.py"
)

# List all your agents
cursor_agent_list()
```

## Prerequisites

- Hermes Agent installed
- [cursor-sdk](https://pypi.org/project/cursor-sdk/) (`pip install cursor-sdk`)
- Cursor API key (user or service account; Team Admin keys not yet supported by the SDK)
- GitHub repos connected at [cursor.com/agents](https://cursor.com/agents)

## Architecture

The Cursor SDK uses a local bridge binary (`cursor-sdk-bridge`) as a gRPC proxy. The plugin launches the bridge per-call via `Client.launch_bridge()` and passes `api_key=` per operation. This keeps things stateless and avoids stale bridge processes.

Key implementation files:

```
~/.hermes/plugins/cursor/
├── plugin.yaml     Plugin manifest
├── client.py       Bridge bootstrap + health check
├── tools.py        13 tool schemas and handlers
└── __init__.py     register(ctx) entry point
```

## Model Support

`cursor_models_list()` returns all available models. Composer-2.5 is the default and recommended for most tasks, but the plugin supports per-send model overrides for any model in the Cursor catalog (Claude, GPT, Gemini, Grok, etc.).

## License

MIT
