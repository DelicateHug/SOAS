---
title: "Graph Editor"
slug: "graph-editor"
icon: "git-branch"
tags: ["guide", "editor"]
---

# Graph Editor

The Graph Editor is the visual interface for building automation workflows.

## Interface

- **Node Palette** - Left sidebar with all available node types organized by category
- **Canvas** - Central area for placing and connecting nodes
- **Property Panel** - Right sidebar for configuring selected node properties
- **Toolbar** - Top bar with save, compile preview, and validation actions

## Working with Nodes

1. **Add Nodes** - Click a node type in the palette or right-click the canvas
2. **Connect Nodes** - Drag from an output port to an input port
3. **Configure** - Select a node and edit its properties in the Property Panel
4. **Move** - Drag nodes to reposition them on the canvas

## Port Types

| Type | Color | Description |
|------|-------|-------------|
| **Flow** | Gray | Execution flow (order of operations) |
| **String** | Green | Text data |
| **Integer** | Blue | Whole numbers |
| **Float** | Teal | Decimal numbers |
| **Boolean** | Orange | True/False values |
| **List** | Purple | Ordered collections |
| **Dict** | Yellow | Key-value mappings |
| **Any** | White | Accepts any data type |

## Tips

- Use **Comment** nodes to document your workflow
- Use **Compile Preview** to see the generated Python code
- Use **Validate** to check for errors before saving
- Nodes with a documentation icon link to their wiki page
