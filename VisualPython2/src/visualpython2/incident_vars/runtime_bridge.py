"""Runtime bridge code generator for incident variables.

Generates Python code that gets injected at the top of compiled scripts
when an incident_id is provided at execution time. This gives scripts
access to get_incident_var(), set_incident_var(), get_incident_data(),
and group incident functions (get_group_incidents(), get_group_incident(),
get_group_incident_count()).
"""

from __future__ import annotations

import json


def generate_incident_bridge_code(
    incident_id: str,
    group_incident_ids: list[str] | None = None,
) -> str:
    """Generate Python code block injected at the top of compiled scripts.

    The generated code creates Redis-backed functions for accessing
    incident variables at runtime. Redis URL is read from the REDIS_URL
    environment variable.

    Args:
        incident_id: The UUID of the primary incident (index 0) to bind to.
        group_incident_ids: Ordered list of all incident IDs in the group.
            Defaults to [incident_id] when None.

    Returns:
        Python source code string to prepend to the compiled script.
    """
    if group_incident_ids is None:
        group_incident_ids = [incident_id]

    group_ids_json = json.dumps(group_incident_ids)

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
        "# --- Incident Group Bridge ---\n"
        f"_group_incident_ids = {group_ids_json}\n"
        "\n"
        "def get_group_incidents():\n"
        '    """Get data dicts for all incidents in the group, ordered."""\n'
        "    result = []\n"
        "    for iid in _group_incident_ids:\n"
        '        key = f"incident:{iid}:data"\n'
        "        raw = _incident_redis.hgetall(key)\n"
        "        if raw:\n"
        "            result.append({k.decode(): _json.loads(v) for k, v in raw.items()})\n"
        "        else:\n"
        '            result.append({"id": iid})\n'
        "    return result\n"
        "\n"
        "def get_group_incident(index):\n"
        '    """Get data dict for a specific incident by index."""\n'
        "    if index < 0 or index >= len(_group_incident_ids):\n"
        '        raise IndexError(f"Incident index {index} out of range (group size: {len(_group_incident_ids)})")\n'
        "    iid = _group_incident_ids[index]\n"
        '    key = f"incident:{iid}:data"\n'
        "    raw = _incident_redis.hgetall(key)\n"
        "    if raw:\n"
        "        return {k.decode(): _json.loads(v) for k, v in raw.items()}\n"
        '    return {"id": iid}\n'
        "\n"
        "def get_group_incident_count():\n"
        '    """Get the number of incidents in the group."""\n'
        "    return len(_group_incident_ids)\n"
        "# --- End Incident Group Bridge ---\n"
        "\n"
    )
