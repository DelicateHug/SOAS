---
title: "String Format Node"
slug: "node-string-format"
tags: ["node"]
parent_slug: "nodes-string"
linked_node_type: "string_format"
---

# String Format Node

Formats a string using template placeholders.

## Input Ports
- **exec_in** (Flow)
- **template** (String) - Format template
- **values** (Dict) - Values to insert

## Output Ports
- **exec_out** (Flow)
- **result** (String) - Formatted string

## Properties
None

## Example Usage
Template: 'Alert: {title} (Severity: {severity})'
