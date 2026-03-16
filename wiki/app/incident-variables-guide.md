---
title: "Incident Variables"
slug: "incident-variables-guide"
icon: "database"
tags: ["guide", "variables"]
---

# Incident Variables

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
