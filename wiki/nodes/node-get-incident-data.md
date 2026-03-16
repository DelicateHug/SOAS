---
title: "Get Incident Data"
slug: "node-get-incident-data"
tags: ["node"]
parent_slug: "nodes-incident"
linked_node_type: "get_incident_data"
---

# Get Incident Data

Retrieves all data for the current incident (title, severity, status, metadata, etc.).

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues after read
- **data** (Dict) - Full incident data dictionary

## Properties
None

## Example Usage
Use at the start of incident-triggered automations to access incident details for decision-making.
