---
title: "Get SOAS Variable"
slug: "node-get-soas-var"
tags: ["node"]
parent_slug: "nodes-variables"
linked_node_type: "get_soas_var"
---

# Get SOAS Variable

Reads a SOAS application-level variable. These are persistent, permission-controlled variables stored in the database.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues after read
- **value** (Any) - The variable's current value

## Properties
- **variable_name** - Select the SOAS variable to read

## Example Usage
Use to read application-wide configuration like API base URLs or feature flags.
