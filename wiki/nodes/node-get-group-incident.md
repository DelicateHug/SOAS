---
title: "Get Group Incident By Index"
slug: "node-get-group-incident"
tags: ["node"]
parent_slug: "nodes-incident"
linked_node_type: "get_group_incident"
---

# Get Group Incident By Index

Gets a specific incident from the group by its zero-based index.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues
- **incident** (Dict) - Incident data at the given index

## Properties
- **index** - Zero-based index of the incident to retrieve

## Example Usage
Use with a For Loop to iterate through group incidents by index.
