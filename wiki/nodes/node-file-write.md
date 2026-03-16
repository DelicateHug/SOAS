---
title: "File Write Node"
slug: "node-file-write"
tags: ["node"]
parent_slug: "nodes-file-io"
linked_node_type: "file_write"
---

# File Write Node

Writes content to a file on the worker filesystem.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **path** (String) - File path to write
- **content** (String) - Content to write

## Output Ports
- **exec_out** (Flow) - Continues after write

## Properties
None

## Example Usage
Use to save reports, export data, or create temporary files for processing.
