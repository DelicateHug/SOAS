---
title: "Try/Catch Node"
slug: "node-try-catch"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "try_catch"
---

# Try/Catch Node

Exception handling. Wraps a block of execution in error handling - if an error occurs, the catch branch executes.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **try** (Flow) - Normal execution path
- **catch** (Flow) - Error handling path
- **finally** (Flow) - Always executes
- **error** (String) - Error message if caught

## Properties
None

## Example Usage
Wrap HTTP requests in a Try/Catch to handle network errors gracefully.
