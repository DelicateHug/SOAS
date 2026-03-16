---
title: "Set Case Variable"
slug: "node-set-case-variable"
tags: ["node"]
parent_slug: "nodes-variables"
linked_node_type: "set_case_variable"
---

# Set Case Variable

Sets a per-execution (case) variable value.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **value** (Any) - Value to store

## Output Ports
- **exec_out** (Flow) - Continues after write

## Properties
- **variable_name** - Name of the case variable to set

## Example Usage
Use for execution-scoped state that should not leak between runs.
