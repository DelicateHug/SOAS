---
title: "Regex Replace Node"
slug: "node-regex-replace"
tags: ["node"]
parent_slug: "nodes-string"
linked_node_type: "regex_replace"
---

# Regex Replace Node

Finds and replaces text using regular expressions.

## Input Ports
- **exec_in** (Flow)
- **input** (String) - Source string
- **pattern** (String) - Regex pattern
- **replacement** (String) - Replacement text

## Output Ports
- **exec_out** (Flow)
- **result** (String) - Modified string

## Properties
None

## Example Usage
Redact email addresses: pattern `[\w.]+@[\w.]+` replacement `[REDACTED]`
