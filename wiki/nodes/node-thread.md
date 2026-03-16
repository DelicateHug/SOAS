---
title: "Thread Node"
slug: "node-thread"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "thread"
---

# Thread Node

Spawns parallel execution threads. Each output executes concurrently.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **thread_1** through **thread_N** (Flow) - Parallel execution paths (2-8)

## Properties
- **num_threads** - Number of parallel threads (2-8)

## Example Usage
Use to run multiple HTTP requests in parallel: connect each thread output to a different HTTP Request node, then join with a Thread Join node.
