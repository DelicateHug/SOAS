---
title: "Thread Join Node"
slug: "node-thread-join"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "thread_join"
---

# Thread Join Node

Synchronizes parallel threads. Waits for all incoming threads to complete before continuing.

## Input Ports
- **thread_1** through **thread_N** (Flow) - Incoming parallel paths (2-8)

## Output Ports
- **exec_out** (Flow) - Continues after all threads complete

## Properties
- **num_inputs** - Number of threads to wait for (2-8)

## Example Usage
Place after a Thread node to wait for all parallel tasks to finish before proceeding.
