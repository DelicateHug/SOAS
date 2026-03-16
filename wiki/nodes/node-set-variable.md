---
title: "Set Variable"
slug: "node-set-variable"
tags: ["node"]
parent_slug: "nodes-variables"
linked_node_type: "set_variable"
---

# Set Variable

Sets a global variable value. The value persists for the rest of the execution.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **value** (Any) - Value to store

## Output Ports
- **exec_out** (Flow) - Continues after write

## Properties
- **variable_name** - Name of the global variable to set

## Example Usage
Use to store intermediate results that other nodes need to access later.
