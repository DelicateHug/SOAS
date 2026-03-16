---
title: "Print Node"
slug: "node-print"
tags: ["node"]
parent_slug: "nodes-io"
linked_node_type: "print"
---

# Print Node

Outputs a message to the execution log (stdout). Useful for debugging and status updates.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **value** (Any) - Value to print

## Output Ports
- **exec_out** (Flow) - Continues after print

## Properties
- **message** - Static message text (used if no value connected)

## Example Usage
Connect any data port to see its value in the execution output. Great for debugging.
