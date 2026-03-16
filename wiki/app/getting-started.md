---
title: "Getting Started"
slug: "getting-started"
icon: "rocket"
tags: ["guide"]
---

# Getting Started with SOC on a Stick

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
