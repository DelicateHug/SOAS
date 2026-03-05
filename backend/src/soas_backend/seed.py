"""Seed data module - populates default wiki pages, variables, secrets, and automations.

Runs on startup (idempotent). Uses app_settings.seed_version to track state.
"""

import logging
import uuid
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.database import async_session
from soas_backend.models.app_setting import AppSetting
from soas_backend.models.automation import Automation
from soas_backend.models.incident_variable import IncidentVariable
from soas_backend.models.user import User
from soas_backend.models.user_secret import UserSecret
from soas_backend.models.wiki import WikiPage
from soas_backend.services.automation_service import AutomationService
from soas_backend.services.incident_variable_service import IncidentVariableService
from soas_backend.services.user_secret_service import UserSecretService
from soas_backend.services.wiki_service import WikiService

logger = logging.getLogger(__name__)

CURRENT_SEED_VERSION = "2"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def seed_defaults() -> None:
    """Run all seed functions if not already seeded."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(AppSetting).where(AppSetting.key == "seed_version")
            )
            setting = result.scalar_one_or_none()

            if setting and setting.value >= CURRENT_SEED_VERSION:
                logger.info("Seed data already applied (v%s), skipping.", setting.value)
                return

            # Need at least one user for created_by references
            admin_result = await db.execute(
                select(User).order_by(User.created_at).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()
            if not admin_user:
                logger.info("No users yet - seeding deferred until first user registers.")
                return

            uid = admin_user.id
            logger.info("Seeding default data (created_by=%s)...", admin_user.username)

            await _seed_wiki_pages(db, uid)
            await _seed_incident_variables(db, uid)
            await _seed_user_secrets(db, uid)
            await _seed_automations(db, uid)
            await _seed_login_security_settings(db)

            # Mark seed version
            if setting:
                setting.value = CURRENT_SEED_VERSION
            else:
                db.add(AppSetting(
                    key="seed_version",
                    value=CURRENT_SEED_VERSION,
                    description="Tracks which seed data version has been applied",
                ))

            await db.commit()
            logger.info("Seed data applied successfully (v%s).", CURRENT_SEED_VERSION)
        except Exception:
            await db.rollback()
            logger.exception("Failed to apply seed data")


# ---------------------------------------------------------------------------
# Login security settings
# ---------------------------------------------------------------------------

async def _seed_login_security_settings(db: AsyncSession) -> None:
    """Seed default login security app_settings (idempotent)."""
    defaults = [
        ("max_failed_login_attempts", "5", "Max failed login attempts before lockout (0 = no lockout)"),
        ("failed_login_lockout_minutes", "30", "Minutes to lock an account after max failed attempts"),
    ]
    for key, value, description in defaults:
        existing = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        if existing.scalar_one_or_none() is None:
            db.add(AppSetting(key=key, value=value, description=description))
    await db.flush()


# ---------------------------------------------------------------------------
# Wiki pages
# ---------------------------------------------------------------------------

# Helper to build a node page entry
def _node_page(title: str, slug: str, node_type: str, category_slug: str,
               description: str, inputs: str, outputs: str, properties: str,
               example: str, tags: list[str] | None = None) -> dict:
    content = f"""# {title}

{description}

## Input Ports
{inputs}

## Output Ports
{outputs}

## Properties
{properties}

## Example Usage
{example}
"""
    return {
        "title": title,
        "slug": slug,
        "content": content,
        "parent_slug": category_slug,
        "tags": tags or ["node"],
        "linked_node_type": node_type,
    }


_APP_WIKI_PAGES: list[dict] = [
    # ── Top-level app pages ──
    {
        "title": "Getting Started",
        "slug": "getting-started",
        "icon": "rocket",
        "tags": ["guide"],
        "content": """# Getting Started with SOC on a Stick

Welcome to **SOC on a Stick (SOAS)** - a visual Security Operations Center platform for building, managing, and executing security automation workflows.

## First-Time Setup

1. **Register** - The first user to register automatically receives the **admin** role.
2. **Create Automations** - Navigate to **Automations > New** to open the Graph Editor.
3. **Define Incident Variables** - Go to **Admin > Incident Variables** to set up variables your automations can use.
4. **Configure Secrets** - Visit **My Secrets** to store API keys and credentials securely.

## Platform Overview

| Feature | Description |
|---------|-------------|
| **Incidents** | Track security events with severity, status, and assignment |
| **Cases** | Group related incidents into investigation cases |
| **Automations** | Visual node-based workflows executed by Celery workers |
| **Wiki** | Built-in documentation with version history |
| **User Secrets** | Encrypted per-user secrets for API keys and tokens |
| **Incident Variables** | Shared variables scoped to incidents at runtime |
| **Code Library** | Reusable Python code blocks for automation nodes |

## Key Concepts

- **Graph Editor**: Drag-and-drop node editor for building automations visually.
- **Nodes**: Building blocks of automations (conditions, loops, HTTP requests, etc.).
- **Execution**: Automations run as Celery tasks with full stdout/stderr capture.
- **Collaboration**: Real-time co-editing of automations via WebSocket.
""",
    },
    {
        "title": "Incidents",
        "slug": "incidents",
        "icon": "alert-triangle",
        "tags": ["guide", "incidents"],
        "content": """# Incidents

Incidents represent security events that require investigation and response.

## Creating an Incident

Navigate to **Incidents > New Incident** and fill in:
- **Title** - Brief description of the event
- **Severity** - Critical, High, Medium, Low, or Info
- **Source** - Where the event originated (e.g., SIEM, IDS, manual)
- **Summary** - Detailed description of what happened

## Incident Lifecycle

| Status | Description |
|--------|-------------|
| **Detected** | Initial state when created |
| **In Progress** | Analyst is actively investigating |
| **Resolved** | Root cause identified, remediation applied |
| **Closed** | Incident fully handled and documented |

## Features

- **Assignment** - Assign incidents to team members
- **Notes** - Add investigation notes and findings
- **Files** - Attach evidence files and screenshots
- **Timeline** - Automatic timeline of all actions taken
- **Automations** - Trigger automations directly from an incident
- **Incident Variables** - Store runtime data scoped to the incident
""",
    },
    {
        "title": "Cases",
        "slug": "cases",
        "icon": "folder",
        "tags": ["guide", "cases"],
        "content": """# Cases

Cases group related incidents into a single investigation.

## When to Use Cases

- Multiple incidents from the same attack campaign
- Related alerts that should be investigated together
- Ongoing investigations spanning multiple events

## Creating a Case

Navigate to **Cases > New Case** and provide:
- **Title** - Name for the investigation
- **Description** - What ties these incidents together
- **Priority** - High, Medium, or Low

## Case Features

- **Link Incidents** - Associate multiple incidents with a case
- **Case Notes** - Shared investigation notes
- **File Attachments** - Evidence and documentation
- **Timeline** - Unified timeline across all linked incidents
- **Form Submissions** - Fill out structured forms attached to the case
- **Automations** - Run automations in the context of a case
""",
    },
    {
        "title": "Automations",
        "slug": "automations",
        "icon": "zap",
        "tags": ["guide", "automations"],
        "content": """# Automations

