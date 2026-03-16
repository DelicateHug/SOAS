---
title: "Database Query Node"
slug: "node-database-query"
tags: ["node"]
parent_slug: "nodes-database"
linked_node_type: "database_query"
---

# Database Query Node

Executes SQL queries against a database. Use with caution - ensure queries are safe.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **query** (String) - SQL query
- **params** (Dict) - Query parameters

## Output Ports
- **exec_out** (Flow) - Continues after query
- **rows** (List) - Query result rows
- **row_count** (Integer) - Number of rows affected/returned

## Properties
None

## Example Usage
Use for custom database lookups that aren't covered by built-in nodes. Always use parameterized queries.
