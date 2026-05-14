# SOAS local-MCP

A Python MCP server you run on your **host machine** to give Claude Code (or
any MCP client) read access to SOAS through your own analyst account.

Unlike the production `mcp/` (Node, service-token, network-exposed), this one:

- runs over **stdio** (no network port at all — Claude Code launches it as a child process)
- authenticates using **your** SOAS JWT (stored at `~/.soas/token`), so it
  inherits your exact RBAC

## Install

```powershell
pip install -r local-mcp/requirements.txt
python -m local-mcp login --base-url http://localhost:8000 --username admin
```

## Register with Claude Code

Add this to your Claude Code MCP config (typically `~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "soas-local": {
      "command": "python",
      "args": ["-m", "local-mcp"],
      "cwd": "C:/path/to/SOAS"
    }
  }
}
```

## Tools exposed

| Tool                | Description                          |
|---------------------|--------------------------------------|
| `list_incidents`    | Recent incidents                     |
| `get_incident`      | One incident by id                   |
| `list_cases`        | Recent cases                         |
| `get_case`          | One case by id                       |
| `list_automations`  | All automations                      |
| `search_wiki`       | Full-text wiki search                |
| `run_saved_query`   | Execute a stored saved-query         |

All tools call the existing `/api/v1/*` routes with your bearer token. RBAC
is enforced server-side, so this MCP can never do anything you couldn't do
yourself in the UI.
