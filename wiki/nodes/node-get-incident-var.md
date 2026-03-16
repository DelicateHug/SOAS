---
title: "Get Incident Variable"
slug: "node-get-incident-var"
tags: ["node"]
parent_slug: "nodes-incident"
linked_node_type: "get_incident_var"
---

# Get Incident Variable

Reads an incident-scoped variable from Redis/Postgres. The variable must be defined in Admin > Incident Variables.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues after read
- **value** (Any) - The variable's current value

## Properties
- **variable_name** - Select the incident variable to read

## Example Usage
Use in incident-triggered automations to read previously stored triage data.
