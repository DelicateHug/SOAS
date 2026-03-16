---
title: "Incidents"
slug: "incidents"
icon: "alert-triangle"
tags: ["guide", "incidents"]
---

# Incidents

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