Automations are visual workflows built using the Graph Editor. They execute Python code generated from node-based graphs.

## Creating an Automation

1. Navigate to **Automations > New**
2. Use the Graph Editor to add and connect nodes
3. Save the automation (it starts in **Draft** status)
4. Set status to **Active** when ready to use

## Automation Lifecycle

| Status | Description |
|--------|-------------|
| **Draft** | Work in progress, cannot be triggered |
| **Active** | Ready for manual or automated execution |
| **Inactive** | Temporarily disabled |

## Execution

- Automations run as Celery tasks on worker containers
- Each execution captures stdout, stderr, and result data
- View execution history and logs in the Execution detail page

## Input Parameters

Define input parameters on the automation to make it reusable:
- Use **Subgraph Input** nodes to define named parameters
- Parameters can have types (string, integer, boolean, list, dict)
- Default values are supported

## Triggers

- **Manual** - Execute from the UI or API
- **Incident** - Trigger when an incident matches tags
- **Scheduled** - Run on a cron schedule via Scheduled Jobs
- **Webhook** - Trigger via external webhook events
""",
    },
    {
        "title": "Graph Editor",
        "slug": "graph-editor",
        "icon": "git-branch",
        "tags": ["guide", "editor"],
        "content": """# Graph Editor

The Graph Editor is the visual interface for building automation workflows.

## Interface

- **Node Palette** - Left sidebar with all available node types organized by category
- **Canvas** - Central area for placing and connecting nodes
- **Property Panel** - Right sidebar for configuring selected node properties
- **Toolbar** - Top bar with save, compile preview, and validation actions

## Working with Nodes

1. **Add Nodes** - Click a node type in the palette or right-click the canvas
2. **Connect Nodes** - Drag from an output port to an input port
3. **Configure** - Select a node and edit its properties in the Property Panel
4. **Move** - Drag nodes to reposition them on the canvas

## Port Types

| Type | Color | Description |
|------|-------|-------------|
| **Flow** | Gray | Execution flow (order of operations) |
| **String** | Green | Text data |
| **Integer** | Blue | Whole numbers |
| **Float** | Teal | Decimal numbers |
| **Boolean** | Orange | True/False values |
| **List** | Purple | Ordered collections |
| **Dict** | Yellow | Key-value mappings |
| **Any** | White | Accepts any data type |

## Tips

- Use **Comment** nodes to document your workflow
- Use **Compile Preview** to see the generated Python code
- Use **Validate** to check for errors before saving
- Nodes with a documentation icon link to their wiki page
""",
    },
    {
        "title": "Wiki",
        "slug": "wiki-guide",
        "icon": "book",
        "tags": ["guide", "wiki"],
        "content": """# Wiki

The built-in Wiki provides documentation for your SOC team.

## Features

- **Hierarchical Pages** - Organize pages in a tree structure
- **Version History** - Every edit is versioned (up to 30 versions per page)
- **Full-Text Search** - Search across all wiki content
- **Tags** - Categorize pages with tags
- **Permissions** - Control who can read and edit each page
- **Node Linking** - Wiki pages can be linked to graph editor nodes

## Creating a Page

1. Navigate to **Wiki > New Page**
2. Enter a title (slug is auto-generated)
3. Write content using Markdown
4. Optionally set a parent page, tags, and icon

## Markdown Support

Wiki pages support full Markdown including:
- Headings, lists, tables
- Code blocks with syntax highlighting
- Links and images
- Task lists
""",
    },
    {
        "title": "User Secrets",
        "slug": "user-secrets-guide",
        "icon": "key",
        "tags": ["guide", "secrets"],
        "content": """# User Secrets

User Secrets store sensitive credentials (API keys, tokens, passwords) encrypted at rest.

## How It Works

- Each user has their own set of secrets
- Secrets are encrypted using AES before storage
- At automation runtime, secrets are decrypted and made available via the **Get User Secret** node
- Secrets marked as **Sensitive** cannot have their values retrieved via the API

## Managing Secrets

Navigate to **My Secrets** to:
- **Create** - Add a new secret with a name, description, and value
- **Update** - Change the value or description
- **Delete** - Remove a secret permanently

## Using Secrets in Automations

1. Create a secret (e.g., `VIRUSTOTAL_API_KEY`)
2. In your automation, add a **Get User Secret** node
3. Select the secret name from the dropdown
4. The decrypted value is available on the output port

## Admin View

Administrators can view all users' secret names (not values) at **Admin > User Secrets**.
""",
    },
    {
        "title": "Incident Variables",
        "slug": "incident-variables-guide",
        "icon": "database",
        "tags": ["guide", "variables"],
        "content": """# Incident Variables

Incident Variables are named data slots that automations can read and write at runtime, scoped to a specific incident.

## How It Works

- **Definitions** are created by admins (name, description, enabled flag)
- **Values** are stored in Redis at runtime, keyed by incident ID
- Automations use **Get Incident Var** / **Set Incident Var** nodes to access them

## Managing Definitions

Navigate to **Admin > Incident Variables** to:
- Create new variable definitions
- Enable or disable variables
- Mark variables as sensitive

## Use Cases

- `severity_override` - Let automations adjust incident severity
- `analyst_notes` - Store analyst findings during triage
- `escalation_level` - Track escalation tier (1-3)
- `affected_hosts` - Record affected hostnames/IPs
- `triage_verdict` - Store triage outcome (true_positive, false_positive, benign)
""",
    },
    {
        "title": "Administration",
        "slug": "administration",
        "icon": "settings",
        "tags": ["guide", "admin"],
        "content": """# Administration

## User Management

Navigate to **Admin > Users** to:
- View all registered users
- Create new users (generates a temporary password)
- Activate or deactivate accounts
- Assign roles

## Roles & Permissions

SOAS uses role-based access control (RBAC):

| Role | Description |
|------|-------------|
| **admin** | Full access to everything |
| **soc_manager** | Manage incidents, cases, and automations |
| **soc_analyst_l3** | Advanced analysis and automation editing |
| **soc_analyst_l2** | Standard analysis and execution |
| **soc_analyst_l1** | Basic triage and viewing |
| **viewer** | Read-only access |

## Application Settings

- **SOAS Variables** - Application-level key-value store with RBAC
- **Webhooks** - Configure outgoing webhook notifications
- **Webhook Sources** - Define incoming event sources
- **Normalization** - Event field mapping rules
- **Form Definitions** - Create structured forms for cases
- **Scheduled Jobs** - Configure cron-based automation schedules

## Monitoring

The monitoring dashboard shows:
- Service health and quorum status
- Request metrics and error rates
- Worker status and queue depths
""",
    },
    {
        "title": "API Reference",
        "slug": "api-reference",
        "icon": "code",
        "tags": ["guide", "api"],
        "content": """# API Reference

