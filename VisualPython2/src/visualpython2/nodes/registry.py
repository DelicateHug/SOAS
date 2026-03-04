"""Node registry for VisualPython2.

Web-friendly registry - no singleton pattern, instantiable directly.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from visualpython2.nodes.definitions import BaseNode, Position


class NodeTypeInfo:
    """Information about a registered node type."""

    def __init__(
        self,
        node_type: str,
        node_class: Type[BaseNode],
        name: str,
        category: str,
        color: str,
        description: str = "",
        icon: Optional[str] = None,
    ) -> None:
        self.node_type = node_type
        self.node_class = node_class
        self.name = name
        self.category = category
        self.color = color
        self.description = description
        self.icon = icon

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_type": self.node_type,
            "name": self.name,
            "category": self.category,
            "color": self.color,
            "description": self.description,
            "icon": self.icon,
        }


class NodeRegistry:
    """Registry for managing available node types.

    Unlike VP1, this is NOT a singleton - create instances as needed.
    """

    def __init__(self) -> None:
        self._node_types: Dict[str, NodeTypeInfo] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(
        self,
        node_class: Type[BaseNode],
        description: str = "",
        icon: Optional[str] = None,
    ) -> None:
        node_type = node_class.node_type
        name = getattr(node_class, "display_name", None) or node_class.node_type.replace("_", " ").title()
        category = node_class.node_category
        color = node_class.node_color

        info = NodeTypeInfo(
            node_type=node_type,
            node_class=node_class,
            name=name,
            category=category,
            color=color,
            description=description,
            icon=icon,
        )

        self._node_types[node_type] = info

        if category not in self._categories:
            self._categories[category] = []
        if node_type not in self._categories[category]:
            self._categories[category].append(node_type)

    def unregister(self, node_type: str) -> bool:
        if node_type not in self._node_types:
            return False
        info = self._node_types[node_type]
        del self._node_types[node_type]
        if info.category in self._categories:
            if node_type in self._categories[info.category]:
                self._categories[info.category].remove(node_type)
            if not self._categories[info.category]:
                del self._categories[info.category]
        return True

    def get_node_type(self, node_type: str) -> Optional[NodeTypeInfo]:
        return self._node_types.get(node_type)

    def get_all_node_types(self) -> List[NodeTypeInfo]:
        return list(self._node_types.values())

    def get_categories(self) -> List[str]:
        return sorted(self._categories.keys())

    def get_node_types_in_category(self, category: str) -> List[NodeTypeInfo]:
        node_types = self._categories.get(category, [])
        return [self._node_types[nt] for nt in node_types if nt in self._node_types]

    def get_node_types_by_category(self) -> Dict[str, List[NodeTypeInfo]]:
        result: Dict[str, List[NodeTypeInfo]] = {}
        for category in sorted(self._categories.keys()):
            result[category] = self.get_node_types_in_category(category)
        return result

    def create_node(
        self,
        node_type: str,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        **kwargs: Any,
    ) -> Optional[BaseNode]:
        info = self._node_types.get(node_type)
        if info is None:
            return None
        return info.node_class(node_id=node_id, name=name, position=position, **kwargs)

    def is_registered(self, node_type: str) -> bool:
        return node_type in self._node_types

    def create_node_from_dict(self, data: Dict[str, Any]) -> Optional[BaseNode]:
        node_type = data.get("type")
        if not node_type:
            return None
        info = self._node_types.get(node_type)
        if info is None:
            return None
        try:
            if hasattr(info.node_class, "from_dict"):
                return info.node_class.from_dict(data)
            else:
                from visualpython2.nodes.definitions import Position
                position = Position.from_dict(data.get("position", {}))
                return info.node_class(
                    node_id=data.get("id"),
                    name=data.get("name"),
                    position=position,
                )
        except Exception:
            return None

    def register_default_nodes(self) -> None:
        """Register all built-in node types."""
        from visualpython2.nodes.definitions import (
            StartNode, EndNode, CodeNode, IfNode, ForLoopNode, WhileLoopNode,
            PrintNode, GetVariableNode, SetVariableNode, GetCaseVariableNode,
            SetCaseVariableNode, FileReadNode, FileWriteNode, HTTPRequestNode,
            InputNode, MergeNode, DataAggregationNode, JSONParseNode,
            JSONStringifyNode, ThreadNode, ThreadJoinNode, TryCatchNode,
            BreakpointNode, DatabaseQueryNode,
            ListAppendNode, ListFilterNode, ListMapNode, ListReduceNode,
            AddNode, SubtractNode, MultiplyNode, DivideNode, ModuloNode, PowerNode,
            RegexMatchNode, RegexReplaceNode,
            StringConcatNode, StringSplitNode, StringReplaceNode, StringFormatNode,
            SubgraphNode, SubgraphInputNode, SubgraphOutputNode, RunAutomationNode,
            GetIncidentVarNode, SetIncidentVarNode, GetIncidentDataNode,
            GetSOASVarNode, SetSOASVarNode,
            GetUserSecretNode,
        )

        self.register(StartNode, "Entry point of script execution.", "play")
        self.register(EndNode, "End of an execution path.", "stop")
        self.register(CodeNode, "Execute custom Python code.", "code")
        self.register(IfNode, "Conditional branching.", "branch")
        self.register(ForLoopNode, "Iterate over a collection.", "loop")
        self.register(WhileLoopNode, "Iterate while condition is true.", "loop")
        self.register(PrintNode, "Print messages to output.", "print")
        self.register(GetVariableNode, "Get a global variable value.", "variable")
        self.register(SetVariableNode, "Set a global variable value.", "variable")
        self.register(GetCaseVariableNode, "Get a per-execution variable.", "variable")
        self.register(SetCaseVariableNode, "Set a per-execution variable.", "variable")
        self.register(FileReadNode, "Read content from a file.", "file-read")
        self.register(FileWriteNode, "Write content to a file.", "file-write")
        self.register(HTTPRequestNode, "Make HTTP requests.", "network")
        self.register(InputNode, "Prompt for user input.", "input")
        self.register(MergeNode, "Converge execution paths.", "merge")
        self.register(DataAggregationNode, "Combine data from multiple sources.", "aggregate")
        self.register(JSONParseNode, "Parse JSON strings.", "json")
        self.register(JSONStringifyNode, "Convert to JSON strings.", "json")
        self.register(ThreadNode, "Spawn parallel threads.", "thread")
        self.register(ThreadJoinNode, "Wait for thread completion.", "thread-join")
        self.register(TryCatchNode, "Exception handling.", "shield")
        self.register(BreakpointNode, "Pause for debugging.", "bug")
        self.register(DatabaseQueryNode, "Execute SQL queries.", "database")
        self.register(ListAppendNode, "Append elements to a list.", "list-add")
        self.register(ListFilterNode, "Filter list elements.", "filter")
        self.register(ListMapNode, "Transform list elements.", "transform")
        self.register(ListReduceNode, "Reduce a list to a single value.", "compress")
        self.register(AddNode, "Add two numbers.", "plus")
        self.register(SubtractNode, "Subtract numbers.", "minus")
        self.register(MultiplyNode, "Multiply numbers.", "multiply")
        self.register(DivideNode, "Divide numbers.", "divide")
        self.register(ModuloNode, "Modulo operation.", "percent")
        self.register(PowerNode, "Exponentiation.", "superscript")
        self.register(RegexMatchNode, "Find regex matches.", "search")
        self.register(RegexReplaceNode, "Regex find and replace.", "replace")
        self.register(StringConcatNode, "Concatenate strings.", "text")
        self.register(StringSplitNode, "Split strings.", "split")
        self.register(StringReplaceNode, "Find and replace in strings.", "replace-text")
        self.register(StringFormatNode, "Format strings with templates.", "template")
        self.register(SubgraphNode, "Reusable subgraph.", "box")
        self.register(SubgraphInputNode, "Subgraph input parameter.", "arrow-right")
        self.register(SubgraphOutputNode, "Subgraph output parameter.", "arrow-left")
        self.register(RunAutomationNode, "Run another automation as a sub-automation.", "play-circle")
        # Incident variable nodes
        self.register(GetIncidentVarNode, "Get an incident variable from Redis/Postgres.", "shield")
        self.register(SetIncidentVarNode, "Set an incident variable in Redis.", "shield")
        self.register(GetIncidentDataNode, "Get all incident data.", "shield")
        # SOAS application-level variable nodes
        self.register(GetSOASVarNode, "Get a SOAS application variable (permission-restricted).", "variable")
        self.register(SetSOASVarNode, "Set a SOAS application variable (permission-restricted).", "variable")
        # User secret nodes
        self.register(GetUserSecretNode, "Get a per-user secret (read-only, resolved at runtime).", "key")
