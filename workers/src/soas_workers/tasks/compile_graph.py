"""Compile VisualPython .vpy graph files to standalone .py scripts."""

import hashlib
import json
import os

from soas_workers.celery_app import app
from soas_workers.config import config
from soas_workers.db import get_connection, get_sensitive_incident_variable_names


@app.task(name="soas.compile_graph", bind=True, max_retries=1)
def compile_graph(self, automation_id: str, graph_json: dict):
    """Compile a .vpy graph JSON to a .py script using VisualPython's CodeGenerator.

    This task imports VisualPython's compiler headlessly (no PyQt6 needed).
    The graph_json is the deserialized content of a .vpy file.
    """
    try:
        # Try VisualPython2 compiler first, fall back to VP1
        try:
            from visualpython2.serialization.graph_serializer import GraphSerializer
            from visualpython2.compiler.code_generator import CodeGenerator

            sensitive_vars = get_sensitive_incident_variable_names()
            serializer = GraphSerializer()
            graph = serializer.deserialize(graph_json)
            result = CodeGenerator(graph, debug_mode=True, sensitive_var_names=sensitive_vars).generate()
        except ImportError:
            # Fall back to VP1
            from visualpython.serialization.project_serializer import ProjectSerializer
            from visualpython.compiler.code_generator import (
                CodeGenerator as CodeGeneratorV1,
            )

            serializer = ProjectSerializer()
            graph = serializer.deserialize(graph_json)
            result = CodeGeneratorV1(graph).generate()

        if not result.success:
            _update_automation(automation_id, "draft", errors=result.errors)
            return {"success": False, "errors": result.errors}

        # Write compiled script to automations volume
        os.makedirs(config.AUTOMATIONS_DIR, exist_ok=True)
        script_filename = f"{automation_id}.py"
        script_path = os.path.join(config.AUTOMATIONS_DIR, script_filename)

        with open(script_path, "w") as f:
            f.write(result.code)

        script_hash = hashlib.sha256(result.code.encode()).hexdigest()

        _update_automation(
            automation_id,
            "active",
            script_path=script_filename,
            script_hash=script_hash,
        )

        return {
            "success": True,
            "script_path": script_filename,
            "script_hash": script_hash,
        }

    except ImportError:
        # Neither VP2 nor VP1 available in this worker
        _update_automation(
            automation_id,
            "draft",
            errors=["VisualPython compiler not available in worker"],
        )
        return {
            "success": False,
            "errors": ["VisualPython compiler not available"],
        }

    except Exception as e:
        _update_automation(automation_id, "draft", errors=[str(e)])
        return {"success": False, "errors": [str(e)]}


def _update_automation(
    automation_id: str,
    status: str,
    script_path: str | None = None,
    script_hash: str | None = None,
    errors: list[str] | None = None,
):
    """Update automation record in database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if script_path:
                cur.execute(
                    """
                    UPDATE automations
                    SET status = %s, script_path = %s, script_hash = %s
                    WHERE id = %s::uuid
                    """,
                    (status, script_path, script_hash, automation_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE automations SET status = %s WHERE id = %s::uuid
                    """,
                    (status, automation_id),
                )
        conn.commit()
