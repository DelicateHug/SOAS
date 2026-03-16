---
title: "JSON Parse Node"
slug: "node-json-parse"
tags: ["node"]
parent_slug: "nodes-data-processing"
linked_node_type: "json_parse"
---

# JSON Parse Node

Parses a JSON string into a Python object (dict, list, etc.).

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **input** (String) - JSON string to parse

## Output Ports
- **exec_out** (Flow) - Continues
- **output** (Any) - Parsed Python object

## Properties
None

## Example Usage
Use after an HTTP Request to parse the response body from a JSON string.
