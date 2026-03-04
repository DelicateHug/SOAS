"""Runtime bridge code generator for incident variables.

Generates Python code that gets injected at the top of compiled scripts
when an incident_id is provided at execution time. This gives scripts
access to get_incident_var(), set_incident_var(), and get_incident_data().
"""

from __future__ import annotations


def generate_incident_bridge_code(incident_id: str) -> str:
    """Generate Python code block injected at the top of compiled scripts.

    The generated code creates Redis-backed functions for accessing
    incident variables at runtime. Redis URL is read from the REDIS_URL
    environment variable.

    Args:
        incident_id: The UUID of the incident to bind to.

    Returns:
        Python source code string to prepend to the compiled script.
    """
    return (
        "# --- Incident Variable Bridge ---\n"
        "import json as _json\n"
        "import os as _os\n"
        "import redis as _redis\n"
        f'_incident_id = "{incident_id}"\n'
        '_incident_redis = _redis.from_url(_os.environ.get("REDIS_URL", "redis://localhost:6379/0"))\n'
        '_incident_redis_key = f"incident:{_incident_id}:data"\n'
        "\n"
        "def get_incident_var(name, default=None):\n"
        '    """Get an incident variable (Redis first, returns default if missing)."""\n'
        "    val = _incident_redis.hget(_incident_redis_key, name)\n"
        "    if val is not None:\n"
        "        return _json.loads(val)\n"
        "    return default\n"
        "\n"
        "def set_incident_var(name, value):\n"
        '    """Set an incident variable in Redis."""\n'
        "    _incident_redis.hset(_incident_redis_key, name, _json.dumps(value, default=str))\n"
        '    _incident_redis.sadd(f"incident:{_incident_id}:dirty_vars", name)\n'
        "\n"
        "def get_incident_data():\n"
        '    """Get all incident data as a dict."""\n'
        "    data = _incident_redis.hgetall(_incident_redis_key)\n"
        "    return {k.decode(): _json.loads(v) for k, v in data.items()}\n"
        "# --- End Incident Variable Bridge ---\n"
        "\n"
    )
