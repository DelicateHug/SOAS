---
title: "Get Case Variable"
slug: "node-get-case-variable"
tags: ["node"]
parent_slug: "nodes-variables"
linked_node_type: "get_case_variable"
---

# Get Case Variable

Reads a per-execution (case) variable. Case variables are isolated to the current execution instance.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues after read
- **value** (Any) - The variable's current value

## Properties
- **variable_name** - Name of the case variable to read

## Example Usage
Similar to Get Variable but scoped to the current execution context.
