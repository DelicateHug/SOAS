---
title: "Input Node"
slug: "node-input"
tags: ["node"]
parent_slug: "nodes-io"
linked_node_type: "input"
---

# Input Node

Prompts for user input during execution. Pauses the automation until input is provided.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues after input received
- **value** (String) - The user's input

## Properties
- **prompt** - Message to display to the user

## Example Usage
Use for interactive automations that require analyst decisions mid-execution.
