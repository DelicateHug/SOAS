---
title: "File Read Node"
slug: "node-file-read"
tags: ["node"]
parent_slug: "nodes-file-io"
linked_node_type: "file_read"
---

# File Read Node

Reads the contents of a file from the worker filesystem.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **path** (String) - File path to read

## Output Ports
- **exec_out** (Flow) - Continues after read
- **content** (String) - File contents

## Properties
None

## Example Usage
Use to read configuration files, log files, or data exports.