SOAS exposes a RESTful API at `/api/v1/`. Interactive documentation is available at `/api/docs` (Swagger UI).

## Authentication

All API requests (except `/auth/login`, `/auth/register`, `/auth/registration-open`) require a JWT bearer token:

```
Authorization: Bearer <access_token>
```

Tokens are obtained via `POST /api/v1/auth/login`.

## Core Endpoints

| Resource | Prefix | Operations |
|----------|--------|------------|
| **Auth** | `/auth` | login, register, refresh, logout, MFA, change-password |
| **Incidents** | `/incidents` | CRUD, assign, notes, files, timeline |
| **Cases** | `/cases` | CRUD, link incidents, notes, files |
| **Automations** | `/automations` | CRUD, execute, permissions, dependencies |
| **Graph Editor** | `/graph-editor` | node catalog, validate, compile preview |
| **Executions** | `/executions` | list, detail, WebSocket streaming |
| **Wiki** | `/wiki` | CRUD, tree, search, versions, permissions |
| **User Secrets** | `/user-secrets` | CRUD, admin view |
| **Incident Variables** | `/incident-variables` | CRUD |
| **Code Library** | `/code-library` | CRUD, favorites |
| **Users** | `/users` | admin CRUD, roles |
| **SOAS Variables** | `/soas-variables` | CRUD, permissions |
| **Webhooks** | `/webhooks` | CRUD, logs |
| **Monitoring** | `/monitoring` | health, metrics, alerts |
| **Settings** | `/settings` | app settings CRUD |

## WebSocket Endpoints

