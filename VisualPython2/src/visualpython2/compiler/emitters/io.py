"""
Emitters for input/output nodes: Print, Input, FileRead, FileWrite, HttpRequest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext


class PrintNodeEmitter(NodeEmitter):
    """Emitter for Print nodes."""

    @property
    def node_type(self) -> str:
        return "print"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        message = self.get_input_value(node, "message", context, generator.graph, default="''")
        prefix = self.get_input_value(node, "prefix", context, generator.graph, default="''")

        out_var = context.generate_variable_name("printed_msg")
        context.set_output_variable(node.id, "printed_message", out_var)

        context.add_line(f"_prefix = {prefix}")
        context.add_line(f"_msg = {message}")
        context.add_line(f'{out_var} = f"{{_prefix}}{{_msg}}" if _prefix else str(_msg)')
        context.add_line(f"print({out_var})")
        context.mark_node_processed(node.id)


class InputNodeEmitter(NodeEmitter):
    """Emitter for Input nodes (user/parameter input)."""

    @property
    def node_type(self) -> str:
        return "input"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        prompt = self.get_input_value(node, "prompt_text", context, generator.graph, default="'Enter value: '")
        default_val = self.get_input_value(node, "default_value", context, generator.graph, default="''")

        val_var = context.generate_variable_name("user_input")
        cancelled_var = context.generate_variable_name("input_cancelled")
        context.set_output_variable(node.id, "value", val_var)
        context.set_output_variable(node.id, "cancelled", cancelled_var)

        context.add_line("from soas_input import soas_input")
        context.add_line(f"{val_var}, {cancelled_var} = soas_input({repr(node.id)}, {prompt}, {default_val})")
        context.mark_node_processed(node.id)


class FileReadNodeEmitter(NodeEmitter):
    """Emitter for FileRead nodes."""

    @property
    def node_type(self) -> str:
        return "file_read"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        file_path = self.get_input_value(node, "file_path", context, generator.graph, default="''")

        out_var = context.generate_variable_name("file_content")
        context.set_output_variable(node.id, "content", out_var)

        context.add_line(f"with open({file_path}, 'r') as _f:")
        context.indentation.indent()
        context.add_line(f"{out_var} = _f.read()")
        context.indentation.dedent()
        context.mark_node_processed(node.id)


class FileWriteNodeEmitter(NodeEmitter):
    """Emitter for FileWrite nodes."""

    @property
    def node_type(self) -> str:
        return "file_write"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        file_path = self.get_input_value(node, "file_path", context, generator.graph, default="''")
        content = self.get_input_value(node, "content", context, generator.graph, default="''")

        context.add_line(f"with open({file_path}, 'w') as _f:")
        context.indentation.indent()
        context.add_line(f"_f.write(str({content}))")
        context.indentation.dedent()
        context.mark_node_processed(node.id)


class HttpRequestNodeEmitter(NodeEmitter):
    """Emitter for HttpRequest nodes."""

    @property
    def node_type(self) -> str:
        return "http_request"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        url = self.get_input_value(node, "url", context, generator.graph, default="''")
        method = self.get_input_value(node, "method", context, generator.graph, default="'GET'")
        body = self.get_input_value(node, "body", context, generator.graph, default="None")
        headers = self.get_input_value(node, "headers", context, generator.graph, default="{}")

        resp_var = context.generate_variable_name("response")
        status_var = context.generate_variable_name("status_code")
        body_var = context.generate_variable_name("response_body")

        context.set_output_variable(node.id, "response", resp_var)
        context.set_output_variable(node.id, "status_code", status_var)
        context.set_output_variable(node.id, "response_body", body_var)

        context.add_line("import requests")
        context.add_line(f"{resp_var} = requests.request({method}, {url}, json={body}, headers={headers})")
        context.add_line(f"{status_var} = {resp_var}.status_code")
        context.add_line(f"{body_var} = {resp_var}.text")
        context.mark_node_processed(node.id)
