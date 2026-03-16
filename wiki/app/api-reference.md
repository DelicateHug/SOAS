---
title: "API Reference"
slug: "api-reference"
icon: "code"
tags: ["guide", "api"]
---

# API Reference

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
