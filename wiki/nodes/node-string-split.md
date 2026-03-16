---
title: "String Split Node"
slug: "node-string-split"
tags: ["node"]
parent_slug: "nodes-string"
linked_node_type: "string_split"
---

# String Split Node

Splits a string into a list using a delimiter.

## Input Ports
- **exec_in** (Flow)
- **input** (String) - String to split
- **delimiter** (String) - Split character/pattern

## Output Ports
- **exec_out** (Flow)
- **result** (List) - List of substrings

## Properties
None

## Example Usage
Split '10.0.0.1,10.0.0.2' by ',' to get ['10.0.0.1', '10.0.0.2']
