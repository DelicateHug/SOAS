---
title: "For Loop Node"
slug: "node-for-loop"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "for_loop"
---

# For Loop Node

Iterates over a collection. For each element, the loop body executes with the current item and index.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **iterable** (Any) - Collection to iterate over

## Output Ports
- **loop_body** (Flow) - Executes for each iteration
- **completed** (Flow) - Executes after all iterations
- **item** (Any) - Current element
- **index** (Integer) - Current index

## Properties
- **iterable_code** - Python expression for the collection (e.g., `range(10)`)

## Example Usage
Use to process a list of IP addresses: connect a list to the `iterable` port, then use the `item` output in an HTTP Request node.
