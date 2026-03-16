---
title: "Start Node"
slug: "node-start"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "start"
---

# Start Node

The entry point of every automation. Execution begins here. If the automation defines input parameters, they appear as output ports on this node.

## Input Ports
None - this is the entry point.

## Output Ports
- **exec_out** (Flow) - Execution continues to the next node
- Dynamic output ports for each automation input parameter

## Properties
None

## Example Usage
Every automation must have exactly one Start node. Connect its `exec_out` port to the first action in your workflow.
