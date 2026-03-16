---
title: "Subgraph Input Node"
slug: "node-subgraph-input"
tags: ["node"]
parent_slug: "nodes-subgraph"
linked_node_type: "subgraph_input"
---

# Subgraph Input Node

Defines an input parameter for the automation. Appears as an output port on the Start node at execution time.

## Input Ports
None

## Output Ports
- **value** (Any) - The parameter value provided at execution

## Properties
- **port_name** - Select the automation input parameter
- **port_type_setting** - Data type of this input
- **description** - What this input is for
- **default_value** - Default when not provided

## Example Usage
Add a Subgraph Input named 'target_ip' to make your automation accept an IP address parameter.
