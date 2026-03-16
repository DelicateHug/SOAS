---
title: "If Node"
slug: "node-if"
tags: ["node"]
parent_slug: "nodes-control-flow"
linked_node_type: "if"
---

# If Node

Conditional branching node. Evaluates a condition and routes execution to the **true** or **false** branch.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **value** (Any) - Value to evaluate
- **condition** (Any) - Comparison value (for operators that need it)

## Output Ports
- **true** (Flow) - Executes when condition is true
- **false** (Flow) - Executes when condition is false
- **result** (Boolean) - The evaluation result

## Properties
- **operator** - Comparison operator (is_truthy, equals, contains, greater_than, matches_regex, custom, etc.)
- **compare_value** - Value to compare against
- **condition_code** - Custom Python expression (when operator is 'custom')

## Example Usage
Use the If node to route incidents by severity: connect the incident severity to the `value` port, set operator to `equals`, and compare_value to `critical`.
