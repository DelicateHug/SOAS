---
title: "Regex Match Node"
slug: "node-regex-match"
tags: ["node"]
parent_slug: "nodes-string"
linked_node_type: "regex_match"
---

# Regex Match Node

Finds all matches of a regular expression pattern in a string.

## Input Ports
- **exec_in** (Flow)
- **input** (String) - String to search
- **pattern** (String) - Regex pattern

## Output Ports
- **exec_out** (Flow)
- **matches** (List) - List of matches
- **found** (Boolean) - Whether any matches were found

## Properties
None

## Example Usage
Extract IP addresses: pattern `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}`
