---
title: "Get User Secret"
slug: "node-get-user-secret"
tags: ["node"]
parent_slug: "nodes-secrets"
linked_node_type: "get_user_secret"
---

# Get User Secret

Retrieves a decrypted user secret at runtime. The secret must be created in My Secrets. The executing user's secrets are resolved.

## Input Ports
- **exec_in** (Flow) - Incoming execution

## Output Ports
- **exec_out** (Flow) - Continues
- **value** (String) - Decrypted secret value

## Properties
- **secret_name** - Select the user secret to read

## Example Usage
Use to inject API keys into HTTP Request nodes without hardcoding them in the graph.