- `/api/v1/ws/executions/{execution_id}` - Real-time execution output
- `/api/v1/ws/collaboration/{automation_id}` - Graph editor collaboration
- `/api/v1/ws/monitoring` - Live monitoring updates
""",
    },
]


# ── Node category pages (children of graph-editor) ──
_NODE_CATEGORY_PAGES: list[dict] = [
    {"title": "Control Flow Nodes", "slug": "nodes-control-flow", "parent_slug": "graph-editor", "icon": "git-branch", "tags": ["nodes", "control-flow"],
     "content": "# Control Flow Nodes\n\nNodes that control the execution order and branching of your automation.\n\nThese nodes determine *when* and *how* your workflow progresses."},
    {"title": "Custom Code Nodes", "slug": "nodes-custom-code", "parent_slug": "graph-editor", "icon": "code", "tags": ["nodes", "code"],
     "content": "# Custom Code Nodes\n\nNodes for executing custom Python code within your automation."},
    {"title": "Variable Nodes", "slug": "nodes-variables", "parent_slug": "graph-editor", "icon": "variable", "tags": ["nodes", "variables"],
     "content": "# Variable Nodes\n\nNodes for reading and writing variables at different scopes (global, per-execution, SOAS application, incident)."},
    {"title": "Input/Output Nodes", "slug": "nodes-io", "parent_slug": "graph-editor", "icon": "terminal", "tags": ["nodes", "io"],
     "content": "# Input/Output Nodes\n\nNodes for printing output and receiving user input during execution."},
    {"title": "File I/O Nodes", "slug": "nodes-file-io", "parent_slug": "graph-editor", "icon": "file", "tags": ["nodes", "file"],
     "content": "# File I/O Nodes\n\nNodes for reading from and writing to files on the worker filesystem."},
    {"title": "Network Nodes", "slug": "nodes-network", "parent_slug": "graph-editor", "icon": "globe", "tags": ["nodes", "network"],
     "content": "# Network Nodes\n\nNodes for making HTTP requests to external APIs and services."},
    {"title": "Database Nodes", "slug": "nodes-database", "parent_slug": "graph-editor", "icon": "database", "tags": ["nodes", "database"],
     "content": "# Database Nodes\n\nNodes for executing SQL queries against databases."},
    {"title": "Data Processing Nodes", "slug": "nodes-data-processing", "parent_slug": "graph-editor", "icon": "layers", "tags": ["nodes", "data"],
     "content": "# Data Processing Nodes\n\nNodes for parsing, transforming, and aggregating data."},
    {"title": "Math Nodes", "slug": "nodes-math", "parent_slug": "graph-editor", "icon": "calculator", "tags": ["nodes", "math"],
     "content": "# Math Nodes\n\nNodes for performing arithmetic operations."},
    {"title": "String Nodes", "slug": "nodes-string", "parent_slug": "graph-editor", "icon": "type", "tags": ["nodes", "string"],
     "content": "# String Nodes\n\nNodes for manipulating and transforming text strings."},
    {"title": "List Nodes", "slug": "nodes-list", "parent_slug": "graph-editor", "icon": "list", "tags": ["nodes", "list"],
     "content": "# List Nodes\n\nNodes for working with lists (append, filter, map, reduce)."},
    {"title": "Subgraph Nodes", "slug": "nodes-subgraph", "parent_slug": "graph-editor", "icon": "box", "tags": ["nodes", "subgraph"],
     "content": "# Subgraph Nodes\n\nNodes for defining reusable sub-automations and running other automations."},
    {"title": "Incident Nodes", "slug": "nodes-incident", "parent_slug": "graph-editor", "icon": "shield", "tags": ["nodes", "incident"],
     "content": "# Incident Nodes\n\nNodes for reading incident data and working with incident-scoped variables."},
    {"title": "Secrets Nodes", "slug": "nodes-secrets", "parent_slug": "graph-editor", "icon": "key", "tags": ["nodes", "secrets"],
     "content": "# Secrets Nodes\n\nNodes for accessing encrypted user secrets at runtime."},
    {"title": "Debugging Nodes", "slug": "nodes-debugging", "parent_slug": "graph-editor", "icon": "bug", "tags": ["nodes", "debug"],
     "content": "# Debugging Nodes\n\nNodes for debugging and documenting your automations."},
]


# ── Individual node pages ──
_NODE_PAGES: list[dict] = [
    # Control Flow
    _node_page("Start Node", "node-start", "start", "nodes-control-flow",
               "The entry point of every automation. Execution begins here. If the automation defines input parameters, they appear as output ports on this node.",
               "None - this is the entry point.", "- **exec_out** (Flow) - Execution continues to the next node\n- Dynamic output ports for each automation input parameter",
               "None", "Every automation must have exactly one Start node. Connect its `exec_out` port to the first action in your workflow."),
    _node_page("End Node", "node-end", "end", "nodes-control-flow",
               "Marks the end of an execution path. The automation stops when an End node is reached.",
               "- **exec_in** (Flow) - Incoming execution\n- **result** (Any) - Optional result value", "None - execution terminates here.",
               "None", "Place an End node at the end of each branch. Optionally pass a result value for the execution output."),
    _node_page("If Node", "node-if", "if", "nodes-control-flow",
               "Conditional branching node. Evaluates a condition and routes execution to the **true** or **false** branch.",
               "- **exec_in** (Flow) - Incoming execution\n- **value** (Any) - Value to evaluate\n- **condition** (Any) - Comparison value (for operators that need it)",
               "- **true** (Flow) - Executes when condition is true\n- **false** (Flow) - Executes when condition is false\n- **result** (Boolean) - The evaluation result",
               "- **operator** - Comparison operator (is_truthy, equals, contains, greater_than, matches_regex, custom, etc.)\n- **compare_value** - Value to compare against\n- **condition_code** - Custom Python expression (when operator is 'custom')",
               "Use the If node to route incidents by severity: connect the incident severity to the `value` port, set operator to `equals`, and compare_value to `critical`."),
    _node_page("For Loop Node", "node-for-loop", "for_loop", "nodes-control-flow",
               "Iterates over a collection. For each element, the loop body executes with the current item and index.",
               "- **exec_in** (Flow) - Incoming execution\n- **iterable** (Any) - Collection to iterate over",
               "- **loop_body** (Flow) - Executes for each iteration\n- **completed** (Flow) - Executes after all iterations\n- **item** (Any) - Current element\n- **index** (Integer) - Current index",
               "- **iterable_code** - Python expression for the collection (e.g., `range(10)`)",
               "Use to process a list of IP addresses: connect a list to the `iterable` port, then use the `item` output in an HTTP Request node."),
    _node_page("While Loop Node", "node-while-loop", "while_loop", "nodes-control-flow",
               "Repeats execution while a condition remains true. Has a configurable maximum iteration limit to prevent infinite loops.",
               "- **exec_in** (Flow) - Incoming execution\n- **condition** (Any) - Condition variable",
               "- **loop_body** (Flow) - Executes each iteration\n- **completed** (Flow) - Executes when condition becomes false\n- **iteration** (Integer) - Current iteration count",
               "- **condition_code** - Python expression checked before each iteration\n- **max_iterations** - Safety limit (default: 10000)",
               "Use to poll an API until a job completes: set condition_code to `status != 'complete'` and add an HTTP Request in the loop body."),
    _node_page("Merge Node", "node-merge", "merge", "nodes-control-flow",
               "Converges multiple execution paths back into one. Supports `first_in` (continues on first arrival) or `wait_all` (waits for all paths).",
               "- **exec_in_1** through **exec_in_N** (Flow) - Multiple incoming paths (2-8)",
               "- **exec_out** (Flow) - Continues after merge",
               "- **strategy** - `first_in` or `wait_all`\n- **num_inputs** - Number of input paths (2-8)",
               "After an If node splits into true/false branches, use a Merge node to rejoin them before continuing to the End node."),
    _node_page("Thread Node", "node-thread", "thread", "nodes-control-flow",
               "Spawns parallel execution threads. Each output executes concurrently.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **thread_1** through **thread_N** (Flow) - Parallel execution paths (2-8)",
               "- **num_threads** - Number of parallel threads (2-8)",
               "Use to run multiple HTTP requests in parallel: connect each thread output to a different HTTP Request node, then join with a Thread Join node."),
    _node_page("Thread Join Node", "node-thread-join", "thread_join", "nodes-control-flow",
               "Synchronizes parallel threads. Waits for all incoming threads to complete before continuing.",
               "- **thread_1** through **thread_N** (Flow) - Incoming parallel paths (2-8)",
               "- **exec_out** (Flow) - Continues after all threads complete",
               "- **num_inputs** - Number of threads to wait for (2-8)",
               "Place after a Thread node to wait for all parallel tasks to finish before proceeding."),
    _node_page("Try/Catch Node", "node-try-catch", "try_catch", "nodes-control-flow",
               "Exception handling. Wraps a block of execution in error handling - if an error occurs, the catch branch executes.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **try** (Flow) - Normal execution path\n- **catch** (Flow) - Error handling path\n- **finally** (Flow) - Always executes\n- **error** (String) - Error message if caught",
               "None",
               "Wrap HTTP requests in a Try/Catch to handle network errors gracefully."),

    # Custom Code
    _node_page("Code Node", "node-code", "code", "nodes-custom-code",
               "Executes custom Python code. The code has access to all input port values as local variables and can set output values.",
               "- **exec_in** (Flow) - Incoming execution\n- **input_1** through **input_3** (Any) - Input data",
               "- **exec_out** (Flow) - Continues after code executes\n- **output** (Any) - Return value from the code",
               "- **code** - Python code to execute\n- **language** - Programming language (default: python)\n- **description** - What this code does",
               "```python\n# Access inputs via their port names\nresult = input_1.upper() + ' - ' + str(input_2)\noutput = result\n```"),

    # Variables
    _node_page("Get Variable", "node-get-variable", "get_variable", "nodes-variables",
               "Reads a global variable value. Global variables persist across nodes within a single execution.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after read\n- **value** (Any) - The variable's current value",
               "- **variable_name** - Name of the global variable to read",
               "Use to retrieve a counter or accumulated result set earlier in the workflow."),
    _node_page("Set Variable", "node-set-variable", "set_variable", "nodes-variables",
               "Sets a global variable value. The value persists for the rest of the execution.",
               "- **exec_in** (Flow) - Incoming execution\n- **value** (Any) - Value to store",
               "- **exec_out** (Flow) - Continues after write",
               "- **variable_name** - Name of the global variable to set",
               "Use to store intermediate results that other nodes need to access later."),
    _node_page("Get Case Variable", "node-get-case-variable", "get_case_variable", "nodes-variables",
               "Reads a per-execution (case) variable. Case variables are isolated to the current execution instance.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after read\n- **value** (Any) - The variable's current value",
               "- **variable_name** - Name of the case variable to read",
               "Similar to Get Variable but scoped to the current execution context."),
    _node_page("Set Case Variable", "node-set-case-variable", "set_case_variable", "nodes-variables",
               "Sets a per-execution (case) variable value.",
               "- **exec_in** (Flow) - Incoming execution\n- **value** (Any) - Value to store",
               "- **exec_out** (Flow) - Continues after write",
               "- **variable_name** - Name of the case variable to set",
               "Use for execution-scoped state that should not leak between runs."),
    _node_page("Get SOAS Variable", "node-get-soas-var", "get_soas_var", "nodes-variables",
               "Reads a SOAS application-level variable. These are persistent, permission-controlled variables stored in the database.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after read\n- **value** (Any) - The variable's current value",
               "- **variable_name** - Select the SOAS variable to read",
               "Use to read application-wide configuration like API base URLs or feature flags."),
    _node_page("Set SOAS Variable", "node-set-soas-var", "set_soas_var", "nodes-variables",
               "Writes a SOAS application-level variable. Requires appropriate permissions.",
               "- **exec_in** (Flow) - Incoming execution\n- **value** (Any) - Value to store",
               "- **exec_out** (Flow) - Continues after write",
               "- **variable_name** - Select the SOAS variable to write",
               "Use to update application state that persists across executions and is shared between users."),

    # Incident Variables
    _node_page("Get Incident Variable", "node-get-incident-var", "get_incident_var", "nodes-incident",
               "Reads an incident-scoped variable from Redis/Postgres. The variable must be defined in Admin > Incident Variables.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after read\n- **value** (Any) - The variable's current value",
               "- **variable_name** - Select the incident variable to read",
               "Use in incident-triggered automations to read previously stored triage data."),
    _node_page("Set Incident Variable", "node-set-incident-var", "set_incident_var", "nodes-incident",
               "Writes an incident-scoped variable to Redis. The variable definition must exist in Admin > Incident Variables.",
               "- **exec_in** (Flow) - Incoming execution\n- **value** (Any) - Value to store",
               "- **exec_out** (Flow) - Continues after write",
               "- **variable_name** - Select the incident variable to write",
               "Use to store triage verdicts, escalation levels, or analyst notes on an incident."),
    _node_page("Get Incident Data", "node-get-incident-data", "get_incident_data", "nodes-incident",
               "Retrieves all data for the current incident (title, severity, status, metadata, etc.).",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after read\n- **data** (Dict) - Full incident data dictionary",
               "None",
               "Use at the start of incident-triggered automations to access incident details for decision-making."),
    _node_page("Get Group Incidents", "node-get-group-incidents", "get_group_incidents", "nodes-incident",
               "Gets all incidents in the current case/group.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after read\n- **incidents** (List) - List of all incident data dictionaries",
               "None",
               "Use in case-triggered automations to process all related incidents."),
    _node_page("Get Group Incident By Index", "node-get-group-incident", "get_group_incident", "nodes-incident",
               "Gets a specific incident from the group by its zero-based index.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues\n- **incident** (Dict) - Incident data at the given index",
               "- **index** - Zero-based index of the incident to retrieve",
               "Use with a For Loop to iterate through group incidents by index."),
    _node_page("Get Group Incident Count", "node-get-group-incident-count", "get_group_incident_count", "nodes-incident",
               "Returns the number of incidents in the current case/group.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues\n- **count** (Integer) - Number of incidents",
               "None",
               "Use to check how many incidents are in a case before processing."),

    # Secrets
    _node_page("Get User Secret", "node-get-user-secret", "get_user_secret", "nodes-secrets",
               "Retrieves a decrypted user secret at runtime. The secret must be created in My Secrets. The executing user's secrets are resolved.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues\n- **value** (String) - Decrypted secret value",
               "- **secret_name** - Select the user secret to read",
               "Use to inject API keys into HTTP Request nodes without hardcoding them in the graph."),

    # I/O
    _node_page("Print Node", "node-print", "print", "nodes-io",
               "Outputs a message to the execution log (stdout). Useful for debugging and status updates.",
               "- **exec_in** (Flow) - Incoming execution\n- **value** (Any) - Value to print",
               "- **exec_out** (Flow) - Continues after print",
               "- **message** - Static message text (used if no value connected)",
               "Connect any data port to see its value in the execution output. Great for debugging."),
    _node_page("Input Node", "node-input", "input", "nodes-io",
               "Prompts for user input during execution. Pauses the automation until input is provided.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues after input received\n- **value** (String) - The user's input",
               "- **prompt** - Message to display to the user",
               "Use for interactive automations that require analyst decisions mid-execution."),

    # File I/O
    _node_page("File Read Node", "node-file-read", "file_read", "nodes-file-io",
               "Reads the contents of a file from the worker filesystem.",
               "- **exec_in** (Flow) - Incoming execution\n- **path** (String) - File path to read",
               "- **exec_out** (Flow) - Continues after read\n- **content** (String) - File contents",
               "None",
               "Use to read configuration files, log files, or data exports."),
    _node_page("File Write Node", "node-file-write", "file_write", "nodes-file-io",
               "Writes content to a file on the worker filesystem.",
               "- **exec_in** (Flow) - Incoming execution\n- **path** (String) - File path to write\n- **content** (String) - Content to write",
               "- **exec_out** (Flow) - Continues after write",
               "None",
               "Use to save reports, export data, or create temporary files for processing."),

    # Network
    _node_page("HTTP Request Node", "node-http-request", "http_request", "nodes-network",
               "Makes HTTP requests to external APIs. Supports GET, POST, PUT, DELETE, and other methods.",
               "- **exec_in** (Flow) - Incoming execution\n- **url** (String) - Request URL\n- **body** (Any) - Request body",
               "- **exec_out** (Flow) - Continues after response\n- **response** (Dict) - Response object with status, headers, body\n- **status_code** (Integer) - HTTP status code\n- **body** (Any) - Parsed response body",
               "- **url** - Target URL\n- **method** - HTTP method (GET, POST, PUT, DELETE)\n- **headers** - JSON object of headers\n- **body** - Request body content",
               "```\nURL: https://api.example.com/lookup\nMethod: POST\nHeaders: {\"Authorization\": \"Bearer {{api_key}}\"}\nBody: {\"query\": \"8.8.8.8\"}\n```"),

    # Database
    _node_page("Database Query Node", "node-database-query", "database_query", "nodes-database",
               "Executes SQL queries against a database. Use with caution - ensure queries are safe.",
               "- **exec_in** (Flow) - Incoming execution\n- **query** (String) - SQL query\n- **params** (Dict) - Query parameters",
               "- **exec_out** (Flow) - Continues after query\n- **rows** (List) - Query result rows\n- **row_count** (Integer) - Number of rows affected/returned",
               "None",
               "Use for custom database lookups that aren't covered by built-in nodes. Always use parameterized queries."),

    # Data Processing
    _node_page("JSON Parse Node", "node-json-parse", "json_parse", "nodes-data-processing",
               "Parses a JSON string into a Python object (dict, list, etc.).",
               "- **exec_in** (Flow) - Incoming execution\n- **input** (String) - JSON string to parse",
               "- **exec_out** (Flow) - Continues\n- **output** (Any) - Parsed Python object",
               "None",
               "Use after an HTTP Request to parse the response body from a JSON string."),
    _node_page("JSON Stringify Node", "node-json-stringify", "json_stringify", "nodes-data-processing",
               "Converts a Python object to a JSON string.",
               "- **exec_in** (Flow) - Incoming execution\n- **input** (Any) - Object to serialize",
               "- **exec_out** (Flow) - Continues\n- **output** (String) - JSON string",
               "None",
               "Use to prepare data for HTTP Request body or file output."),
    _node_page("Data Aggregation Node", "node-data-aggregation", "data_aggregation", "nodes-data-processing",
               "Combines data from multiple input sources into a single output.",
               "- **exec_in** (Flow) - Incoming execution\n- **input_1** through **input_4** (Any) - Data sources",
               "- **exec_out** (Flow) - Continues\n- **output** (Dict) - Aggregated data",
               "None",
               "Use to merge results from multiple parallel HTTP requests or data lookups."),

    # Math
    _node_page("Add Node", "node-add", "add", "nodes-math",
               "Adds two numbers together.", "- **exec_in** (Flow)\n- **a** (Float) - First number\n- **b** (Float) - Second number",
               "- **exec_out** (Flow)\n- **result** (Float) - Sum", "None", "Connect two numeric outputs to get their sum."),
    _node_page("Subtract Node", "node-subtract", "subtract", "nodes-math",
               "Subtracts the second number from the first.", "- **exec_in** (Flow)\n- **a** (Float)\n- **b** (Float)",
               "- **exec_out** (Flow)\n- **result** (Float) - Difference", "None", "a - b"),
    _node_page("Multiply Node", "node-multiply", "multiply", "nodes-math",
               "Multiplies two numbers.", "- **exec_in** (Flow)\n- **a** (Float)\n- **b** (Float)",
               "- **exec_out** (Flow)\n- **result** (Float) - Product", "None", "a * b"),
    _node_page("Divide Node", "node-divide", "divide", "nodes-math",
               "Divides the first number by the second.", "- **exec_in** (Flow)\n- **a** (Float)\n- **b** (Float)",
               "- **exec_out** (Flow)\n- **result** (Float) - Quotient", "None", "a / b (raises error if b is 0)"),
    _node_page("Modulo Node", "node-modulo", "modulo", "nodes-math",
               "Returns the remainder of dividing the first number by the second.", "- **exec_in** (Flow)\n- **a** (Float)\n- **b** (Float)",
               "- **exec_out** (Flow)\n- **result** (Float) - Remainder", "None", "a % b"),
    _node_page("Power Node", "node-power", "power", "nodes-math",
               "Raises the first number to the power of the second.", "- **exec_in** (Flow)\n- **a** (Float)\n- **b** (Float)",
               "- **exec_out** (Flow)\n- **result** (Float) - Result", "None", "a ** b"),

    # String Operations
    _node_page("String Concat Node", "node-string-concat", "string_concat", "nodes-string",
               "Concatenates two or more strings together.",
               "- **exec_in** (Flow)\n- **a** (String) - First string\n- **b** (String) - Second string",
               "- **exec_out** (Flow)\n- **result** (String) - Concatenated string", "None", "Joins strings: 'Hello' + ' ' + 'World' = 'Hello World'"),
    _node_page("String Split Node", "node-string-split", "string_split", "nodes-string",
               "Splits a string into a list using a delimiter.",
               "- **exec_in** (Flow)\n- **input** (String) - String to split\n- **delimiter** (String) - Split character/pattern",
               "- **exec_out** (Flow)\n- **result** (List) - List of substrings", "None", "Split '10.0.0.1,10.0.0.2' by ',' to get ['10.0.0.1', '10.0.0.2']"),
    _node_page("String Replace Node", "node-string-replace", "string_replace", "nodes-string",
               "Finds and replaces text within a string.",
               "- **exec_in** (Flow)\n- **input** (String) - Source string\n- **find** (String) - Text to find\n- **replace** (String) - Replacement text",
               "- **exec_out** (Flow)\n- **result** (String) - Modified string", "None", "Replace 'http://' with 'https://' in URLs."),
    _node_page("String Format Node", "node-string-format", "string_format", "nodes-string",
               "Formats a string using template placeholders.",
               "- **exec_in** (Flow)\n- **template** (String) - Format template\n- **values** (Dict) - Values to insert",
               "- **exec_out** (Flow)\n- **result** (String) - Formatted string", "None", "Template: 'Alert: {title} (Severity: {severity})'"),
    _node_page("Regex Match Node", "node-regex-match", "regex_match", "nodes-string",
               "Finds all matches of a regular expression pattern in a string.",
               "- **exec_in** (Flow)\n- **input** (String) - String to search\n- **pattern** (String) - Regex pattern",
               "- **exec_out** (Flow)\n- **matches** (List) - List of matches\n- **found** (Boolean) - Whether any matches were found", "None",
               "Extract IP addresses: pattern `\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}`"),
    _node_page("Regex Replace Node", "node-regex-replace", "regex_replace", "nodes-string",
               "Finds and replaces text using regular expressions.",
               "- **exec_in** (Flow)\n- **input** (String) - Source string\n- **pattern** (String) - Regex pattern\n- **replacement** (String) - Replacement text",
               "- **exec_out** (Flow)\n- **result** (String) - Modified string", "None", "Redact email addresses: pattern `[\\w.]+@[\\w.]+` replacement `[REDACTED]`"),

    # List Operations
    _node_page("List Append Node", "node-list-append", "list_append", "nodes-list",
               "Appends an element to the end of a list.",
               "- **exec_in** (Flow)\n- **list** (List) - Existing list\n- **item** (Any) - Item to append",
               "- **exec_out** (Flow)\n- **result** (List) - Updated list", "None", "Build up a list of findings as you process incidents."),
    _node_page("List Filter Node", "node-list-filter", "list_filter", "nodes-list",
               "Filters list elements based on a condition.",
               "- **exec_in** (Flow)\n- **list** (List) - List to filter",
               "- **exec_out** (Flow)\n- **result** (List) - Filtered list", "None", "Filter a list of alerts to only include critical severity."),
    _node_page("List Map Node", "node-list-map", "list_map", "nodes-list",
               "Transforms each element in a list using an expression.",
               "- **exec_in** (Flow)\n- **list** (List) - List to transform",
               "- **exec_out** (Flow)\n- **result** (List) - Transformed list", "None", "Extract just the IP addresses from a list of alert objects."),
    _node_page("List Reduce Node", "node-list-reduce", "list_reduce", "nodes-list",
               "Reduces a list to a single value using an accumulator expression.",
               "- **exec_in** (Flow)\n- **list** (List) - List to reduce",
               "- **exec_out** (Flow)\n- **result** (Any) - Accumulated result", "None", "Sum up all severity scores from a list of incidents."),

    # Subgraphs
    _node_page("Subgraph Node", "node-subgraph", "subgraph", "nodes-subgraph",
               "A reusable container that encapsulates a group of nodes. Think of it as a function in code.",
               "- Dynamic based on subgraph inputs", "- Dynamic based on subgraph outputs",
               "None", "Group related nodes into a subgraph for reuse and cleaner automation layout."),
    _node_page("Subgraph Input Node", "node-subgraph-input", "subgraph_input", "nodes-subgraph",
               "Defines an input parameter for the automation. Appears as an output port on the Start node at execution time.",
               "None",
               "- **value** (Any) - The parameter value provided at execution",
               "- **port_name** - Select the automation input parameter\n- **port_type_setting** - Data type of this input\n- **description** - What this input is for\n- **default_value** - Default when not provided",
               "Add a Subgraph Input named 'target_ip' to make your automation accept an IP address parameter."),
    _node_page("Subgraph Output Node", "node-subgraph-output", "subgraph_output", "nodes-subgraph",
               "Defines an output of a subgraph or automation result.",
               "- **exec_in** (Flow)\n- **value** (Any) - Value to output",
               "None",
               "- **port_name** - Name for this output\n- **port_type_setting** - Data type of this output",
               "Use to define what your automation returns as its result."),
    _node_page("Run Automation Node", "node-run-automation", "run_automation", "nodes-subgraph",
               "Executes another automation as a sub-automation. Can run synchronously (wait for result) or asynchronously (fire and forget).",
               "- **exec_in** (Flow) - Incoming execution\n- Dynamic input ports matching the target automation's parameters",
               "- **exec_out** (Flow) - Continues after execution\n- **result** (Any) - Result from the sub-automation (sync only)",
               "- **automation_id** - Select the automation to run\n- **synchronous** - Wait for completion (true) or fire-and-forget (false)",
               "Use to chain automations: a triage automation can call a remediation automation based on its findings."),

    # Debugging
    _node_page("Breakpoint Node", "node-breakpoint", "breakpoint", "nodes-debugging",
               "Pauses execution for debugging. The execution will pause at this point until manually resumed.",
               "- **exec_in** (Flow) - Incoming execution",
               "- **exec_out** (Flow) - Continues when resumed",
               "None", "Place before a critical section to inspect variable values in the debug view."),
    _node_page("Comment Node", "node-comment", "comment", "nodes-debugging",
               "A documentation node that does not affect execution. Use to add notes and explanations directly on the canvas.",
               "None", "None",
               "- **text** - Note text visible on the canvas",
               "Add comments to explain complex logic or document requirements."),
]


# ---------------------------------------------------------------------------
# Incident variables
# ---------------------------------------------------------------------------

_INCIDENT_VARIABLES: list[dict] = [
    {"name": "severity_override", "description": "Override the auto-detected severity level", "default_enabled": True, "sensitive": False},
    {"name": "analyst_notes", "description": "Free-form notes from the assigned analyst", "default_enabled": True, "sensitive": False},
    {"name": "escalation_level", "description": "Current escalation tier (1-3)", "default_enabled": True, "sensitive": False},
    {"name": "triage_verdict", "description": "Triage outcome: true_positive, false_positive, benign", "default_enabled": True, "sensitive": False},
    {"name": "affected_hosts", "description": "Comma-separated list of affected hostnames/IPs", "default_enabled": True, "sensitive": False},
    {"name": "containment_status", "description": "Whether containment actions have been taken", "default_enabled": False, "sensitive": False},
    {"name": "ioc_indicators", "description": "Indicators of compromise discovered during analysis", "default_enabled": False, "sensitive": False},
    {"name": "remediation_steps", "description": "Steps taken or planned for remediation", "default_enabled": False, "sensitive": False},
]


# ---------------------------------------------------------------------------
# User secrets
# ---------------------------------------------------------------------------

_USER_SECRETS: list[dict] = [
    {"name": "EXAMPLE_API_KEY", "description": "Example API key for testing HTTP Request nodes (replace with real value)", "value": "replace-me", "sensitive": True},
    {"name": "WEBHOOK_SECRET", "description": "Secret for webhook signature verification", "value": "replace-me", "sensitive": True},
    {"name": "VIRUSTOTAL_API_KEY", "description": "VirusTotal API key for threat intelligence lookups", "value": "", "sensitive": True},
    {"name": "SLACK_WEBHOOK_URL", "description": "Slack webhook URL for notifications", "value": "", "sensitive": False},
]


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------

def _make_id() -> str:
    return str(uuid.uuid4())


def _hello_world_graph() -> dict:
    start_id = _make_id()
    print_id = _make_id()
    end_id = _make_id()
    return {
        "metadata": {"name": "Hello World", "description": "Simple example automation", "version": 1},
        "nodes": [
            {"id": start_id, "type": "start", "name": "Start", "position": {"x": 100, "y": 200}, "properties": {}, "input_ports": [], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": print_id, "type": "print", "name": "Print Greeting", "position": {"x": 400, "y": 200}, "properties": {"message": "Hello from SOC on a Stick!"}, "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": end_id, "type": "end", "name": "End", "position": {"x": 700, "y": 200}, "properties": {}, "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
        ],
        "edges": [
            {"id": _make_id(), "source": start_id, "sourceHandle": "exec_out", "target": print_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": print_id, "sourceHandle": "exec_out", "target": end_id, "targetHandle": "exec_in"},
        ],
    }


def _ip_lookup_graph() -> dict:
    start_id = _make_id()
    http_id = _make_id()
    parse_id = _make_id()
    print_id = _make_id()
    end_id = _make_id()
    return {
        "metadata": {"name": "IP Lookup", "description": "Look up IP geolocation info", "version": 1},
        "nodes": [
            {"id": start_id, "type": "start", "name": "Start", "position": {"x": 100, "y": 200}, "properties": {}, "input_ports": [], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": http_id, "type": "http_request", "name": "Lookup IP", "position": {"x": 400, "y": 200},
             "properties": {"url": "http://ip-api.com/json/8.8.8.8", "method": "GET", "headers": "{}", "body": ""},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "url", "type": "STRING"}, {"name": "body", "type": "ANY"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}, {"name": "response", "type": "DICT"}, {"name": "status_code", "type": "INTEGER"}, {"name": "body", "type": "ANY"}]},
            {"id": parse_id, "type": "json_parse", "name": "Parse Response", "position": {"x": 700, "y": 200},
             "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "input", "type": "STRING"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}, {"name": "output", "type": "ANY"}]},
            {"id": print_id, "type": "print", "name": "Print Result", "position": {"x": 1000, "y": 200},
             "properties": {"message": ""},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": end_id, "type": "end", "name": "End", "position": {"x": 1300, "y": 200}, "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
        ],
        "edges": [
            {"id": _make_id(), "source": start_id, "sourceHandle": "exec_out", "target": http_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": http_id, "sourceHandle": "exec_out", "target": parse_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": http_id, "sourceHandle": "body", "target": parse_id, "targetHandle": "input"},
            {"id": _make_id(), "source": parse_id, "sourceHandle": "exec_out", "target": print_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": parse_id, "sourceHandle": "output", "target": print_id, "targetHandle": "value"},
            {"id": _make_id(), "source": print_id, "sourceHandle": "exec_out", "target": end_id, "targetHandle": "exec_in"},
        ],
    }


def _incident_triage_graph() -> dict:
    start_id = _make_id()
    get_data_id = _make_id()
    if_id = _make_id()
    set_var_id = _make_id()
    print_low_id = _make_id()
    end_high_id = _make_id()
    end_low_id = _make_id()
    return {
        "metadata": {"name": "Incident Triage", "description": "Basic incident triage with severity check", "version": 1},
        "nodes": [
            {"id": start_id, "type": "start", "name": "Start", "position": {"x": 100, "y": 300}, "properties": {},
             "input_ports": [], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": get_data_id, "type": "get_incident_data", "name": "Get Incident", "position": {"x": 400, "y": 300},
             "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}, {"name": "data", "type": "DICT"}]},
            {"id": if_id, "type": "if", "name": "Is Critical?", "position": {"x": 700, "y": 300},
             "properties": {"operator": "equals", "compare_value": "critical"},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}, {"name": "condition", "type": "ANY"}],
             "output_ports": [{"name": "true", "type": "FLOW"}, {"name": "false", "type": "FLOW"}, {"name": "result", "type": "BOOLEAN"}]},
            {"id": set_var_id, "type": "set_incident_var", "name": "Set Escalation", "position": {"x": 1000, "y": 150},
             "properties": {"variable_name": "escalation_level"},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY", "inline_value": "3"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": print_low_id, "type": "print", "name": "Log Low", "position": {"x": 1000, "y": 450},
             "properties": {"message": "Non-critical incident - standard triage."},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": end_high_id, "type": "end", "name": "End (High)", "position": {"x": 1300, "y": 150}, "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
            {"id": end_low_id, "type": "end", "name": "End (Low)", "position": {"x": 1300, "y": 450}, "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
        ],
        "edges": [
            {"id": _make_id(), "source": start_id, "sourceHandle": "exec_out", "target": get_data_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": get_data_id, "sourceHandle": "exec_out", "target": if_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": if_id, "sourceHandle": "true", "target": set_var_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": if_id, "sourceHandle": "false", "target": print_low_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": set_var_id, "sourceHandle": "exec_out", "target": end_high_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": print_low_id, "sourceHandle": "exec_out", "target": end_low_id, "targetHandle": "exec_in"},
        ],
    }


_AUTOMATIONS: list[dict] = [
    {
        "name": "Hello World",
        "description": "A simple example automation that prints a greeting. Great for testing that execution works.",
        "graph_data": _hello_world_graph(),
        "tags": ["example", "getting-started"],
    },
    {
        "name": "IP Lookup",
        "description": "Demonstrates HTTP requests and JSON parsing by looking up geolocation data for an IP address.",
        "graph_data": _ip_lookup_graph(),
        "tags": ["example", "network"],
    },
    {
        "name": "Incident Triage",
        "description": "Example incident triage workflow with conditional logic. Checks severity and sets escalation level.",
        "graph_data": _incident_triage_graph(),
        "tags": ["example", "incident"],
    },
]


# ---------------------------------------------------------------------------
# Seeder functions
# ---------------------------------------------------------------------------

async def _seed_wiki_pages(db: AsyncSession, created_by: UUID) -> None:
    """Seed wiki pages for app docs and node documentation."""
    wiki_svc = WikiService(db)

    # Track slug -> page_id for parent resolution
    slug_to_id: dict[str, UUID] = {}

    # 1. Seed top-level app pages
    for page_def in _APP_WIKI_PAGES:
        existing = await db.execute(
            select(WikiPage.id).where(WikiPage.slug == page_def["slug"])
        )
        if existing.scalar_one_or_none():
            # Already exists - get its ID for child reference
            result = await db.execute(
                select(WikiPage.id).where(WikiPage.slug == page_def["slug"])
            )
            slug_to_id[page_def["slug"]] = result.scalar_one()
            continue

        page = await wiki_svc.create(
            title=page_def["title"],
            slug=page_def["slug"],
            content=page_def.get("content", ""),
            created_by=created_by,
            tags=page_def.get("tags", []),
            icon=page_def.get("icon"),
        )
        slug_to_id[page_def["slug"]] = page.id
        logger.info("  Wiki: %s", page_def["title"])

    # 2. Seed node category pages
    for cat_def in _NODE_CATEGORY_PAGES:
        existing = await db.execute(
            select(WikiPage.id).where(WikiPage.slug == cat_def["slug"])
        )
        if existing.scalar_one_or_none():
            result = await db.execute(
                select(WikiPage.id).where(WikiPage.slug == cat_def["slug"])
            )
            slug_to_id[cat_def["slug"]] = result.scalar_one()
            continue

        parent_id = slug_to_id.get(cat_def.get("parent_slug", ""))
        page = await wiki_svc.create(
            title=cat_def["title"],
            slug=cat_def["slug"],
            content=cat_def.get("content", ""),
            created_by=created_by,
            parent_id=parent_id,
            tags=cat_def.get("tags", []),
            icon=cat_def.get("icon"),
        )
        slug_to_id[cat_def["slug"]] = page.id
        logger.info("  Wiki: %s", cat_def["title"])

    # 3. Seed individual node pages
    for node_def in _NODE_PAGES:
        existing = await db.execute(
            select(WikiPage.id).where(WikiPage.slug == node_def["slug"])
        )
        if existing.scalar_one_or_none():
            continue

        parent_id = slug_to_id.get(node_def.get("parent_slug", ""))
        page = await wiki_svc.create(
            title=node_def["title"],
            slug=node_def["slug"],
            content=node_def.get("content", ""),
            created_by=created_by,
            parent_id=parent_id,
            tags=node_def.get("tags", []),
            linked_node_type=node_def.get("linked_node_type"),
        )
        slug_to_id[node_def["slug"]] = page.id
        logger.info("  Wiki: %s (linked_node_type=%s)", node_def["title"], node_def.get("linked_node_type"))

    await db.flush()


async def _seed_incident_variables(db: AsyncSession, created_by: UUID) -> None:
    """Seed default incident variable definitions."""
    svc = IncidentVariableService(db)
    for var_def in _INCIDENT_VARIABLES:
        existing = await svc.get_by_name(var_def["name"])
        if existing:
            continue
        await svc.create(
            name=var_def["name"],
            created_by=created_by,
            description=var_def.get("description"),
            default_enabled=var_def.get("default_enabled", True),
            sensitive=var_def.get("sensitive", False),
        )
        logger.info("  IncidentVar: %s", var_def["name"])
    await db.flush()


async def _seed_user_secrets(db: AsyncSession, created_by: UUID) -> None:
    """Seed example user secrets for the admin user."""
    svc = UserSecretService(db)
    for secret_def in _USER_SECRETS:
        existing = await svc.get_by_name_for_user(created_by, secret_def["name"])
        if existing:
            continue
        await svc.create(
            user_id=created_by,
            name=secret_def["name"],
            value=secret_def.get("value", ""),
            description=secret_def.get("description"),
            sensitive=secret_def.get("sensitive", False),
        )
        logger.info("  Secret: %s", secret_def["name"])
    await db.flush()


async def _seed_automations(db: AsyncSession, created_by: UUID) -> None:
    """Seed example automations."""
    svc = AutomationService(db)
    for auto_def in _AUTOMATIONS:
        existing = await db.execute(
            select(Automation.id).where(Automation.name == auto_def["name"])
        )
        if existing.scalar_one_or_none():
            continue
        await svc.create(
            name=auto_def["name"],
            created_by=created_by,
            description=auto_def.get("description"),
            graph_data=auto_def.get("graph_data"),
            tags=auto_def.get("tags", []),
        )
        logger.info("  Automation: %s", auto_def["name"])
    await db.flush()
