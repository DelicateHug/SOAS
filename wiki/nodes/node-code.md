---
title: "Code Node"
slug: "node-code"
tags: ["node"]
parent_slug: "nodes-custom-code"
linked_node_type: "code"
---

# Code Node

Executes custom Python code. The code has access to all input port values as local variables and can set output values.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **input_1** through **input_3** (Any) - Input data

## Output Ports
- **exec_out** (Flow) - Continues after code executes
- **output** (Any) - Return value from the code

## Properties
- **code** - Python code to execute
- **language** - Programming language (default: python)
- **description** - What this code does

## Example Usage
```python
# Access inputs via their port names
result = input_1.upper() + ' - ' + str(input_2)
output = result
```
