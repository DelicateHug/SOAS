---
title: "Administration"
slug: "administration"
icon: "settings"
tags: ["guide", "admin"]
---

# Administration

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
