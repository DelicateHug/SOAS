---
title: "Set SOAS Variable"
slug: "node-set-soas-var"
tags: ["node"]
parent_slug: "nodes-variables"
linked_node_type: "set_soas_var"
---

# Set SOAS Variable

Writes a SOAS application-level variable. Requires appropriate permissions.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **value** (Any) - Value to store

## Output Ports
- **exec_out** (Flow) - Continues after write

## Properties
- **variable_name** - Select the SOAS variable to write

## Example Usage
Use to update application state that persists across executions and is shared between users.
