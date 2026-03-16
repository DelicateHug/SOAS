---
title: "HTTP Request Node"
slug: "node-http-request"
tags: ["node"]
parent_slug: "nodes-network"
linked_node_type: "http_request"
---

# HTTP Request Node

Makes HTTP requests to external APIs. Supports GET, POST, PUT, DELETE, and other methods.

## Input Ports
- **exec_in** (Flow) - Incoming execution
- **url** (String) - Request URL
- **body** (Any) - Request body

## Output Ports
- **exec_out** (Flow) - Continues after response
- **response** (Dict) - Response object with status, headers, body
- **status_code** (Integer) - HTTP status code
- **body** (Any) - Parsed response body

## Properties
- **url** - Target URL
- **method** - HTTP method (GET, POST, PUT, DELETE)
- **headers** - JSON object of headers
- **body** - Request body content

## Example Usage
```
URL: https://api.example.com/lookup
Method: POST
Headers: {"Authorization": "Bearer {{api_key}}"}
Body: {"query": "8.8.8.8"}
```
