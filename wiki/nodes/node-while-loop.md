---
title: "While Loop Node"
slug: "node-while-loop"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "while_loop"
---

# While Loop Node

Repeats execution while a condition remains true. Has a configurable maximum iteration limit to prevent infinite loops.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **condition** (Any) - Condition variable

## Output Ports
- **loop_body** (Flow) - Executes each iteration
- **completed** (Flow) - Executes when condition becomes false
- **iteration** (Integer) - Current iteration count

## Properties
- **condition_code** - Python expression checked before each iteration
- **max_iterations** - Safety limit (default: 10000)

## Example Usage
Use to poll an API until a job completes: set condition_code to `status != 'complete'` and add an HTTP Request in the loop body.
