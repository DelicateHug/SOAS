---
title: "Automations"
slug: "automations"
icon: "zap"
tags: ["guide", "automations"]
---

# Automations

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
