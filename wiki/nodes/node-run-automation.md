---
title: "Run Automation Node"
slug: "node-run-automation"
tags: ["node"]
parent_slug: "nodes-subgraph"
linked_node_type: "run_automation"
---

# Run Automation Node

Executes another automation as a sub-automation. Can run synchronously (wait for result) or asynchronously (fire and forget).

## Input Ports
- **exec_in** (Flow) - Incoming execution
- Dynamic input ports matching the target automation's parameters

## Output Ports
- **exec_out** (Flow) - Continues after execution
- **result** (Any) - Result from the sub-automation (sync only)

## Properties
- **automation_id** - Select the automation to run
- **synchronous** - Wait for completion (true) or fire-and-forget (false)

## Example Usage
Use to chain automations: a triage automation can call a remediation automation based on its findings.
