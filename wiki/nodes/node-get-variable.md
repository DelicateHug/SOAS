---
title: "Get Variable"
slug: "node-get-variable"
tags: ["node"]
parent_slug: "nodes-variables"
linked_node_type: "get_variable"
---

# Get Variable

Reads a global variable value. Global variables persist across nodes within a single execution.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues after read
- **value** (Any) - The variable's current value

## Properties
- **variable_name** - Name of the global variable to read

## Example Usage
Use to retrieve a counter or accumulated result set earlier in the workflow.
