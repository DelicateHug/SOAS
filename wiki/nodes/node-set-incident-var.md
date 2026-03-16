---
title: "Set Incident Variable"
slug: "node-set-incident-var"
tags: ["node"]
parent_slug: "nodes-incident"
linked_node_type: "set_incident_var"
---

# Set Incident Variable

Writes an incident-scoped variable to Redis. The variable definition must exist in Admin > Incident Variables.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **value** (Any) - Value to store

## Output Ports
- **exec_out** (Flow) - Continues after write

## Properties
- **variable_name** - Select the incident variable to write

## Example Usage
Use to store triage verdicts, escalation levels, or analyst notes on an incident.
