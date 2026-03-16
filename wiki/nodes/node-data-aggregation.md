---
title: "Data Aggregation Node"
slug: "node-data-aggregation"
tags: ["node"]
parent_slug: "nodes-data-processing"
linked_node_type: "data_aggregation"
---

# Data Aggregation Node

Combines data from multiple input sources into a single output.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **input_1** through **input_4** (Any) - Data sources

## Output Ports
- **exec_out** (Flow) - Continues
- **output** (Dict) - Aggregated data

## Properties
None

## Example Usage
Use to merge results from multiple parallel HTTP requests or data lookups.
