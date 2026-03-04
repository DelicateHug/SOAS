"""
Emitters for utility nodes: math operations, string operations, list operations,
JSON parsing/stringifying, data aggregation, and breakpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext


# ---------------------------------------------------------------------------
# Math operations
# ---------------------------------------------------------------------------


def _math_emitter(node_type_name: str, op: str):
    """Factory for simple binary math emitters."""

    class _Emitter(NodeEmitter):
        @property
        def node_type(self) -> str:
            return node_type_name

        def emit(self, node, context, generator):
            a = self.get_input_value(node, "a", context, generator.graph, default="0")
            b = self.get_input_value(node, "b", context, generator.graph, default="0")
            out = context.generate_variable_name("result")
            context.set_output_variable(node.id, "result", out)
            context.add_line(f"{out} = {a} {op} {b}")
            context.mark_node_processed(node.id)

    return _Emitter


AddNodeEmitter = _math_emitter("add", "+")
SubtractNodeEmitter = _math_emitter("subtract", "-")
MultiplyNodeEmitter = _math_emitter("multiply", "*")
DivideNodeEmitter = _math_emitter("divide", "/")
ModuloNodeEmitter = _math_emitter("modulo", "%")
PowerNodeEmitter = _math_emitter("power", "**")


# ---------------------------------------------------------------------------
# String operations
# ---------------------------------------------------------------------------


class StringConcatNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "string_concat"

    def emit(self, node, context, generator):
        a = self.get_input_value(node, "a", context, generator.graph, default="''")
        b = self.get_input_value(node, "b", context, generator.graph, default="''")
        out = context.generate_variable_name("concat_result")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = str({a}) + str({b})")
        context.mark_node_processed(node.id)


class StringSplitNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "string_split"

    def emit(self, node, context, generator):
        text = self.get_input_value(node, "text", context, generator.graph, default="''")
        delimiter = self.get_input_value(node, "delimiter", context, generator.graph, default="' '")
        out = context.generate_variable_name("split_result")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = str({text}).split({delimiter})")
        context.mark_node_processed(node.id)


class StringReplaceNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "string_replace"

    def emit(self, node, context, generator):
        text = self.get_input_value(node, "text", context, generator.graph, default="''")
        old = self.get_input_value(node, "old", context, generator.graph, default="''")
        new = self.get_input_value(node, "new", context, generator.graph, default="''")
        out = context.generate_variable_name("replace_result")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = str({text}).replace({old}, {new})")
        context.mark_node_processed(node.id)


class StringFormatNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "string_format"

    def emit(self, node, context, generator):
        template = self.get_input_value(node, "template", context, generator.graph, default="''")
        values = self.get_input_value(node, "values", context, generator.graph, default="{}")
        out = context.generate_variable_name("format_result")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = str({template}).format(**{values})")
        context.mark_node_processed(node.id)


# ---------------------------------------------------------------------------
# List operations
# ---------------------------------------------------------------------------


class ListAppendNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "list_append"

    def emit(self, node, context, generator):
        lst = self.get_input_value(node, "list", context, generator.graph, default="[]")
        item = self.get_input_value(node, "item", context, generator.graph, default="None")
        out = context.generate_variable_name("appended_list")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = list({lst})")
        context.add_line(f"{out}.append({item})")
        context.mark_node_processed(node.id)


class ListFilterNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "list_filter"

    def emit(self, node, context, generator):
        lst = self.get_input_value(node, "list", context, generator.graph, default="[]")
        condition = self.get_input_value(node, "condition", context, generator.graph, default="'True'")
        out = context.generate_variable_name("filtered_list")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = [x for x in {lst} if eval({condition})]")
        context.mark_node_processed(node.id)


class ListMapNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "list_map"

    def emit(self, node, context, generator):
        lst = self.get_input_value(node, "list", context, generator.graph, default="[]")
        expression = self.get_input_value(node, "expression", context, generator.graph, default="'x'")
        out = context.generate_variable_name("mapped_list")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"{out} = [eval({expression}) for x in {lst}]")
        context.mark_node_processed(node.id)


class ListReduceNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "list_reduce"

    def emit(self, node, context, generator):
        lst = self.get_input_value(node, "list", context, generator.graph, default="[]")
        initial = self.get_input_value(node, "initial", context, generator.graph, default="0")
        expression = self.get_input_value(node, "expression", context, generator.graph, default="'acc + x'")
        out = context.generate_variable_name("reduced_result")
        context.set_output_variable(node.id, "result", out)
        context.add_line("from functools import reduce")
        context.add_line(f"{out} = reduce(lambda acc, x: eval({expression}), {lst}, {initial})")
        context.mark_node_processed(node.id)


# ---------------------------------------------------------------------------
# JSON operations
# ---------------------------------------------------------------------------


class JsonParseNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "json_parse"

    def emit(self, node, context, generator):
        text = self.get_input_value(node, "text", context, generator.graph, default="'{}'")
        out = context.generate_variable_name("parsed_json")
        context.set_output_variable(node.id, "result", out)
        context.add_line("import json")
        context.add_line(f"{out} = json.loads({text})")
        context.mark_node_processed(node.id)


class JsonStringifyNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "json_stringify"

    def emit(self, node, context, generator):
        data = self.get_input_value(node, "data", context, generator.graph, default="{}")
        out = context.generate_variable_name("json_string")
        context.set_output_variable(node.id, "result", out)
        context.add_line("import json")
        context.add_line(f"{out} = json.dumps({data}, indent=2)")
        context.mark_node_processed(node.id)


# ---------------------------------------------------------------------------
# Data aggregation
# ---------------------------------------------------------------------------


class DataAggregationNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "data_aggregation"

    def emit(self, node, context, generator):
        data = self.get_input_value(node, "data", context, generator.graph, default="[]")
        operation = self.get_input_value(node, "operation", context, generator.graph, default="'count'")
        out = context.generate_variable_name("agg_result")
        context.set_output_variable(node.id, "result", out)
        context.add_line(f"_data = {data}")
        context.add_line(f"_op = {operation}")
        context.add_line(f"if _op == 'count': {out} = len(_data)")
        context.add_line(f"elif _op == 'sum': {out} = sum(_data)")
        context.add_line(f"elif _op == 'avg': {out} = sum(_data) / max(len(_data), 1)")
        context.add_line(f"elif _op == 'min': {out} = min(_data) if _data else None")
        context.add_line(f"elif _op == 'max': {out} = max(_data) if _data else None")
        context.add_line(f"else: {out} = _data")
        context.mark_node_processed(node.id)


# ---------------------------------------------------------------------------
# Breakpoint (debug)
# ---------------------------------------------------------------------------


class BreakpointNodeEmitter(NodeEmitter):
    @property
    def node_type(self) -> str:
        return "breakpoint"

    def emit(self, node, context, generator):
        context.add_line("# Breakpoint - skipped in production")
        context.mark_node_processed(node.id)
