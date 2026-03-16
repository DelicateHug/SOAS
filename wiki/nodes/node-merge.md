---
title: "Merge Node"
slug: "node-merge"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "merge"
---

# Merge Node

Converges multiple execution paths back into one. Supports `first_in` (continues on first arrival) or `wait_all` (waits for all paths).

## Input Ports
- **exec_in_1** through **exec_in_N** (Flow) - Multiple incoming paths (2-8)

## Output Ports
- **exec_out** (Flow) - Continues after merge

## Properties
- **strategy** - `first_in` or `wait_all`
- **num_inputs** - Number of input paths (2-8)

## Example Usage
After an If node splits into true/false branches, use a Merge node to rejoin them before continuing to the End node.
